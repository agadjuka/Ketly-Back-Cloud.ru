"""Фабрика для создания экземпляра хранилища топиков."""

import logging
from typing import Optional

from src.storage.topic_storage import BaseTopicStorage
from src.config.admin_config import get_telegram_admin_group_id

logger = logging.getLogger(__name__)

# Глобальный экземпляр хранилища
_topic_storage: Optional[BaseTopicStorage] = None


def get_topic_storage() -> Optional[BaseTopicStorage]:
    """
    Получает или создает экземпляр хранилища топиков.
    
    Если TELEGRAM_ADMIN_GROUP_ID установлен, автоматически инициализирует PostgresTopicStorage.
    
    Returns:
        Экземпляр хранилища топиков или None, если админ-панель не настроена
    """
    global _topic_storage
    
    if _topic_storage is None:
        # Проверяем, настроена ли админ-панель
        admin_group_id = get_telegram_admin_group_id()
        if admin_group_id is not None:
            # Админ-панель настроена, инициализируем PostgresTopicStorage
            try:
                from src.storage.postgres_topic_storage import PostgresTopicStorage
                _topic_storage = PostgresTopicStorage()
                logger.info("Инициализирован PostgresTopicStorage для админ-панели")
            except Exception as e:
                logger.error(
                    f"Не удалось инициализировать PostgresTopicStorage: {e}. "
                    "Убедитесь, что таблица создана через create_admin_panel_table.py"
                )
                raise
        else:
            logger.debug("Админ-панель не настроена (TELEGRAM_ADMIN_GROUP_ID не установлен)")
    
    return _topic_storage


