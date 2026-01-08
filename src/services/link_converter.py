import re


class LinkConverter:
    """Сервис для преобразования ссылок yclients.com в HTML-гиперссылки"""
    
    @staticmethod
    def convert_yclients_links(text: str) -> str:
        """
        Преобразует ссылки yclients.com в HTML-гиперссылки с текстом "страница мастера"
        
        Поддерживает ссылки:
        - В скобках: (https://n1412149.yclients.com/...)
        - Без скобок: https://n1412149.yclients.com/...
        
        Args:
            text: Текст со ссылками
            
        Returns:
            Текст с преобразованными ссылками в HTML-формате
        """
        if not text:
            return text
        
        # Паттерн для поиска ссылок yclients.com
        # Ищем http/https ссылки, содержащие yclients.com
        # Может быть в скобках или без них
        # Простой паттерн без сложного lookbehind
        pattern = r'(\(?)(https?://[^\s\)<>]+yclients\.com[^\s\)<>]+)(\)?)'
        
        def replace_link(match):
            # Проверяем, не находимся ли мы уже внутри HTML-тега <a>
            start_pos = match.start()
            # Проверяем, есть ли перед этой позицией незакрытый тег <a href="
            text_before = text[:start_pos]
            # Считаем открывающие и закрывающие теги <a>
            open_tags = text_before.count('<a href="')
            close_tags = text_before.count('</a>')
            # Если есть незакрытый тег <a>, значит мы внутри уже обработанной ссылки
            if open_tags > close_tags:
                return match.group(0)  # Возвращаем исходный текст без изменений
            
            url = match.group(2)  # Извлекаем URL (группа 1 - открывающая скобка, группа 3 - закрывающая скобка)
            # Создаем HTML-гиперссылку (скобки не включаем в результат)
            return f'<a href="{url}">Страница мастера</a>'
        
        result = re.sub(pattern, replace_link, text)
        
        return result


def convert_yclients_links_in_text(text: str) -> str:
    """
    Удобная функция для преобразования ссылок yclients.com в HTML-гиперссылки
    
    Args:
        text: Текст со ссылками
        
    Returns:
        Текст с преобразованными ссылками в HTML-формате
    """
    return LinkConverter.convert_yclients_links(text)


def convert_markdown_links_in_text(text: str) -> str:
    """
    Преобразует Markdown ссылки [текст](url) в HTML-гиперссылки <a href="url">текст</a>
    
    Args:
        text: Текст с Markdown ссылками
        
    Returns:
        Текст с преобразованными ссылками в HTML-формате
    """
    if not text:
        return text
    
    # Паттерн для поиска Markdown ссылок [текст](url)
    # Поддерживает ссылки с пробелами и специальными символами в тексте
    pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    
    def replace_markdown_link(match):
        link_text = match.group(1)  # Текст ссылки
        url = match.group(2)  # URL
        # Создаем HTML-гиперссылку
        return f'<a href="{url}">{link_text}</a>'
    
    result = re.sub(pattern, replace_markdown_link, text)
    return result

