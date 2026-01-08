"""
Сервис для удаления ID в скобках из текста сообщений
"""
import re


class IdCleaner:
    """Сервис для очистки текста от ID в скобках"""
    
    # Компилируем паттерн один раз для производительности
    # Ищем ID в любых скобках: (ID: 12345), [ID: 12345], {ID: 12345}
    # Поддерживает форматы: (ID: 12345), (ID 12345), (ID12345)
    _ID_PATTERN = re.compile(
        r'[\(\[\{]ID\s*:?\s*\d{5,10}[\)\]\}]',
        flags=re.IGNORECASE
    )
    
    @staticmethod
    def remove_id_brackets(text: str) -> str:
        """
        Удаляет скобки с ID из текста.
        
        Ищет скобки (круглые, квадратные или фигурные), внутри которых есть:
        - Текст "ID" (регистронезависимо)
        - Набор цифр (5-10 цифр)
        
        Поддерживаемые форматы:
        - (ID: 3409600), (ID 16699751), (ID3409600)
        - [ID: 3409600], [ID 16699751], [ID3409600]
        - {ID: 3409600}, {ID 16699751}, {ID3409600}
        
        Args:
            text: Текст с ID в скобках
            
        Returns:
            Текст без скобок с ID
        """
        if not text:
            return text
        
        # Удаляем все ID в скобках
        result = IdCleaner._ID_PATTERN.sub('', text)
        
        # Очищаем лишние пробелы, сохраняя переносы строк
        # Заменяем множественные пробелы/табы на один пробел
        result = re.sub(r'[ \t]+', ' ', result)
        # Удаляем пробелы перед и после переносов строк
        result = re.sub(r' +\n', '\n', result)
        result = re.sub(r'\n +', '\n', result)
        
        return result.strip()


def remove_id_brackets_from_text(text: str) -> str:
    """
    Удаляет ID в скобках из текста
    
    Args:
        text: Текст с ID в скобках
    
    Returns:
        Текст без скобок с ID
    """
    return IdCleaner.remove_id_brackets(text)

