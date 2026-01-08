"""Реализация хранилища топиков на базе PostgreSQL."""

import logging
import re
from typing import Optional, Union
import psycopg

from src.storage.topic_storage import BaseTopicStorage
from src.config.admin_config import get_admin_topics_table
from src.storage.checkpointer import _get_connection_string

logger = logging.getLogger(__name__)


class PostgresTopicStorage(BaseTopicStorage):
    """Реализация хранилища топиков на базе PostgreSQL."""

    def __init__(self, connection_string: Optional[str] = None):
        """
        Инициализирует хранилище топиков.
        
        Args:
            connection_string: Строка подключения к PostgreSQL.
                              Если не указана, берется из переменных окружения.
        """
        self.connection_string = connection_string or _get_connection_string()
        self.table_name = get_admin_topics_table()
        logger.debug(f"Инициализирован PostgresTopicStorage с таблицей '{self.table_name}'")

    def _get_connection(self):
        """Получает соединение с базой данных (синхронное)."""
        return psycopg.connect(self.connection_string, autocommit=True)

    def _is_uuid(self, user_id: Union[int, str]) -> bool:
        """
        Проверяет, является ли user_id UUID строкой.
        
        Args:
            user_id: ID пользователя (int или str)
            
        Returns:
            True если это UUID, False иначе
        """
        if isinstance(user_id, int):
            return False
        if isinstance(user_id, str):
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            return bool(re.match(uuid_pattern, user_id, re.IGNORECASE))
        return False

    def save_topic(self, user_id: Union[int, str], topic_id: int, topic_name: str) -> None:
        """
        Сохраняет связь между пользователем и топиком.
        
        Args:
            user_id: ID пользователя Telegram (int) или UUID строки для веб-пользователей
            topic_id: ID топика в Telegram Forum
            topic_name: Название топика
        """
        # Преобразуем user_id в строку для универсального хранения (поддержка и int, и UUID)
        user_id_str = str(user_id)
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.table_name} (user_id, topic_id, topic_name, mode, updated_at)
                    VALUES (%s, %s, %s, 'auto', NOW())
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        topic_id = EXCLUDED.topic_id,
                        topic_name = EXCLUDED.topic_name,
                        updated_at = NOW()
                    """,
                    (user_id_str, topic_id, topic_name)
                )
                logger.debug(
                    f"Сохранена связь user_id={user_id_str} -> topic_id={topic_id} "
                    f"(name={topic_name})"
                )

    def get_topic_id(self, user_id: Union[int, str]) -> int | None:
        """
        Получает ID топика по ID пользователя.
        
        Args:
            user_id: ID пользователя Telegram (int) или UUID строки для веб-пользователей
            
        Returns:
            ID топика или None, если связь не найдена
        """
        # Преобразуем user_id в строку для поиска
        user_id_str = str(user_id)
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT topic_id FROM {self.table_name} WHERE user_id = %s",
                    (user_id_str,)
                )
                row = cur.fetchone()
                return row[0] if row else None

    def get_user_id(self, topic_id: int) -> int | None:
        """
        Получает ID пользователя по ID топика (обратная связь).
        
        Args:
            topic_id: ID топика в Telegram Forum
            
        Returns:
            ID пользователя или None, если связь не найдена
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT user_id FROM {self.table_name} WHERE topic_id = %s",
                    (topic_id,)
                )
                row = cur.fetchone()
                return row[0] if row else None

    def set_mode(self, user_id: Union[int, str], mode: str) -> None:
        """
        Устанавливает режим работы для пользователя.
        
        Args:
            user_id: ID пользователя Telegram (int) или UUID строки для веб-пользователей
            mode: Режим работы ("auto" или "manual")
        """
        # Преобразуем user_id в строку
        user_id_str = str(user_id)
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {self.table_name} 
                    SET mode = %s, updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (mode, user_id_str)
                )
                logger.debug(f"Установлен режим '{mode}' для user_id={user_id_str}")

    def get_mode(self, user_id: Union[int, str]) -> str:
        """
        Получает режим работы для пользователя.
        
        Args:
            user_id: ID пользователя Telegram (int) или UUID строки для веб-пользователей
            
        Returns:
            Режим работы ("auto" или "manual"). По умолчанию "auto", если поле не установлено.
        """
        # Преобразуем user_id в строку
        user_id_str = str(user_id)
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT mode FROM {self.table_name} WHERE user_id = %s",
                    (user_id_str,)
                )
                row = cur.fetchone()
                return row[0] if row else "auto"

