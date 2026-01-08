"""
Инструмент для переключения режима на демонстрацию
"""
from typing import Optional, Any
from pydantic import BaseModel, Field
from yandex_cloud_ml_sdk._threads.thread import Thread

try:
    from ...services.logger_service import logger
except ImportError:
    class SimpleLogger:
        def error(self, msg, *args, **kwargs):
            print(f"ERROR: {msg}")
        def info(self, msg, *args, **kwargs):
            print(f"INFO: {msg}")
    logger = SimpleLogger()


class SwitchToDemoTool(BaseModel):
    """
    Используй этот инструмент, если пользователь согласился на демонстрацию, хочет попробовать демо-режим или посмотреть симуляцию. Больше ничего не пиши в ответе, просто вызови этот инструмент.
    """
    
    def process(self, thread: Thread) -> str:
        """
        Переключение режима на демонстрацию
        
        ВАЖНО: Не использует DialogStateStorage (YDB).
        Возвращает маркер [SWITCH_TO_DEMO_RESULT] для обработки в графе.
        Граф обновит state["stage"] = "demo" автоматически.
        
        Args:
            thread: Thread с историей диалога
            
        Returns:
            Строка с маркером [SWITCH_TO_DEMO_RESULT] для обработки в графе
        """
        try:
            # Получаем chat_id из thread (для логирования)
            chat_id = getattr(thread, 'chat_id', None)
            if not chat_id:
                # Пробуем получить из thread.id
                chat_id = getattr(thread, 'id', None)
            
            if chat_id:
                logger.info(f"SwitchToDemoTool вызван для chat_id={chat_id}")
            else:
                logger.info("SwitchToDemoTool вызван (chat_id не определен)")
            
            # КЛЮЧЕВОЕ ОТЛИЧИЕ: Не записываем в YDB, только возвращаем маркер
            # Граф обработает маркер и обновит state["stage"] = "demo"
            return "[SWITCH_TO_DEMO_RESULT]"
            
        except Exception as e:
            logger.error(f"Ошибка при переключении на демо-режим: {e}")
            # Возвращаем маркер даже при ошибке, чтобы граф мог обработать
            return "[SWITCH_TO_DEMO_RESULT]"

