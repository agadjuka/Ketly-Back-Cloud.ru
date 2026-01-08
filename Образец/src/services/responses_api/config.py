"""
Конфигурация для Responses API
"""
import os
from typing import Optional


class ResponsesAPIConfig:
    """Конфигурация для работы с Responses API"""
    
    def __init__(self):
        self.folder_id = os.getenv("YANDEX_FOLDER_ID")
        self.api_key = os.getenv("YANDEX_API_KEY_SECRET")
        
        if not self.folder_id or not self.api_key:
            raise ValueError("Не заданы YANDEX_FOLDER_ID или YANDEX_API_KEY_SECRET")
        
        self.base_url = "https://rest-assistant.api.cloud.yandex.net/v1"
        self.model_uri = os.getenv(
            "YANDEX_MODEL_URI",
            f"gpt://{self.folder_id}/yandexgpt/latest"
        )
        
        # Параметры модели по умолчанию
        self.max_output_tokens = int(os.getenv("YANDEX_MAX_OUTPUT_TOKENS", "800"))
        self.temperature = float(os.getenv("YANDEX_TEMPERATURE", "0.1"))
    
    @property
    def project(self) -> str:
        """ID папки для использования в качестве project"""
        return self.folder_id

