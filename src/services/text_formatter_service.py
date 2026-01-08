"""
Сервис для форматирования текста ответов агента
Объединяет все операции нормализации и форматирования в одном месте
"""
from typing import Optional, List, Any
from datetime import datetime
from .date_normalizer import normalize_dates_in_text
from .time_normalizer import normalize_times_in_text
from .link_converter import convert_markdown_links_in_text
from .text_formatter import convert_bold_markdown_to_html
from .id_cleaner import remove_id_brackets_from_text


class TextFormatterService:
    """Сервис для форматирования текста ответов агента"""
    
    @staticmethod
    def format_agent_response(
        text: str,
        is_first_message: Optional[bool] = None,
        messages: Optional[List[Any]] = None,
        current_datetime: Optional[datetime] = None
    ) -> str:
        """
        Форматирует текст ответа агента, применяя все необходимые нормализации
        
        Args:
            text: Исходный текст ответа
            is_first_message: Флаг первого сообщения (для добавления приветствия)
            messages: Список сообщений из истории для проверки первого сообщения в день
            current_datetime: Текущая дата и время (для проверки первого сообщения в день)
            
        Returns:
            Отформатированный текст
        """
        if not text:
            return text
        
        # Нормализуем даты и время
        text = normalize_dates_in_text(text)
        text = normalize_times_in_text(text)
        
        # Преобразуем Markdown ссылки [текст](ссылка) в HTML-гиперссылки
        text = convert_markdown_links_in_text(text)
        
        # Заменяем Markdown жирный текст (**текст**) на HTML теги (<b>текст</b>)
        text = convert_bold_markdown_to_html(text)
        
        # Удаляем ID в скобках из сообщения
        text = remove_id_brackets_from_text(text)
        
        return text
    
    @staticmethod
    def format_manager_alert(text: str) -> str:
        """
        Форматирует текст уведомления менеджера
        
        Args:
            text: Исходный текст уведомления
            
        Returns:
            Отформатированный текст
        """
        if not text:
            return text
        
        # Нормализуем даты и время
        text = normalize_dates_in_text(text)
        text = normalize_times_in_text(text)
        
        # Преобразуем Markdown ссылки [текст](ссылка) в HTML-гиперссылки
        text = convert_markdown_links_in_text(text)
        
        # Заменяем Markdown жирный текст на HTML теги
        text = convert_bold_markdown_to_html(text)
        
        # Удаляем ID в скобках из уведомления
        text = remove_id_brackets_from_text(text)
        
        return text


def format_agent_response(
    text: str, 
    is_first_message: Optional[bool] = None,
    messages: Optional[List[Any]] = None,
    current_datetime: Optional[datetime] = None
) -> str:
    """Удобная функция для форматирования ответа агента"""
    return TextFormatterService.format_agent_response(text, is_first_message, messages, current_datetime)


def format_manager_alert(text: str) -> str:
    """Удобная функция для форматирования уведомления менеджера"""
    return TextFormatterService.format_manager_alert(text)

