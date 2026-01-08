"""
Orchestrator для обработки диалогов через OpenAI API
"""
import json
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from .client import ResponsesAPIClient
from .tools_registry import ResponsesToolsRegistry
from .config import ResponsesAPIConfig
from ..logger_service import logger

# Импортируем CallManagerException один раз, а не в цикле
try:
    from ...agents.tools.call_manager_tools import CallManagerException
except ImportError:
    CallManagerException = None


class ResponsesOrchestrator:
    """Orchestrator для обработки диалогов через OpenAI API"""
    
    def __init__(
        self,
        instructions: str,
        tools_registry: Optional[ResponsesToolsRegistry] = None,
        client: Optional[ResponsesAPIClient] = None,
        config: Optional[ResponsesAPIConfig] = None,
        agent_name: Optional[str] = None,
    ):
        """
        Инициализация orchestrator
        """
        self.instructions = instructions
        self.tools_registry = tools_registry or ResponsesToolsRegistry()
        self.config = config or ResponsesAPIConfig()
        self.client = client or ResponsesAPIClient(self.config)
        self.agent_name = agent_name
    
    def run_turn(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Один полный ход диалога
        """
        # Получаем схемы инструментов один раз
        tools_schemas = self.tools_registry.get_all_tools_schemas()
        
        # Формируем messages для первого запроса к API
        # История теперь приходит из LangGraph messages, которые уже нормализованы
        # ВАЖНО: Копируем ВСЕ типы сообщений (user, assistant, tool, system) для полного контекста
        messages = []
        if history:
            # Копируем ВСЮ историю без фильтрации по ролям
            # Это критично для видимости ToolMessage (результаты инструментов) и AIMessage (ответы бота)
            messages = [msg.copy() for msg in history]
        
        # Сохраняем количество сообщений из истории для определения новых сообщений
        # ВАЖНО: user_message НЕ включаем в new_messages, так как он уже есть в state["messages"]
        history_length = len(messages)
        
        # Добавляем текущее сообщение пользователя только если его еще нет в истории
        # Проверяем, не является ли последнее сообщение в истории уже текущим сообщением
        last_message_is_current = (
            messages and 
            messages[-1].get("role") == "user" and 
            messages[-1].get("content") == user_message
        )
        
        # Флаг: был ли добавлен user_message в этот вызов
        user_message_added = False
        if not last_message_is_current:
            messages.append({
                "role": "user",
                "content": user_message
            })
            user_message_added = True
        
        # Цикл для обработки множественных вызовов инструментов
        max_iterations = 10
        iteration = 0
        tool_calls_info = []
        reply_text = ""
        
        while iteration < max_iterations:
            iteration += 1
            
            # Обрезаем историю перед вызовом LLM (оставляем последние 10 сообщений)
            # Используем простую обрезку по количеству сообщений
            # ВАЖНО: Сохраняем CallManager только если он входит в последние 10 сообщений
            try:
                # Разделяем системные и несистемные сообщения
                system_msgs = [msg for msg in messages if msg.get("role") == "system"]
                non_system_msgs = [msg for msg in messages if msg.get("role") != "system"]
                
                # Берем последние 10 несистемных сообщений
                if len(non_system_msgs) > 10:
                    recent_non_system = non_system_msgs[-10:]
                else:
                    recent_non_system = non_system_msgs
                
                # Извлекаем CallManager сообщения только из последних 10
                call_manager_ids = set()
                for msg in recent_non_system:
                    role = msg.get("role")
                    tool_calls = msg.get("tool_calls", [])
                    
                    if role == "assistant" and tool_calls:
                        for tc in tool_calls:
                            if isinstance(tc, dict):
                                func_dict = tc.get("function", {})
                                tool_name = func_dict.get("name", "") if func_dict else tc.get("name", "")
                                call_id = tc.get("id", "")
                            else:
                                tool_name = getattr(tc, "name", "")
                                call_id = getattr(tc, "id", "")
                            
                            if tool_name == "CallManager" and call_id:
                                call_manager_ids.add(call_id)
                
                # Фильтруем: оставляем все сообщения из последних 10, включая CallManager
                # (CallManager уже входит в recent_non_system, если он там был)
                messages_to_send = system_msgs + recent_non_system
                
                # Специальная обработка для stage_detector: добавляем напоминание перед последним сообщением пользователя
                if self.agent_name == "Определитель стадий диалога":
                    # Находим последнее сообщение пользователя
                    last_user_idx = None
                    for i in range(len(messages_to_send) - 1, -1, -1):
                        if messages_to_send[i].get("role") == "user":
                            last_user_idx = i
                            break
                    
                    # Если нашли последнее user сообщение, вставляем напоминание перед ним
                    if last_user_idx is not None:
                        reminder = {
                            "role": "system",
                            "content": "STOP. The following message is the client's last message. You MUST NOT respond to it. Your ONLY task is to analyze it and return ONLY the stage name (one word) from the agent list above. Do not write any other text, do not answer the client's question."
                        }
                        messages_to_send.insert(last_user_idx, reminder)
                
            except Exception as e:
                logger.warning(f"Ошибка при обрезке истории: {e}, используем оригинальные сообщения")
                messages_to_send = messages
            
            # Запрос к модели
            try:
                response = self.client.create_response(
                    instructions=self.instructions,
                    input_messages=messages_to_send,  # Передаем обрезанные сообщения
                    tools=tools_schemas if tools_schemas else None,
                    agent_name=self.agent_name,
                )
            except Exception as e:
                logger.error(f"Ошибка при запросе к API на итерации {iteration}: {e}", exc_info=True)
                # Если это первая итерация и произошла ошибка, возвращаем сообщение об ошибке
                if iteration == 1:
                    error_message = "Извините, произошла техническая ошибка. Пожалуйста, попробуйте еще раз через несколько секунд."
                    # При ошибке новых сообщений нет (исключаем user_message, так как он уже есть в state["messages"])
                    # Если user_message был добавлен, начинаем с history_length + 1, иначе с history_length
                    start_index = history_length + 1 if user_message_added else history_length
                    new_messages = messages[start_index:] if len(messages) > start_index else []
                    return {
                        "reply": error_message,
                        "tool_calls": tool_calls_info,
                        "raw_response": None,
                        "new_messages": new_messages,  # КРИТИЧНО: Все новые сообщения
                    }
                break
            
            message = response.choices[0].message
            
            # Добавляем ответ ассистента в историю сообщений
            # Важно: правильно сериализуем tool_calls из объекта SDK в словари
            assistant_msg = {
                "role": "assistant",
                "content": message.content or ""  # content должен быть строкой, не None
            }
            
            # Правильно сериализуем tool_calls из объекта SDK в формат словарей
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            messages.append(assistant_msg)
            
            # Проверяем tool_calls
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    call_id = tool_call.id
                    args_json = tool_call.function.arguments
                    
                    try:
                        args = json.loads(args_json)
                    except json.JSONDecodeError:
                        logger.error(f"Ошибка парсинга аргументов для {func_name}: {args_json}")
                        args = {}
                    
                    logger.info(f"🔧 Использован инструмент: {func_name}")
                    logger.info(f"📋 Аргументы: {json.dumps(args, ensure_ascii=False, indent=2)}")
                    
                    try:
                        result = self.tools_registry.call_tool(func_name, args, conversation_history=None, chat_id=chat_id)
                        
                        tool_call_info = {
                            "name": func_name,
                            "call_id": call_id,
                            "args": args,
                            "result": result,
                        }
                        tool_calls_info.append(tool_call_info)
                        
                        # Добавляем результат в сообщения
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                        })
                        
                    except Exception as e:
                        # Проверяем CallManager
                        if CallManagerException and isinstance(e, CallManagerException):
                            escalation_result = e.escalation_result
                            logger.info(f"CallManager вызван через инструмент {func_name}")
                            
                            # ВАЖНО: Добавляем ToolMessage с результатом CallManager в messages
                            # Это нужно для сохранения в истории LangGraph
                            call_manager_tool_message = {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "content": json.dumps({
                                    "call_manager": True,
                                    "reason": args.get("reason", ""),
                                    "manager_alert": escalation_result.get("manager_alert", "")
                                }, ensure_ascii=False)
                            }
                            messages.append(call_manager_tool_message)
                            
                            # Извлекаем новые сообщения (включая AIMessage с tool_calls и ToolMessage)
                            # Исключаем user_message, так как он уже есть в state["messages"]
                            # Если user_message был добавлен, начинаем с history_length + 1, иначе с history_length
                            start_index = history_length + 1 if user_message_added else history_length
                            new_messages = messages[start_index:] if len(messages) > start_index else []
                            return {
                                "reply": escalation_result.get("user_message"),
                                "tool_calls": tool_calls_info,
                                "call_manager": True,
                                "manager_alert": escalation_result.get("manager_alert"),
                                "new_messages": new_messages,  # КРИТИЧНО: Все новые сообщения (AIMessage + ToolMessage)
                            }
                        
                        logger.error(f"Ошибка при вызове инструмента {func_name}: {e}", exc_info=True)
                        error_result = f"Ошибка при выполнении инструмента: {str(e)}"
                        
                        tool_call_info = {
                            "name": func_name,
                            "call_id": call_id,
                            "args": args,
                            "result": error_result,
                        }
                        tool_calls_info.append(tool_call_info)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": error_result
                        })
                
                # Продолжаем цикл, чтобы модель могла ответить на результаты инструментов
                continue
            
            # Если нет tool_calls, значит это финальный ответ
            if message.content:
                reply_text = message.content
                logger.info(f"Получен текстовый ответ на итерации {iteration} (длина: {len(reply_text)})")
                break
            else:
                logger.warning(f"Пустой ответ от модели на итерации {iteration}")
                break
        
        if iteration >= max_iterations:
            logger.warning(f"Достигнут лимит итераций ({max_iterations}). Прекращаем цикл.")
        
        # Если ответ пустой, возвращаем сообщение об ошибке
        if not reply_text or not reply_text.strip():
            logger.warning("Получен пустой ответ от API")
            reply_text = "Извините, не удалось получить ответ. Пожалуйста, попробуйте еще раз."
        
        # КРИТИЧНО: Извлекаем только НОВЫЕ сообщения (те, что были добавлены в ходе этого вызова)
        # Это все сообщения после истории (исключаем user_message, так как он уже есть в state["messages"])
        # Если user_message был добавлен в этот вызов, начинаем с history_length + 1, иначе с history_length
        start_index = history_length + 1 if user_message_added else history_length
        new_messages = messages[start_index:] if len(messages) > start_index else []
        
        return {
            "reply": reply_text,
            "tool_calls": tool_calls_info,
            "raw_response": response if 'response' in locals() else None,
            "new_messages": new_messages,  # КРИТИЧНО: Все новые сообщения (AIMessage с tool_calls и ToolMessage)
        }
