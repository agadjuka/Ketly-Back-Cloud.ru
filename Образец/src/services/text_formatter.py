import re


class TextFormatter:
    """Сервис для форматирования текста: замена Markdown на HTML"""
    
    @staticmethod
    def convert_bold_markdown_to_html(text: str) -> str:
        """
        Заменяет Markdown жирный текст (**текст**) на HTML теги (<b>текст</b>)
        
        Args:
            text: Текст с Markdown форматированием
            
        Returns:
            Текст с HTML тегами вместо Markdown
        """
        if not text:
            return text
        
        # Паттерн для поиска **текст** (жирный текст в Markdown)
        # Используем non-greedy match, чтобы не захватывать лишние звездочки
        pattern = r'\*\*(.+?)\*\*'
        
        def replace_bold(match):
            # Извлекаем текст между звездочками
            content = match.group(1)
            # Заменяем на HTML тег <b>
            return f'<b>{content}</b>'
        
        result = re.sub(pattern, replace_bold, text)
        
        return result


def convert_bold_markdown_to_html(text: str) -> str:
    """
    Удобная функция для замены Markdown жирного текста на HTML теги
    
    Args:
        text: Текст с Markdown форматированием
    
    Returns:
        Текст с HTML тегами вместо Markdown
    """
    return TextFormatter.convert_bold_markdown_to_html(text)

