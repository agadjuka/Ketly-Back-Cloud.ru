"""
Класс Thread для работы с историей диалога
"""
from typing import List, Dict, Any, Optional, Iterator


class ThreadMessage:
    """Класс для представления сообщения в Thread"""
    
    def __init__(self, role: str, content: str):
        """
        Args:
            role: Роль сообщения (user, assistant, system, tool)
            content: Содержимое сообщения
        """
        self.role = role
        self.content = content
        self.text = content
        
        # Создаем объект author для совместимости
        class Author:
            def __init__(self, role: str):
                self.role = role.upper()
        
        self.author = Author(role)
        self.author_role = role
        self.parts = [{"text": content}] if content else []


class Thread:
    """
    Класс для работы с историей диалога
    """
    
    def __init__(
        self,
        thread_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Инициализация Thread
        
        Args:
            thread_id: ID потока диалога
            chat_id: ID чата (например, Telegram chat_id)
            messages: Список сообщений в формате [{"role": "user|assistant", "content": "..."}]
        """
        self.id = thread_id
        self.chat_id = chat_id
        self._messages: List[ThreadMessage] = []
        
        # Преобразуем сообщения в ThreadMessage
        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    self._messages.append(ThreadMessage(role, content))
                elif isinstance(msg, ThreadMessage):
                    self._messages.append(msg)
    
    def __iter__(self) -> Iterator[ThreadMessage]:
        """Итерация по сообщениям Thread"""
        return iter(self._messages)
    
    def add_message(self, role: str, content: str):
        """Добавить сообщение в Thread"""
        self._messages.append(ThreadMessage(role, content))
    
    def get_messages(self) -> List[ThreadMessage]:
        """Получить все сообщения"""
        return self._messages.copy()
    
    def get_last_messages(self, count: int = 3) -> List[ThreadMessage]:
        """Получить последние N сообщений"""
        return self._messages[-count:] if len(self._messages) > count else self._messages

