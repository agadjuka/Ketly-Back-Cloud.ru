"""Реализация хранилища топиков на базе YDB."""

import logging
import os
from typing import Optional

from src.storage.topic_storage import BaseTopicStorage

logger = logging.getLogger(__name__)


class YDBTopicStorage(BaseTopicStorage):
    """
    Реализация хранилища топиков на базе YDB.
    
    Структура хранения:
    - Таблица: adminpanel
    - Поля: user_id (String), topic_id (String), topic_name (String), mode (String)
    - PRIMARY KEY: user_id
    - Для обратного поиска используется запрос по topic_id
    """

    def __init__(
        self,
        ydb_client=None,
        table_name: Optional[str] = None,
    ):
        """
        Инициализирует хранилище топиков в YDB.
        
        Args:
            ydb_client: Экземпляр YDBClient (если None, будет получен при первом использовании)
            table_name: Название таблицы (если None, используется "adminpanel")
        """
        from src.config.admin_config import get_admin_topics_table
        
        self.table_name = table_name or get_admin_topics_table()
        self._ydb_client = ydb_client
        
        logger.debug(
            "Инициализирован YDBTopicStorage (table=%s)",
            self.table_name,
        )

    @property
    def ydb_client(self):
        """Получает или создает экземпляр YDBClient."""
        if self._ydb_client is None:
            from src.ydb_client import get_ydb_client
            self._ydb_client = get_ydb_client()
        return self._ydb_client

    def save_topic(self, user_id: int, topic_id: int, topic_name: str) -> None:
        """
        Сохраняет связь между пользователем и топиком.
        
        Args:
            user_id: ID пользователя Telegram
            topic_id: ID топика в Telegram Forum
            topic_name: Название топика
        """
        try:
            query = f"""
            DECLARE $user_id AS String;
            DECLARE $topic_id AS String;
            DECLARE $topic_name AS String;
            UPSERT INTO {self.table_name} (user_id, topic_id, topic_name)
            VALUES ($user_id, $topic_id, $topic_name);
            """
            
            self.ydb_client._execute_query(query, {
                "$user_id": str(user_id),
                "$topic_id": str(topic_id),
                "$topic_name": topic_name,
            })
            
            logger.debug(
                "Сохранена связь: user_id=%s -> topic_id=%s (%s)",
                user_id,
                topic_id,
                topic_name,
            )
        except Exception as e:
            logger.error(
                "Ошибка при сохранении связи user_id=%s -> topic_id=%s: %s",
                user_id,
                topic_id,
                str(e),
            )
            raise

    def get_topic_id(self, user_id: int) -> int | None:
        """
        Получает ID топика по ID пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            ID топика или None, если связь не найдена
        """
        try:
            query = f"""
            DECLARE $user_id AS String;
            SELECT topic_id FROM {self.table_name} WHERE user_id = $user_id;
            """
            
            result = self.ydb_client._execute_query(query, {"$user_id": str(user_id)})
            rows = result[0].rows
            
            if not rows or not rows[0].topic_id:
                return None
            
            return int(rows[0].topic_id.decode() if isinstance(rows[0].topic_id, bytes) else rows[0].topic_id)
        except Exception as e:
            logger.error(
                "Ошибка при получении topic_id для user_id=%s: %s",
                user_id,
                str(e),
            )
            return None

    def get_user_id(self, topic_id: int) -> int | None:
        """
        Получает ID пользователя по ID топика (обратная связь).
        
        Args:
            topic_id: ID топика в Telegram Forum
            
        Returns:
            ID пользователя или None, если связь не найдена
        """
        try:
            query = f"""
            DECLARE $topic_id AS String;
            SELECT user_id FROM {self.table_name} WHERE topic_id = $topic_id;
            """
            
            result = self.ydb_client._execute_query(query, {"$topic_id": str(topic_id)})
            rows = result[0].rows
            
            if not rows or not rows[0].user_id:
                return None

            user_id_raw = rows[0].user_id
            user_id_str = user_id_raw.decode() if isinstance(user_id_raw, bytes) else user_id_raw

            # Поддерживаем оба варианта:
            # - числовые Telegram user_id
            # - строковые thread_id из веб-фронтенда (UUID и др.)
            try:
                # Если это число, вернем int (для Telegram-пользователей)
                return int(user_id_str)
            except (TypeError, ValueError):
                # Если это не число (например, UUID), вернем строку как есть
                return user_id_str
        except Exception as e:
            logger.error(
                "Ошибка при получении user_id для topic_id=%s: %s",
                topic_id,
                str(e),
            )
            return None

    def set_mode(self, user_id: int, mode: str) -> None:
        """
        Устанавливает режим работы для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            mode: Режим работы ("auto" или "manual")
        """
        if mode not in ("auto", "manual"):
            raise ValueError(f"Недопустимый режим: {mode}. Допустимые значения: 'auto', 'manual'")
        
        try:
            topic_id = self.get_topic_id(user_id)
            if topic_id is None:
                logger.warning(
                    "Невозможно установить режим: не найден topic_id для user_id=%s",
                    user_id,
                )
                return
            
            query = f"""
            DECLARE $user_id AS String;
            DECLARE $topic_id AS String;
            DECLARE $mode AS String;
            UPSERT INTO {self.table_name} (user_id, topic_id, mode)
            VALUES ($user_id, $topic_id, $mode);
            """
            
            self.ydb_client._execute_query(query, {
                "$user_id": str(user_id),
                "$topic_id": str(topic_id),
                "$mode": mode,
            })
            
            logger.debug(
                "Установлен режим для user_id=%s: %s",
                user_id,
                mode,
            )
        except Exception as e:
            logger.error(
                "Ошибка при установке режима для user_id=%s: %s",
                user_id,
                str(e),
            )
            raise

    def get_mode(self, user_id: int) -> str:
        """
        Получает режим работы для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Режим работы ("auto" или "manual"). По умолчанию "auto", если поле не установлено.
        """
        try:
            query = f"""
            DECLARE $user_id AS String;
            SELECT mode FROM {self.table_name} WHERE user_id = $user_id;
            """
            
            result = self.ydb_client._execute_query(query, {"$user_id": str(user_id)})
            rows = result[0].rows
            
            if not rows or not rows[0].mode:
                return "auto"
            
            mode = rows[0].mode.decode() if isinstance(rows[0].mode, bytes) else rows[0].mode
            
            # Возвращаем режим или "auto" по умолчанию
            return mode if mode in ("auto", "manual") else "auto"
        except Exception as e:
            logger.error(
                "Ошибка при получении режима для user_id=%s: %s",
                user_id,
                str(e),
            )
            # В случае ошибки возвращаем "auto" по умолчанию
            return "auto"

