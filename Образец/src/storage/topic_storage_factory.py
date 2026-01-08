"""Фабрика для создания экземпляра хранилища топиков."""

import logging

from src.storage.ydb_topic_storage import YDBTopicStorage
from src.storage.topic_storage import BaseTopicStorage

logger = logging.getLogger(__name__)

# Глобальный экземпляр хранилища
_topic_storage: BaseTopicStorage | None = None


def get_topic_storage() -> BaseTopicStorage:
    """
    Получает или создает экземпляр хранилища топиков.
    
    Returns:
        Экземпляр хранилища топиков (по умолчанию YDBTopicStorage)
    """
    global _topic_storage
    
    if _topic_storage is None:
        try:
            _topic_storage = YDBTopicStorage()
            logger.info("Инициализирован YDBTopicStorage")
        except ValueError as e:
            logger.error(
                "Не удалось инициализировать YDBTopicStorage: %s. "
                "Убедитесь, что YDB настроен правильно.",
                str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Ошибка при инициализации хранилища топиков: %s",
                str(e),
            )
            raise
    
    return _topic_storage


