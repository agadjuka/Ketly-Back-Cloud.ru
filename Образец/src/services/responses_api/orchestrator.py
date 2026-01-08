"""
Orchestrator для обработки диалогов через Responses API
"""
import json
from typing import List, Dict, Any, Optional
from .client import ResponsesAPIClient
from .tools_registry import ResponsesToolsRegistry
from .config import ResponsesAPIConfig
from ..logger_service import logger

# Импортируем CallManagerException один раз, а не в цикле
try:
    from ...agents.tools.call_manager_tools import CallManagerException
except ImportError:
    CallManagerException = None


class ResponsesOrchestrator:
    """Orchestrator для обработки диалогов через Responses API"""
    
    def __init__(
        self,
        instructions: str,
        tools_registry: Optional[ResponsesToolsRegistry] = None,
        client: Optional[ResponsesAPIClient] = None,
        config: Optional[ResponsesAPIConfig] = None,
    ):
        """
        Инициализация orchestrator
        
        Args:
            instructions: Системные инструкции для ассистента
            tools_registry: Регистрация инструментов (если None, создаётся пустая)
            client: Клиент Responses API (если None, создаётся новый)
            config: Конфигурация (если None, создаётся новая)
        """
        self.instructions = instructions
        self.tools_registry = tools_registry or ResponsesToolsRegistry()
        self.config = config or ResponsesAPIConfig()
        self.client = client or ResponsesAPIClient(self.config)
    
    def run_turn(
        self,
        user_message: str,
        previous_response_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Один полный ход диалога
        
        Args:
            user_message: Сообщение пользователя
            previous_response_id: ID предыдущего ответа для продолжения диалога (None для нового диалога)
            chat_id: ID чата в Telegram (для передачи в инструменты)
            
        Returns:
            Словарь с ключами:
                - reply: Текст ответа для пользователя
                - response_id: ID ответа для сохранения (для следующего запроса)
                - tool_calls: Список вызовов инструментов (если были)
        """
        # Получаем схемы инструментов один раз (не меняются в процессе выполнения)
        tools_schemas = self.tools_registry.get_all_tools_schemas()
        
        # Цикл для обработки множественных вызовов инструментов
        # API может вызывать инструменты несколько раз подряд
        max_iterations = 10  # Максимальное количество итераций для предотвращения бесконечного цикла
        iteration = 0
        tool_calls_info = []
        last_iteration_tool_calls = []  # Результаты инструментов из последней итерации
        reply_text = ""
        current_response_id = previous_response_id
        final_response_id = None
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Итерация {iteration}: Запрос к API (previous_response_id={current_response_id})")
            
            # Формируем input для запроса
            # На первой итерации передаём сообщение пользователя
            # На последующих итерациях передаём результаты инструментов из предыдущей итерации
            input_messages = None
            if iteration == 1:
                # Первый запрос: передаём сообщение пользователя
                input_messages = [{
                    "role": "user",
                    "content": user_message
                }]
            else:
                # Последующие запросы: передаём результаты инструментов из предыдущей итерации
                # Responses API сам управляет историей через previous_response_id
                # Но нужно передать результаты инструментов для продолжения диалога
                input_messages = self._build_tool_results_input(last_iteration_tool_calls)
            
            # Очищаем результаты предыдущей итерации для новой
            last_iteration_tool_calls = []
            
            # Запрос к модели
            try:
                response = self.client.create_response(
                    instructions=self.instructions,
                    input_messages=input_messages,
                    tools=tools_schemas if tools_schemas else None,
                    previous_response_id=current_response_id,
                )
                # Сохраняем полный необработанный JSON ответа для логирования
                last_raw_response = response
            except Exception as e:
                logger.error(f"Ошибка при запросе к API на итерации {iteration}: {e}", exc_info=True)
                # Если это критическая ошибка, прекращаем цикл
                break
            
            # Сохраняем response.id для следующей итерации и финального результата
            if hasattr(response, "id") and response.id:
                current_response_id = response.id
                final_response_id = response.id
                logger.debug(f"Получен response.id: {current_response_id}")
            else:
                logger.warning(f"response.id не найден в ответе на итерации {iteration}")
            
            # Логируем ответ только на уровне DEBUG (избыточно для INFO)
            logger.debug(f"ОТВЕТ ОТ RESPONSES API (итерация {iteration}): output_text={bool(getattr(response, 'output_text', None))}, output_len={len(getattr(response, 'output', []))}")
            
            # Проверяем, есть ли готовый текст ответа
            if hasattr(response, "output_text") and response.output_text:
                reply_text = response.output_text
                logger.info(f"Получен текстовый ответ на итерации {iteration} (длина: {len(reply_text)})")
                break
            
            # Обрабатываем tool_calls
            tool_calls = self._extract_tool_calls(response)
            
            if not tool_calls:
                # Если нет tool_calls, но и нет output_text, прекращаем цикл
                logger.warning(f"Нет tool_calls и нет output_text на итерации {iteration}")
                break
            
            logger.debug(f"Найдено {len(tool_calls)} вызовов инструментов на итерации {iteration}")
            
            # Выполняем инструменты
            for call in tool_calls:
                func_name = call.get("name")
                call_id = call.get("call_id", "")
                args_json = call.get("arguments", "{}")
                
                try:
                    args = json.loads(args_json) if isinstance(args_json, str) else args_json
                except json.JSONDecodeError:
                    logger.error(f"Ошибка парсинга аргументов для {func_name}: {args_json}")
                    args = {}
                
                # Логируем использование инструмента
                logger.info(f"🔧 Использован инструмент: {func_name}")
                logger.info(f"📋 Аргументы: {json.dumps(args, ensure_ascii=False, indent=2)}")
                
                # Вызываем инструмент
                try:
                    # Передаём None для conversation_history, так как Responses API сам управляет историей
                    result = self.tools_registry.call_tool(func_name, args, conversation_history=None, chat_id=chat_id)
                    
                    # Сохраняем информацию о вызове инструмента
                    tool_call_info = {
                        "name": func_name,
                        "call_id": call_id,
                        "args": args,
                        "result": result,
                    }
                    tool_calls_info.append(tool_call_info)
                    last_iteration_tool_calls.append(tool_call_info)
                    
                except Exception as e:
                    # Проверяем, не является ли это CallManagerException
                    if CallManagerException and isinstance(e, CallManagerException):
                        # CallManager был вызван - возвращаем специальный результат
                        escalation_result = e.escalation_result
                        logger.info(f"CallManager вызван через инструмент {func_name}")
                        
                        return {
                            "reply": escalation_result.get("user_message"),
                            "response_id": final_response_id,
                            "tool_calls": tool_calls_info,
                            "call_manager": True,
                            "manager_alert": escalation_result.get("manager_alert"),
                        }
                    
                    # Обрабатываем ошибку инструмента
                    logger.error(f"Ошибка при вызове инструмента {func_name}: {e}", exc_info=True)
                    error_result = f"Ошибка при выполнении инструмента: {str(e)}"
                    
                    # Сохраняем информацию об ошибке
                    tool_call_info = {
                        "name": func_name,
                        "call_id": call_id,
                        "args": args,
                        "result": error_result,
                    }
                    tool_calls_info.append(tool_call_info)
                    last_iteration_tool_calls.append(tool_call_info)
        
        if iteration >= max_iterations:
            logger.warning(f"Достигнут лимит итераций ({max_iterations}). Прекращаем цикл.")
        
        if not reply_text:
            logger.warning(f"Не получен текстовый ответ после {iteration} итераций")
        
        logger.debug(f"Финальный результат: итераций={iteration}, длина ответа={len(reply_text) if reply_text else 0}, инструментов={len(tool_calls_info)}, response_id={final_response_id}")
        
        return {
            "reply": reply_text,
            "response_id": final_response_id,
            "tool_calls": tool_calls_info,
            "raw_response": last_raw_response if 'last_raw_response' in locals() else None,
        }
    
    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """
        Извлечение tool_calls из ответа Responses API
        
        Args:
            response: Ответ от Responses API
            
        Returns:
            Список tool_calls
        """
        tool_calls = []
        
        # Проверяем наличие output в ответе
        if not hasattr(response, "output"):
            return tool_calls
        
        output = response.output
        if not output:
            return tool_calls
        
        # Обрабатываем каждый элемент output
        for item in output:
            # item может быть словарём, а не объектом
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "function_call":
                    tool_call = {
                        "name": item.get("name", ""),
                        "call_id": item.get("call_id", ""),
                        "arguments": item.get("arguments", "{}"),
                    }
                    tool_calls.append(tool_call)
            elif hasattr(item, "type"):
                if item.type == "function_call":
                    tool_call = {
                        "name": getattr(item, "name", ""),
                        "call_id": getattr(item, "call_id", ""),
                        "arguments": getattr(item, "arguments", "{}"),
                    }
                    tool_calls.append(tool_call)
        
        return tool_calls
    
    def _build_tool_results_input(self, tool_calls_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Формирование input с результатами инструментов для передачи в Responses API
        
        Args:
            tool_calls_info: Список информации о вызовах инструментов из последней итерации
            
        Returns:
            Список сообщений для input
        """
        input_messages = []
        
        # Добавляем результаты инструментов из последней итерации
        # Берем только результаты из последней итерации (последние N элементов, где N - количество tool_calls)
        for tool_call in tool_calls_info:
            call_id = tool_call.get("call_id", "")
            func_name = tool_call.get("name", "")
            args = tool_call.get("args", {})
            result = tool_call.get("result", "")
            
            # Добавляем function_call
            input_messages.append({
                "type": "function_call",
                "call_id": call_id,
                "name": func_name,
                "arguments": json.dumps(args, ensure_ascii=False) if not isinstance(args, str) else args,
            })
            
            # Добавляем результат
            input_messages.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result,
            })
        
        return input_messages

