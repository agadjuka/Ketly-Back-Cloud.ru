"""
Инструмент для переключения режима на демонстрацию
"""
from typing import Optional, Any
from pydantic import BaseModel, Field
from yandex_cloud_ml_sdk._threads.thread import Thread

try:
    from ..services.logger_service import logger
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
    
    # Поля для внутреннего использования (не передаются LLM)
    storage: Optional[Any] = Field(
        default=None,
        description="Экземпляр DialogStateStorage (внутреннее поле, не используется LLM)",
        exclude=True  # Исключаем из схемы для LLM
    )
    chat_id: Optional[str] = Field(
        default=None,
        description="ID текущего пользователя (внутреннее поле, не используется LLM)",
        exclude=True  # Исключаем из схемы для LLM
    )
    
    def process(self, thread: Thread) -> str:
        """
        Переключение режима на демонстрацию
        
        Args:
            thread: Thread с историей диалога
            
        Returns:
            Строка с маркером [SWITCH_TO_DEMO_RESULT] для обработки в графе
        """
        try:
            from ...storage.dialog_state_storage_factory import get_dialog_state_storage
            
            # Используем chat_id из поля класса, если передан, иначе получаем из thread
            chat_id = self.chat_id
            if not chat_id:
                chat_id = getattr(thread, 'chat_id', None)
            if not chat_id:
                # Пробуем получить из thread.id
                chat_id = getattr(thread, 'id', None)
            
            if not chat_id:
                logger.error("Не удалось получить chat_id для SwitchToDemoTool")
                return "[SWITCH_TO_DEMO_RESULT]"
            
            # Используем storage из поля класса, если передан, иначе получаем через фабрику
            storage = self.storage
            if not storage:
                storage = get_dialog_state_storage()
            
            # Устанавливаем стадию "demo"
            storage.set_stage(str(chat_id), "demo")
            
            logger.info(f"Переключен режим на 'demo' для chat_id={chat_id}")
            
            return "[SWITCH_TO_DEMO_RESULT]"
            
        except Exception as e:
            logger.error(f"Ошибка при переключении на демо-режим: {e}")
            # Возвращаем маркер даже при ошибке, чтобы граф мог обработать
            return "[SWITCH_TO_DEMO_RESULT]"

