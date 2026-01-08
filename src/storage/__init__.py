"""Модуль для работы с хранилищем данных."""

from src.storage.topic_storage import BaseTopicStorage
from src.storage.topic_storage_factory import get_topic_storage

__all__ = [
    "BaseTopicStorage",
    "get_topic_storage",
]


