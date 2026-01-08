"""
Клиент для работы с Responses API Yandex Cloud
"""
import json
import requests
from typing import List, Dict, Any, Optional
from .config import ResponsesAPIConfig
from ..logger_service import logger


class ResponsesAPIClient:
    """Клиент для работы с Responses API"""
    
    def __init__(self, config: Optional[ResponsesAPIConfig] = None):
        self.config = config or ResponsesAPIConfig()
        self.base_url = self.config.base_url
        self.api_key = self.config.api_key
        self.project = self.config.project
    
    def create_response(
        self,
        instructions: str,
        input_messages: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        previous_response_id: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        """
        Создание запроса к Responses API
        
        Args:
            instructions: Системные инструкции для ассистента
            input_messages: Сообщения для нового диалога (используется только если previous_response_id не указан)
            tools: Список инструментов в формате OpenAI function tools
            previous_response_id: ID предыдущего ответа для продолжения диалога
            max_output_tokens: Максимальное количество токенов в ответе
            temperature: Температура модели
            
        Returns:
            Ответ от Responses API (объект с атрибутами id, output_text и output)
        """
        try:
            url = f"{self.base_url}/responses"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "x-folder-id": self.project,
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.config.model_uri,
                "instructions": instructions,
            }
            
            # Используем previous_response_id для продолжения диалога (если есть)
            if previous_response_id:
                payload["previous_response_id"] = previous_response_id
            
            # input_messages добавляется всегда, когда указан (для нового сообщения или результатов инструментов)
            if input_messages:
                payload["input"] = input_messages
            
            if tools:
                payload["tools"] = tools
            
            if max_output_tokens is not None:
                payload["max_output_tokens"] = max_output_tokens
            else:
                payload["max_output_tokens"] = self.config.max_output_tokens
            
            if temperature is not None:
                payload["temperature"] = temperature
            else:
                payload["temperature"] = self.config.temperature
            
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            
            # Создаём объект-обёртку для совместимости с кодом
            class ResponseWrapper:
                def __init__(self, data):
                    self._data = data
                    # Сохраняем полный необработанный JSON ответа
                    self._raw_json = data
                    
                    # Извлекаем response.id (обязательное поле для памяти диалога)
                    self.id = data.get("id") if isinstance(data, dict) else None
                    if not self.id:
                        logger.warning("response.id не найден в ответе API - память диалога не будет работать")
                    
                    # Извлекаем output_text из структуры output
                    output_raw = data.get("output") if isinstance(data, dict) else None
                    self.output = output_raw if output_raw is not None else []
                    
                    # Извлекаем текст из output[0]['content'][0]['text']
                    output_text = ""
                    if self.output and isinstance(self.output, list) and len(self.output) > 0:
                        # Логируем структуру output для диагностики
                        logger.debug(f"Структура output: {json.dumps(self.output, ensure_ascii=False, indent=2)}")
                        
                        first_output = self.output[0]
                        if isinstance(first_output, dict):
                            content = first_output.get("content", [])
                            if isinstance(content, list) and len(content) > 0:
                                # Ищем элемент с type='output_text'
                                for item in content:
                                    if isinstance(item, dict):
                                        item_type = item.get("type")
                                        if item_type == "output_text":
                                            output_text = item.get("text", "")
                                            logger.debug(f"Найден output_text: {output_text[:100]}...")
                                            break
                                        else:
                                            logger.debug(f"Пропущен элемент с type={item_type}")
                    
                    if not output_text:
                        logger.warning("output_text не найден в ответе API")
                        logger.debug(f"Полная структура output: {json.dumps(self.output, ensure_ascii=False, indent=2)}")
                    
                    self.output_text = output_text
            
            return ResponseWrapper(result)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при создании запроса к Responses API: {e}", exc_info=True)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Детали ошибки: {error_detail}")
                except:
                    logger.error(f"Текст ответа: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании запроса к Responses API: {e}", exc_info=True)
            raise
