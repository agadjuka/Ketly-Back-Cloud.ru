"""
Сервис для отладки и логирования запросов
"""
import json
import os
from datetime import datetime
from .logger_service import logger


class DebugService:
    """Сервис для сохранения debug-логов"""
    
    def __init__(self):
        """Инициализация сервиса отладки"""
        # Проверяем, нужно ли сохранять debug логи
        # В облачной версии (контейнере) отключаем сохранение логов
        self.debug_enabled = os.getenv('ENABLE_DEBUG_LOGS', 'false').lower() == 'true'
        self.debug_logs_dir = "debug_logs"
        
        if self.debug_enabled:
            # Создаем папку для логов, если её нет (только если включено)
            try:
                os.makedirs(self.debug_logs_dir, exist_ok=True)
            except Exception as e:
                logger.warning(f"Не удалось создать папку {self.debug_logs_dir}: {str(e)}")
        else:
            logger.debug("Debug логи отключены (работа в контейнере)")
    
    def save_request(self, payload: dict, chat_id: str):
        """Сохранить запрос к LLM в файл для дебага"""
        if not self.debug_enabled:
            return
        
        try:
            # Убеждаемся, что папка существует
            os.makedirs(self.debug_logs_dir, exist_ok=True)
            
            # Создаем имя файла с временной меткой
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.debug_logs_dir, f"llm_request_{chat_id}_{timestamp}.json")
            
            # Сохраняем payload как есть, без форматирования
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=None, separators=(',', ':'))
            
            logger.debug("Запрос к LLM сохранен", filename)
            
        except Exception as e:
            logger.error("Ошибка при сохранении запроса", str(e))
    
    def save_response(self, response: dict, chat_id: str):
        """Сохранить ответ от LLM в файл для дебага"""
        if not self.debug_enabled:
            return
        
        try:
            # Убеждаемся, что папка существует
            os.makedirs(self.debug_logs_dir, exist_ok=True)
            
            # Создаем имя файла с временной меткой
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.debug_logs_dir, f"llm_response_{chat_id}_{timestamp}.json")
            
            # Сохраняем response как есть, без форматирования
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(response, f, ensure_ascii=False, indent=None, separators=(',', ':'))
            
            logger.debug("Ответ от LLM сохранен", filename)
            
        except Exception as e:
            logger.error("Ошибка при сохранении ответа", str(e))