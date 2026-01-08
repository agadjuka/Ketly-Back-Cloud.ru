"""
Утилиты для работы с /chat endpoint
"""
from types import SimpleNamespace
from typing import Any


def create_virtual_user(thread_id: str) -> Any:
    """
    Создает виртуальный User объект из thread_id для совместимости с админ-панелью.

    ВАЖНО:
    - В качестве id пользователя используется сам thread_id (строка UUID).
    - Это гарантирует, что во всех местах (история сообщений, админ-панель, PostgreSQL)
      используется один и тот же стабильный идентификатор сессии.
    """

    # Создаем виртуальный User объект с необходимыми атрибутами
    # Используем thread_id напрямую как идентификатор "пользователя"
    user = SimpleNamespace(
        id=thread_id,
        is_bot=False,
        first_name=f"Web User {thread_id[:8]}",
        last_name=None,
        username=None,
        full_name=f"Web User {thread_id[:8]}",
    )
    
    return user


def create_virtual_message(text: str, user: Any) -> Any:
    """
    Создает виртуальное Message объект для отправки в админ-панель.
    
    Args:
        text: Текст сообщения
        user: Виртуальный User объект
        
    Returns:
        Виртуальный Message объект (SimpleNamespace с атрибутами Message)
    """
    # Создаем виртуальный Message объект с необходимыми атрибутами
    message = SimpleNamespace(
        message_id=0,
        date=None,
        chat=SimpleNamespace(id=0),  # Фиктивный chat объект
        from_user=user,
        text=text,
        caption=None,
    )
    
    return message



