"""
Состояние для основного графа диалога (Responses API)
"""
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from langgraph.graph.message import AnyMessage, add_messages


class ConversationState(TypedDict):
    """Состояние основного графа диалога"""
    messages: Annotated[list[AnyMessage], add_messages]  # История сообщений (управляется LangGraph через checkpointer)
    message: str                                          # Исходное сообщение пользователя (для обратной совместимости)
    chat_id: Optional[str]                                # ID чата в Telegram
    stage: Optional[str]                                  # Определённая стадия диалога
    extracted_info: Optional[dict]                       # Извлечённая информация
    answer: str                                           # Финальный ответ пользователю
    manager_alert: Optional[str]                         # Сообщение для менеджера (если нужно)
    agent_name: Optional[str]                            # Имя агента, который дал ответ
    used_tools: Optional[list]                           # Список использованных инструментов
    tool_results: Optional[List[Dict[str, Any]]]          # Полная информация о результатах инструментов
    demo_config: Optional[Dict[str, Any]]                 # Конфигурация демо-режима (niche, company_name, persona_instruction, welcome_message)
    demo_was_conducted: Optional[bool]                     # Флаг того, что демонстрация была проведена
    # Изолированная история для demo агента (admin и demo_setup используют общую историю messages)
    demo_messages: Annotated[list[AnyMessage], add_messages]   # История для demo агента

