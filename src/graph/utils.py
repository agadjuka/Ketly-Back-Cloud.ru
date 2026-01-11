"""
Утилиты для работы с графами
"""
import json
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage


def dicts_to_messages(messages_dicts: List[Dict[str, Any]]) -> List[BaseMessage]:
    """
    Преобразует словари сообщений из orchestrator в объекты BaseMessage для LangGraph
    
    Args:
        messages_dicts: Список словарей с полями role, content, tool_calls, tool_call_id
        
    Returns:
        Список объектов BaseMessage
    """
    langgraph_messages = []
    
    for msg in messages_dicts:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if role == "user":
            langgraph_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            ai_msg = AIMessage(content=content)
            if msg.get("tool_calls"):
                tool_calls = []
                for tc in msg.get("tool_calls", []):
                    if isinstance(tc, dict):
                        func_dict = tc.get("function", {})
                        func_name = func_dict.get("name", "")
                        func_args_str = func_dict.get("arguments", "{}")
                        try:
                            func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
                        except json.JSONDecodeError:
                            func_args = {}
                        tool_calls.append({
                            "name": func_name,
                            "args": func_args,
                            "id": tc.get("id", ""),
                        })
                    else:
                        tool_calls.append(tc)
                ai_msg.tool_calls = tool_calls
            langgraph_messages.append(ai_msg)
        elif role == "tool":
            langgraph_messages.append(ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", "")
            ))
        elif role == "system":
            langgraph_messages.append(SystemMessage(content=content))
    
    return langgraph_messages


def messages_to_history(messages: List[BaseMessage | Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Преобразует список BaseMessage объектов или словарей в список словарей для обратной совместимости.
    Сохраняет все типы сообщений, включая ToolMessage с tool_call_id.
    """
    if not messages:
        return []
    
    history = []
    for msg in messages:
        if isinstance(msg, dict):
            msg_dict = {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                msg_dict["tool_call_id"] = msg.get("tool_call_id")
            history.append(msg_dict)
        else:
            role_map = {"ai": "assistant", "system": "system", "tool": "tool", "human": "user"}
            role = role_map.get(getattr(msg, "type", "human"), "user")
            msg_dict = {"role": role, "content": getattr(msg, "content", "")}
            if role == "tool" and hasattr(msg, "tool_call_id"):
                msg_dict["tool_call_id"] = getattr(msg, "tool_call_id", "")
            history.append(msg_dict)
    return history


def filter_history_for_stage_detector(history: List[Dict[str, Any]], max_messages: int = 10) -> List[Dict[str, Any]]:
    """
    Фильтрует историю для StageDetector:
    - Удаляет сообщения с role: "tool" (кроме CallManager)
    - Ограничивает до последних max_messages сообщений
    
    Args:
        history: История сообщений в формате словарей
        max_messages: Максимальное количество сообщений (по умолчанию 10)
        
    Returns:
        Отфильтрованная и ограниченная история
    """
    if not history:
        return []
    
    # Берем последние max_messages сообщений
    recent_history = history[-max_messages:] if len(history) > max_messages else history
    
    # Фильтруем сообщения с role: "tool"
    filtered_history = []
    for msg in recent_history:
        role = msg.get("role", "user")
        # Пропускаем tool сообщения
        if role == "tool":
            continue
        filtered_history.append(msg)
    
    return filtered_history


def get_agent_history(state: Dict[str, Any], agent_name: str) -> List[BaseMessage | Dict[str, Any]]:
    """
    Получает историю для конкретного агента.
    
    Правила:
    - admin и demo_setup агенты используют общую историю messages
    - demo агент использует изолированную историю demo_messages
    
    Args:
        state: Состояние графа ConversationState
        agent_name: Имя агента ("AdminAgent", "DemoAgent", "DemoSetupAgent")
        
    Returns:
        История сообщений для агента
    """
    # admin и demo_setup используют общую историю
    if agent_name == "DemoSetupAgent" or agent_name == "AdminAgent":
        return state.get("messages", [])
    
    # demo использует изолированную историю
    if agent_name == "DemoAgent":
        return state.get("demo_messages", [])
    
    # По умолчанию возвращаем общую историю
    return state.get("messages", [])