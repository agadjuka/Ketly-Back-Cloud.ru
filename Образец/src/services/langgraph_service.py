"""
Сервис для работы с LangGraph (Responses API)
"""
from typing import Optional
from .responses_api.config import ResponsesAPIConfig


class LangGraphService:
    """Сервис для работы с LangGraph (Responses API)"""
    
    def __init__(self, config: Optional[ResponsesAPIConfig] = None):
        """
        Инициализация сервиса
        
        Args:
            config: Конфигурация Responses API (если None, создаётся новая)
        """
        # Используем общую конфигурацию для избежания дублирования
        self.config = config or ResponsesAPIConfig()
        self.folder_id = self.config.folder_id
        self.api_key = self.config.api_key
