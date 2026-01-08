"""
Состояние для основного графа диалога (Responses API)
"""
from typing import TypedDict, Optional, List, Dict, Any


class ConversationState(TypedDict):
    """Состояние основного графа диалога"""
    message: str                                    # Исходное сообщение пользователя
    previous_response_id: Optional[str]             # ID предыдущего ответа для продолжения диалога
    chat_id: Optional[str]                         # ID чата в Telegram
    stage: Optional[str]                           # Определённая стадия диалога
    extracted_info: Optional[dict]                 # Извлечённая информация
    answer: str                                    # Финальный ответ пользователю
    manager_alert: Optional[str]                   # Сообщение для менеджера (если нужно)
    agent_name: Optional[str]                      # Имя агента, который дал ответ
    used_tools: Optional[list]                    # Список использованных инструментов
    response_id: Optional[str]                     # ID ответа для сохранения (для следующего запроса)

