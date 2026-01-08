"""Фабрика для создания экземпляра хранилища состояний диалогов."""

import logging

from src.storage.dialog_state_storage import DialogStateStorage

logger = logging.getLogger(__name__)

# Глобальный экземпляр хранилища
_dialog_state_storage: DialogStateStorage | None = None


def get_dialog_state_storage() -> DialogStateStorage:
    """
    Получает или создает экземпляр хранилища состояний диалогов.
    
    Returns:
        Экземпляр хранилища состояний диалогов (DialogStateStorage)
    """
    global _dialog_state_storage
    
    if _dialog_state_storage is None:
        try:
            _dialog_state_storage = DialogStateStorage()
            logger.info("Инициализирован DialogStateStorage")
        except ValueError as e:
            logger.error(
                "Не удалось инициализировать DialogStateStorage: %s. "
                "Убедитесь, что YDB настроен правильно.",
                str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Ошибка при инициализации хранилища состояний диалогов: %s",
                str(e),
            )
            raise
    
    return _dialog_state_storage


