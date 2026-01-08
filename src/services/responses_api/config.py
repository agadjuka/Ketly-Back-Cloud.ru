"""
Конфигурация для Responses API (OpenAI compatible)
"""
import os
from typing import Optional


class ResponsesAPIConfig:
    """Конфигурация для работы с OpenAI API (cloud.ru)"""
    
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.base_url = "https://foundation-models.api.cloud.ru/v1"
        self.model = "Qwen/Qwen3-235B-A22B-Instruct-2507"
        
        if not self.api_key:
            # Если API_KEY не задан, можно попробовать прочитать из старых переменных или оставить пустым
            # но лучше предупредить
            pass
        
        # Параметры модели по умолчанию
        self.max_tokens = 2500
        self.temperature = 0.1
        self.top_p = 0.95
        self.presence_penalty = 0
    
    @property
    def project(self) -> str:
        """Для совместимости, если где-то используется"""
        return "default"

