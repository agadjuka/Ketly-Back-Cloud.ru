import re
from datetime import datetime
from typing import Optional


class DateNormalizer:
    """Сервис для нормализации дат в тексте"""
    
    # Названия месяцев в родительном падеже
    MONTHS_RU = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    
    @staticmethod
    def normalize_dates(text: str) -> str:
        """
        Нормализует все даты в тексте в формат "DD месяца"
        
        Поддерживаемые форматы:
        - YYYY-MM-DD (2025-11-08)
        - YYYY‑MM‑DD (с длинным дефисом)
        - DD.MM.YYYY (08.11.2025)
        - DD/MM/YYYY (08/11/2025)
        """
        if not text:
            return text
        
        # Паттерны для различных форматов дат
        # Поддерживаем различные типы дефисов: обычный (-), длинный (‑), en-dash (–), em-dash (—)
        patterns = [
            # YYYY-MM-DD или YYYY‑MM‑DD (с различными типами дефисов)
            (r'(\d{4})[\u002D\u2010\u2011\u2013\u2014\-](\d{1,2})[\u002D\u2010\u2011\u2013\u2014\-](\d{1,2})', lambda m: DateNormalizer._format_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
            # DD.MM.YYYY
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', lambda m: DateNormalizer._format_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))),
            # DD/MM/YYYY
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: DateNormalizer._format_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))),
            # YYYY.MM.DD
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', lambda m: DateNormalizer._format_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        ]
        
        result = text
        for pattern, formatter in patterns:
            def safe_formatter(match):
                formatted = formatter(match)
                return formatted if formatted is not None else match.group(0)
            result = re.sub(pattern, safe_formatter, result)
        
        return result
    
    @staticmethod
    def _format_date(year: int, month: int, day: int) -> Optional[str]:
        """
        Форматирует дату в формат "DD месяца"
        
        Args:
            year: Год
            month: Месяц (1-12)
            day: День (1-31)
        
        Returns:
            Отформатированная дата или None, если дата невалидна
        """
        try:
            # Проверяем валидность даты
            datetime(year, month, day)
            
            # Форматируем в "DD месяца"
            month_name = DateNormalizer.MONTHS_RU.get(month)
            if month_name:
                return f"{day:02d} {month_name}"
            return None
        except ValueError:
            # Некорректная дата, возвращаем None (не заменяем)
            return None


def normalize_dates_in_text(text: str) -> str:
    """
    Удобная функция для нормализации дат в тексте
    
    Args:
        text: Текст с датами
    
    Returns:
        Текст с нормализованными датами
    """
    return DateNormalizer.normalize_dates(text)

