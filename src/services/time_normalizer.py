import re
from typing import Optional


class TimeNormalizer:
    """Сервис для нормализации времени в тексте"""
    
    @staticmethod
    def normalize_times(text: str) -> str:
        """
        Нормализует все время в тексте в формат "HH:MM"
        
        Поддерживаемые форматы:
        - 9 : 00 -> 09:00
        - 12 : 30 -> 12:30
        - 9:00 -> 09:00
        - 12:30 -> 12:30
        - 9 :00 -> 09:00
        - 9: 00 -> 09:00
        """
        if not text:
            return text
        
        # Паттерн для времени с пробелами вокруг двоеточия или без них
        # Ищем: одна или две цифры, возможные пробелы, двоеточие, возможные пробелы, две цифры
        pattern = r'(\d{1,2})\s*:\s*(\d{2})'
        
        def format_time(match):
            hours = int(match.group(1))
            minutes = int(match.group(2))
            
            # Проверяем валидность времени
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                # Форматируем с ведущим нулем для часов
                return f"{hours:02d}:{minutes:02d}"
            # Если время невалидно, возвращаем исходное
            return match.group(0)
        
        result = re.sub(pattern, format_time, text)
        
        return result


def normalize_times_in_text(text: str) -> str:
    """
    Удобная функция для нормализации времени в тексте
    
    Args:
        text: Текст с временем
    
    Returns:
        Текст с нормализованным временем
    """
    return TimeNormalizer.normalize_times(text)

