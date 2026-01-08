"""Конфигурация для админ-панели на базе Telegram Forum Topics."""

import logging
import os

logger = logging.getLogger(__name__)


def get_telegram_admin_group_id() -> int | None:
    """
    Получает ID группы Telegram для админ-панели.
    
    Returns:
        ID группы или None, если не установлен
    """
    group_id_str = os.getenv("TELEGRAM_ADMIN_GROUP_ID")
    if not group_id_str:
        logger.warning("TELEGRAM_ADMIN_GROUP_ID не установлен")
        return None
    
    try:
        return int(group_id_str)
    except ValueError:
        logger.error(
            "TELEGRAM_ADMIN_GROUP_ID должен быть числом, получено: %s",
            group_id_str
        )
        return None


def get_admin_topics_table() -> str:
    """
    Получает название таблицы для хранения топиков в БД.
    
    Returns:
        Название таблицы (по умолчанию "adminpanel")
    """
    return os.getenv("ADMIN_TOPICS_TABLE", "adminpanel")


