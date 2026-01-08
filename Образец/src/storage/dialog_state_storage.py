"""Реализация хранилища состояний диалогов на базе YDB."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DialogStateStorage:
    """
    Реализация хранилища состояний диалогов на базе YDB.
    
    Структура хранения:
    - Таблица: dialog_states
    - Поля: chat_id (String, Primary Key), current_stage (String)
    """

    def __init__(
        self,
        ydb_client=None,
        table_name: Optional[str] = None,
    ):
        """
        Инициализирует хранилище состояний диалогов в YDB.
        
        Args:
            ydb_client: Экземпляр YDBClient (если None, будет получен при первом использовании)
            table_name: Название таблицы (если None, используется "dialog_states")
        """
        from src.config.admin_config import get_dialog_states_table
        
        self.table_name = table_name or get_dialog_states_table()
        self._ydb_client = ydb_client
        
        logger.debug(
            "Инициализирован DialogStateStorage (table=%s)",
            self.table_name,
        )

    @property
    def ydb_client(self):
        """Получает или создает экземпляр YDBClient."""
        if self._ydb_client is None:
            from src.ydb_client import get_ydb_client
            self._ydb_client = get_ydb_client()
        return self._ydb_client

    def get_stage(self, chat_id: str) -> Optional[str]:
        """
        Получает текущую стадию диалога по chat_id.
        
        Args:
            chat_id: ID чата (может быть user_id или thread_id)
            
        Returns:
            Текущая стадия диалога (например, "admin", "demo") или None, если запись не найдена.
            None означает, что стадия по умолчанию - "admin".
        """
        try:
            query = f"""
            DECLARE $chat_id AS String;
            SELECT current_stage FROM {self.table_name} WHERE chat_id = $chat_id;
            """
            
            result = self.ydb_client._execute_query(query, {"$chat_id": str(chat_id)})
            rows = result[0].rows
            
            if not rows or not rows[0].current_stage:
                logger.debug(
                    "Стадия для chat_id=%s не найдена, возвращаю None (по умолчанию admin)",
                    chat_id,
                )
                return None
            
            stage = rows[0].current_stage.decode() if isinstance(rows[0].current_stage, bytes) else rows[0].current_stage
            
            logger.debug(
                "Получена стадия для chat_id=%s: %s",
                chat_id,
                stage,
            )
            return stage
        except Exception as e:
            logger.error(
                "Ошибка при получении стадии для chat_id=%s: %s",
                chat_id,
                str(e),
            )
            # В случае ошибки возвращаем None (по умолчанию "admin")
            return None

    def set_stage(self, chat_id: str, stage: str) -> None:
        """
        Устанавливает текущую стадию диалога для chat_id.
        
        Args:
            chat_id: ID чата (может быть user_id или thread_id)
            stage: Стадия диалога (например, "admin", "demo", "demo_setup")
        """
        try:
            query = f"""
            DECLARE $chat_id AS String;
            DECLARE $current_stage AS String;
            UPSERT INTO {self.table_name} (chat_id, current_stage)
            VALUES ($chat_id, $current_stage);
            """
            
            self.ydb_client._execute_query(query, {
                "$chat_id": str(chat_id),
                "$current_stage": stage,
            })
            
            logger.debug(
                "Установлена стадия для chat_id=%s: %s",
                chat_id,
                stage,
            )
        except Exception as e:
            logger.error(
                "Ошибка при установке стадии для chat_id=%s: %s",
                chat_id,
                str(e),
            )
            raise


