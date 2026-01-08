"""
Клиент для работы с OpenAI API (cloud.ru)
"""
import json
import re
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI
from openai import InternalServerError, RateLimitError, APIError
from .config import ResponsesAPIConfig
from ..logger_service import logger


# Валидные роли для OpenAI API
VALID_ROLES = {"system", "user", "assistant", "tool"}


class ResponsesAPIClient:
    """Клиент для работы с OpenAI API"""
    
    def __init__(self, config: Optional[ResponsesAPIConfig] = None):
        self.config = config or ResponsesAPIConfig()
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )
        # Настройки retry
        self.max_retries = 3
        self.retry_delay = 1.0  # секунды
    
    def _normalize_text(self, text: str) -> str:
        """
        Нормализует текст для отправки в API
        
        Убирает проблемные символы и форматирование, которые могут вызвать ошибки
        """
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        
        # Убираем нулевые байты и другие проблемные символы
        text = text.replace('\x00', '')
        
        # Нормализуем переносы строк
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Убираем множественные пробелы (но сохраняем переносы строк)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Убираем пробелы в начале и конце каждой строки
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Убираем множественные пустые строки
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Убираем управляющие символы, кроме стандартных (табуляция, перенос строки)
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        
        return text.strip()
    
    def _validate_and_normalize_role(self, role: Any) -> str:
        """
        Валидирует и нормализует роль сообщения
        
        Args:
            role: Роль из сообщения
            
        Returns:
            Валидная роль (user, assistant, system, tool)
        """
        if not isinstance(role, str):
            role = str(role) if role is not None else "user"
        
        role_lower = role.lower().strip()
        
        # Маппинг недопустимых ролей
        role_mapping = {
            "final": "assistant",  # Роль "final" не поддерживается, заменяем на assistant
            "model": "assistant",
            "ai": "assistant",
            "bot": "assistant",
        }
        
        if role_lower in role_mapping:
            logger.warning(f"Обнаружена недопустимая роль '{role}', заменяем на '{role_mapping[role_lower]}'")
            return role_mapping[role_lower]
        
        # Проверяем, что роль валидная
        if role_lower not in VALID_ROLES:
            logger.error(f"Обнаружена неизвестная роль '{role}', заменяем на 'user'")
            return "user"
        
        return role_lower
    
    def _validate_tool_calls(self, tool_calls: Any) -> Optional[List[Dict[str, Any]]]:
        """
        Валидирует и нормализует tool_calls
        
        Args:
            tool_calls: tool_calls из сообщения
            
        Returns:
            Нормализованный список tool_calls или None
        """
        if not tool_calls:
            return None
        
        if not isinstance(tool_calls, list):
            logger.warning(f"tool_calls не является списком: {type(tool_calls)}, пропускаем")
            return None
        
        normalized_calls = []
        for tc in tool_calls:
            try:
                # Если это уже словарь
                if isinstance(tc, dict):
                    # Поддержка формата LangGraph (name, args, id)
                    if "name" in tc and "args" in tc:
                        import json
                        normalized_tc = {
                            "id": str(tc.get("id", "")),
                            "type": "function",
                            "function": {
                                "name": str(tc.get("name", "")),
                                "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False)
                            }
                        }
                        normalized_calls.append(normalized_tc)
                        continue
                    
                    # Проверяем обязательные поля для формата OpenAI
                    if "id" not in tc or "function" not in tc:
                        continue
                    
                    # Нормализуем структуру
                    normalized_tc = {
                        "id": str(tc.get("id", "")),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": str(tc.get("function", {}).get("name", "")),
                            "arguments": str(tc.get("function", {}).get("arguments", "{}"))
                        }
                    }
                    normalized_calls.append(normalized_tc)
                
                # Если это объект SDK
                elif hasattr(tc, 'id') and hasattr(tc, 'function'):
                    normalized_tc = {
                        "id": str(tc.id),
                        "type": "function",
                        "function": {
                            "name": str(tc.function.name),
                            "arguments": str(tc.function.arguments)
                        }
                    }
                    normalized_calls.append(normalized_tc)
                else:
                    logger.warning(f"Неизвестный формат tool_call: {type(tc)}, пропускаем")
                    
            except Exception as e:
                logger.error(f"Ошибка при нормализации tool_call: {e}, пропускаем")
                continue
        
        return normalized_calls if normalized_calls else None
    
    def _normalize_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Нормализует сообщение для отправки в API
        
        Returns:
            Нормализованное сообщение или None, если сообщение невалидно
        """
        # Валидируем и нормализуем роль
        role = self._validate_and_normalize_role(message.get("role", "user"))
        
        # ВАЖНО: НЕ фильтруем system сообщения - передаем ВСЕ типы сообщений для полного контекста
        # System сообщения из истории могут содержать важный контекст диалога
        
        # Нормализуем content
        content = self._normalize_text(message.get("content", ""))
        
        # Для tool сообщений требуется tool_call_id
        if role == "tool":
            tool_call_id = message.get("tool_call_id")
            if not tool_call_id:
                logger.warning("Tool сообщение без tool_call_id, пропускаем")
                return None
            
            return {
                "role": "tool",
                "tool_call_id": str(tool_call_id),
                "content": content
            }
        
        # Для assistant сообщений
        normalized = {
            "role": role,
            "content": content
        }
        
        # Валидируем и добавляем tool_calls если есть (только для assistant)
        if role == "assistant" and "tool_calls" in message:
            tool_calls = self._validate_tool_calls(message["tool_calls"])
            if tool_calls:
                normalized["tool_calls"] = tool_calls
        
        # Для user сообщений просто content
        return normalized
    
    def create_response(
        self,
        instructions: str,
        input_messages: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        previous_response_id: Optional[str] = None, # Not used in OpenAI chat completions usually
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        agent_name: Optional[str] = None,
    ) -> Any:
        """
        Создание запроса к OpenAI API
        """
        try:
            # Импортируем логгер для сырых запросов
            from ..llm_request_logger import llm_request_logger
            
            # Нормализуем instructions
            normalized_instructions = self._normalize_text(instructions)
            
            # Проверяем, что инструкции не пустые
            if not normalized_instructions or len(normalized_instructions.strip()) == 0:
                logger.warning("Получены пустые инструкции, используем дефолтные")
                normalized_instructions = "You are a helpful assistant."
            
            # Формируем сообщения
            messages = []
            
            # System message
            messages.append({
                "role": "system",
                "content": normalized_instructions
            })
            
            # History - нормализуем каждое сообщение
            if input_messages:
                for idx, msg in enumerate(input_messages):
                    try:
                        normalized_msg = self._normalize_message(msg)
                        # Пропускаем None (невалидные сообщения)
                        if normalized_msg is None:
                            continue
                        
                        # Пропускаем пустые сообщения (кроме tool, которые могут быть без content)
                        if normalized_msg.get("role") != "tool":
                            if not normalized_msg.get("content") and not normalized_msg.get("tool_calls"):
                                logger.debug(f"Пропущено пустое сообщение на позиции {idx}")
                                continue
                        
                        messages.append(normalized_msg)
                    except Exception as e:
                        logger.warning(f"Ошибка при нормализации сообщения на позиции {idx}: {e}, пропускаем")
                        continue
            
            # Параметры
            params = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": max_output_tokens if max_output_tokens is not None else self.config.max_tokens,
                "temperature": temperature if temperature is not None else self.config.temperature,
                "top_p": self.config.top_p,
                "presence_penalty": self.config.presence_penalty,
            }
            
            if tools:
                params["tools"] = tools
                logger.debug(f"Tools count: {len(tools)}")
                # Логируем схемы инструментов для диагностики
                try:
                    import json
                    tools_json = json.dumps(tools, ensure_ascii=False, indent=2)
                    logger.debug(f"Tools schemas (first 1000 chars): {tools_json[:1000]}")
                except Exception as e:
                    logger.warning(f"Не удалось сериализовать схемы инструментов: {e}")
            
            logger.debug(f"Sending request to OpenAI: {len(messages)} messages")
            logger.debug(f"Instructions length: {len(normalized_instructions)} chars")
            logger.debug(f"System message (first 200 chars): {normalized_instructions[:200]}")
            
            # Логируем первые несколько сообщений для диагностики
            if messages:
                logger.debug(f"First message role: {messages[0].get('role')}, content length: {len(messages[0].get('content', ''))}")
                if len(messages) > 1:
                    logger.debug(f"Second message role: {messages[1].get('role')}, content length: {len(messages[1].get('content', ''))}")
            
            # Retry механизм для временных ошибок
            last_exception = None
            request_id = None
            for attempt in range(self.max_retries):
                # Логируем запрос при каждой попытке (параметры могут измениться)
                if attempt == 0:
                    # Сохраняем запрос только при первой попытке
                    request_id = llm_request_logger.save_request(
                        request_data=params,
                        agent_name=agent_name
                    )
                    if request_id is None:
                        request_id = 0  # Если логирование отключено, используем 0
                
                try:
                    response = self.client.chat.completions.create(**params)
                    
                    # Логируем ответ после получения
                    llm_request_logger.save_response(
                        response_data=response,
                        agent_name=agent_name,
                        request_id=request_id
                    )
                    
                    return response
                    
                except (InternalServerError, RateLimitError) as e:
                    last_exception = e
                    error_code = getattr(e, 'status_code', None) or getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                    
                    # Проверяем, стоит ли повторять
                    if attempt < self.max_retries - 1:
                        # Для 500, 502, 503, 429 делаем retry
                        if error_code in [500, 502, 503, 429] or "500" in str(e) or "502" in str(e) or "503" in str(e) or "429" in str(e):
                            delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(f"Временная ошибка API (попытка {attempt + 1}/{self.max_retries}): {e}. Повтор через {delay}с")
                            time.sleep(delay)
                            continue
                    
                    # Если это ошибка с токенами structured outputs, пробуем без tools
                    if "token" in str(e).lower() and "2000" in str(e) and tools:
                        logger.warning(f"Ошибка structured outputs токенов, пробуем без tools: {e}")
                        try:
                            params_without_tools = params.copy()
                            params_without_tools.pop("tools", None)
                            
                            # Логируем запрос без tools
                            request_id_no_tools = llm_request_logger.save_request(
                                request_data=params_without_tools,
                                agent_name=agent_name
                            )
                            
                            response = self.client.chat.completions.create(**params_without_tools)
                            
                            # Логируем ответ
                            llm_request_logger.save_response(
                                response_data=response,
                                agent_name=agent_name,
                                request_id=request_id_no_tools
                            )
                            
                            logger.warning("Успешно выполнен запрос без tools после ошибки токенов")
                            return response
                        except Exception as e2:
                            logger.error(f"Ошибка при запросе без tools: {e2}")
                    
                    # Если не удалось повторить, пробрасываем исключение
                    raise
                    
                except APIError as e:
                    # Для других API ошибок не делаем retry
                    logger.error(f"API ошибка: {e}")
                    raise
                    
                except Exception as e:
                    # Для неизвестных ошибок пробуем еще раз, если это первая попытка
                    if attempt < self.max_retries - 1 and "token" not in str(e).lower():
                        delay = self.retry_delay * (2 ** attempt)
                        logger.warning(f"Неизвестная ошибка (попытка {attempt + 1}/{self.max_retries}): {e}. Повтор через {delay}с")
                        time.sleep(delay)
                        continue
                    raise
            
            # Если все попытки исчерпаны
            if last_exception:
                raise last_exception
            
        except Exception as e:
            logger.error(f"Ошибка при создании запроса к OpenAI API: {e}", exc_info=True)
            logger.error(f"Instructions (first 500 chars): {instructions[:500] if instructions else 'None'}")
            logger.error(f"Messages count: {len(messages) if 'messages' in locals() else 0}")
            if 'messages' in locals() and messages:
                logger.error(f"First message: role={messages[0].get('role')}, has_content={bool(messages[0].get('content'))}, has_tool_calls={bool(messages[0].get('tool_calls'))}")
            
            raise
