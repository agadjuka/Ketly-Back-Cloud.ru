"""
Модуль для обработки приветствий в первом сообщении
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz


def has_greeting(text: str) -> bool:
    """
    Проверяет, содержит ли текст приветствие
    
    Args:
        text: Текст для проверки
        
    Returns:
        True, если текст содержит приветствие, False иначе
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    greetings = [
        "добрый день",
        "доброе утро",
        "добрый вечер",
        "здравствуйте",
        "здравствуй",
        "привет",
        "приветствую",
        "доброго времени суток",
        "доброго дня",
        "доброго утра",
        "доброго вечера"
    ]
    
    # Проверяем начало текста
    for greeting in greetings:
        if text_lower.startswith(greeting):
            return True
    
    # Проверяем первые 50 символов
    text_start = text_lower[:50]
    for greeting in greetings:
        if greeting in text_start:
            return True
    
    return False


def _parse_date_from_message(content: str) -> Optional[datetime]:
    """
    Парсит дату и время из сообщения пользователя в формате [Текущее время: YYYY-MM-DD HH:MM]
    
    Args:
        content: Содержимое сообщения
        
    Returns:
        datetime объект или None, если не удалось распарсить
    """
    if not content:
        return None
    
    # Ищем паттерн [Текущее время: YYYY-MM-DD HH:MM] (с учетом пробелов)
    pattern = r'\[Текущее время:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\]'
    match = re.search(pattern, content)
    
    if match:
        try:
            date_str = match.group(1)
            # Парсим дату в московском часовом поясе
            moscow_tz = pytz.timezone('Europe/Moscow')
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            # Применяем московский часовой пояс
            dt = moscow_tz.localize(dt)
            return dt
        except (ValueError, AttributeError):
            return None
    
    return None


def _get_current_moscow_datetime() -> datetime:
    """
    Получает текущую дату и время в московском часовом поясе
    
    Returns:
        datetime объект в московском часовом поясе
    """
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)


def _is_same_day_with_cutoff(dt1: datetime, dt2: datetime, cutoff_hour: int = 4) -> bool:
    """
    Проверяет, находятся ли две даты в одном дне с учетом отсечки.
    День считается с cutoff_hour (по умолчанию 4:00).
    
    Например, если cutoff_hour = 4:
    - 26.12.2025 03:00 и 26.12.2025 05:00 - разные дни (03:00 относится к предыдущему дню)
    - 26.12.2025 05:00 и 26.12.2025 23:00 - один день
    - 26.12.2025 23:00 и 27.12.2025 03:00 - один день (03:00 еще относится к 26.12)
    - 26.12.2025 23:00 и 27.12.2025 05:00 - разные дни
    
    Args:
        dt1: Первая дата
        dt2: Вторая дата
        cutoff_hour: Час отсечки (по умолчанию 4)
        
    Returns:
        True, если даты в одном дне с учетом отсечки, False иначе
    """
    # Убеждаемся, что обе даты в одном часовом поясе (московском)
    moscow_tz = pytz.timezone('Europe/Moscow')
    if dt1.tzinfo is None:
        dt1 = moscow_tz.localize(dt1)
    else:
        dt1 = dt1.astimezone(moscow_tz)
    
    if dt2.tzinfo is None:
        dt2 = moscow_tz.localize(dt2)
    else:
        dt2 = dt2.astimezone(moscow_tz)
    
    # Нормализуем даты: если время меньше cutoff_hour, относим к предыдущему дню
    def normalize_date(dt: datetime) -> datetime:
        if dt.hour < cutoff_hour:
            # Относим к предыдущему дню
            normalized = (dt.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1))
        else:
            # Относим к текущему дню
            normalized = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return normalized
    
    normalized_dt1 = normalize_date(dt1)
    normalized_dt2 = normalize_date(dt2)
    
    return normalized_dt1.date() == normalized_dt2.date()


def is_first_message_in_day(messages: List[Any], current_datetime: Optional[datetime] = None) -> bool:
    """
    Проверяет, является ли текущее сообщение первым сообщением пользователя в день.
    День считается с 4:00 утра.
    
    Args:
        messages: Список сообщений из истории (может быть List[BaseMessage] или List[Dict])
        current_datetime: Текущая дата и время (если None, берется текущее московское время)
        
    Returns:
        True, если это первое сообщение в день, False иначе
    """
    if current_datetime is None:
        current_datetime = _get_current_moscow_datetime()
    
    # Находим последнее сообщение пользователя (не текущее)
    last_user_message_dt = None
    
    # Проходим по сообщениям в обратном порядке, пропуская последнее (текущее)
    for msg in reversed(messages[:-1] if len(messages) > 1 else []):
        # Определяем тип сообщения
        if isinstance(msg, dict):
            msg_type = msg.get('type', '')
            content = msg.get('content', '')
        else:
            msg_type = getattr(msg, 'type', '')
            content = getattr(msg, 'content', '')
        
        # Ищем сообщения от пользователя
        if msg_type in ['human', 'user']:
            # Парсим дату из сообщения
            parsed_dt = _parse_date_from_message(content)
            if parsed_dt:
                last_user_message_dt = parsed_dt
                break
    
    # Если не нашли предыдущих сообщений пользователя, значит это первое сообщение в день
    if last_user_message_dt is None:
        return True
    
    # Проверяем, в одном ли дне (с учетом отсечки в 4 утра)
    return not _is_same_day_with_cutoff(last_user_message_dt, current_datetime, cutoff_hour=4)


def add_greeting_if_needed(
    text: str, 
    is_first_message: bool, 
    messages: Optional[List[Any]] = None,
    current_datetime: Optional[datetime] = None
) -> str:
    """
    Добавляет приветствие "Добрый день!" в начало текста, если:
    1. Это первое сообщение пользователя ИЛИ первое сообщение в день (с отсечкой в 4:00)
    2. В тексте еще нет приветствия
    
    Args:
        text: Текст сообщения от агента
        is_first_message: Флаг первого сообщения (вообще)
        messages: Список сообщений из истории для проверки первого сообщения в день
        current_datetime: Текущая дата и время (если None, берется текущее московское время)
        
    Returns:
        Текст с добавленным приветствием (если нужно) или исходный текст
    """
    if not text or not text.strip():
        return text
    
    # Проверяем, нужно ли добавлять приветствие
    should_add_greeting = False
    
    # Если это первое сообщение вообще
    if is_first_message:
        should_add_greeting = True
    # Или если это первое сообщение в день (с отсечкой в 4:00)
    elif messages is not None:
        is_first_in_day = is_first_message_in_day(messages, current_datetime)
        if is_first_in_day:
            should_add_greeting = True
    
    if not should_add_greeting:
        return text
    
    # Проверяем, нет ли уже приветствия в тексте
    if has_greeting(text):
        return text
    
    return f"Добрый день!\n\n{text}"

