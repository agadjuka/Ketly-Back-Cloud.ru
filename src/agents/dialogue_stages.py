"""
Определение стадий диалога
Соответствует стадиям из dialogue_patterns.json
"""
from enum import Enum


class DialogueStage(str, Enum):
    """Стадии диалога"""
    ADMIN = "admin"                            # Административные функции
    DEMO = "demo"                              # Демонстрационные функции
    DEMO_SETUP = "demo_setup"                  # Настройка демонстрации