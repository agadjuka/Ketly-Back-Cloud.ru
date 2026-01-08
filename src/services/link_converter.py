import re


class LinkConverter:
    """Сервис для преобразования ссылок в HTML-гиперссылки"""
    
    @staticmethod
    def convert_markdown_links_to_html(text: str) -> str:
        """
        Преобразует Markdown ссылки [текст](ссылка) в HTML-гиперссылки <a href="ссылка">текст</a>
        
        Поддерживает формат:
        - [текст](https://example.com)
        - [Instagram](https://www.instagram.com/...)
        
        Args:
            text: Текст с Markdown ссылками
            
        Returns:
            Текст с преобразованными ссылками в HTML-формате
        """
        if not text:
            return text
        
        # Паттерн для поиска Markdown ссылок: [текст](ссылка)
        # Используем non-greedy match для текста в квадратных скобках
        pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        
        def replace_markdown_link(match):
            link_text = match.group(1)  # Текст ссылки из квадратных скобок
            url = match.group(2)  # URL из круглых скобок
            
            # Проверяем, не находимся ли мы уже внутри HTML-тега <a>
            start_pos = match.start()
            text_before = text[:start_pos]
            open_tags = text_before.count('<a href="')
            close_tags = text_before.count('</a>')
            
            # Если уже внутри HTML-ссылки, возвращаем исходный текст
            if open_tags > close_tags:
                return match.group(0)
            
            # Создаем HTML-гиперссылку
            return f'<a href="{url}">{link_text}</a>'
        
        result = re.sub(pattern, replace_markdown_link, text)
        return result
    
    @staticmethod
    def convert_yclients_links(text: str) -> str:
        """
        ОТКЛЮЧЕНО: Преобразует ссылки yclients.com в HTML-гиперссылки с текстом "страница мастера"
        
        Эта функция отключена, так как теперь агент сам формирует ссылки в формате Markdown.
        Используйте convert_markdown_links_to_html для обработки ссылок.
        
        Args:
            text: Текст со ссылками
            
        Returns:
            Текст без изменений (функция отключена)
        """
        # Функция отключена - возвращаем текст без изменений
        return text


def convert_markdown_links_in_text(text: str) -> str:
    """
    Удобная функция для преобразования Markdown ссылок в HTML-гиперссылки
    
    Args:
        text: Текст с Markdown ссылками в формате [текст](ссылка)
        
    Returns:
        Текст с преобразованными ссылками в HTML-формате
    """
    return LinkConverter.convert_markdown_links_to_html(text)


def convert_yclients_links_in_text(text: str) -> str:
    """
    ОТКЛЮЧЕНО: Удобная функция для преобразования ссылок yclients.com в HTML-гиперссылки
    
    Эта функция отключена. Используйте convert_markdown_links_in_text для обработки ссылок.
    
    Args:
        text: Текст со ссылками
        
    Returns:
        Текст без изменений (функция отключена)
    """
    # Функция отключена - возвращаем текст без изменений
    return text
