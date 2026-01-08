"""Модуль для работы с хранилищем данных."""

from src.storage.topic_storage import BaseTopicStorage
from src.storage.ydb_topic_storage import YDBTopicStorage
from src.storage.topic_storage_factory import get_topic_storage
from src.storage.dialog_state_storage import DialogStateStorage
from src.storage.dialog_state_storage_factory import get_dialog_state_storage

__all__ = [
    "BaseTopicStorage",
    "YDBTopicStorage",
    "get_topic_storage",
    "DialogStateStorage",
    "get_dialog_state_storage",
]


