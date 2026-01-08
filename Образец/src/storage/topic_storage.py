"""Абстрактный базовый класс для хранения связей между пользователями и топиками."""

from abc import ABC, abstractmethod


class BaseTopicStorage(ABC):
    """Абстрактный класс для хранения связей между user_id и topic_id."""

    @abstractmethod
    def save_topic(self, user_id: int, topic_id: int, topic_name: str) -> None:
        """
        Сохраняет связь между пользователем и топиком.
        
        Args:
            user_id: ID пользователя Telegram
            topic_id: ID топика в Telegram Forum
            topic_name: Название топика
        """
        pass

    @abstractmethod
    def get_topic_id(self, user_id: int) -> int | None:
        """
        Получает ID топика по ID пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            ID топика или None, если связь не найдена
        """
        pass

    @abstractmethod
    def get_user_id(self, topic_id: int) -> int | None:
        """
        Получает ID пользователя по ID топика (обратная связь).
        
        Args:
            topic_id: ID топика в Telegram Forum
            
        Returns:
            ID пользователя или None, если связь не найдена
        """
        pass

    @abstractmethod
    def set_mode(self, user_id: int, mode: str) -> None:
        """
        Устанавливает режим работы для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            mode: Режим работы ("auto" или "manual")
        """
        pass

    @abstractmethod
    def get_mode(self, user_id: int) -> str:
        """
        Получает режим работы для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Режим работы ("auto" или "manual"). По умолчанию "auto", если поле не установлено.
        """
        pass


