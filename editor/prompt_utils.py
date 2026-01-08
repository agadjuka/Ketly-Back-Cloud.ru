"""
Вспомогательные функции для работы с промптами.
"""

import re
from pathlib import Path


def extract_prompt(content: str) -> str:
    """
    Извлекает промпт из содержимого файла.
    
    Args:
        content: Содержимое файла
    
    Returns:
        Извлеченный промпт или пустая строка
    """
    # Ищем в __init__ методе
    pattern = r'def __init__\([^)]*\):.*?instruction\s*=\s*"""(.*?)"""'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Ищем просто instruction = """..."""
    pattern = r'instruction\s*=\s*"""(.*?)"""'
    matches = list(re.finditer(pattern, content, re.DOTALL))
    if matches:
        # Берем последнее вхождение (обычно это основной промпт)
        return matches[-1].group(1).strip()
    
    return ""


def update_prompt(content: str, new_prompt: str) -> str:
    """
    Обновляет промпт в содержимом файла.
    
    Args:
        content: Исходное содержимое файла
        new_prompt: Новый промпт
    
    Returns:
        Обновленное содержимое файла
    """
    # Пробуем найти в __init__
    pattern = r'(def __init__.*?instruction\s*=\s*""").*?(""")'
    replacement = rf'\1{new_prompt}\2'
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Если не нашли, пробуем найти просто instruction = """..."""
    if new_content == content:
        pattern = r'(instruction\s*=\s*""").*?(""")'
        replacement = rf'\1{new_prompt}\2'
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    return new_content


