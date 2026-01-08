"""
Модели для API endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Модель запроса для /chat endpoint"""
    message: str = Field(..., description="Текст сообщения пользователя")
    thread_id: str = Field(..., description="UUID сессии с фронтенда")
    language: Optional[str] = Field(None, description="Язык интерфейса (игнорируется)")
    
    class Config:
        # Игнорируем дополнительные поля, которые могут прийти от фронтенда
        extra = "ignore"


class WebChatResponse(BaseModel):
    """Модель ответа для /chat endpoint"""
    response: str = Field(..., description="Текст ответа от AI-агента")









