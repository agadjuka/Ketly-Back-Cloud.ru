"""
Базовый класс для агентов (Responses API)
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from ..graph.utils import dicts_to_messages
from ..services.responses_api.orchestrator import ResponsesOrchestrator
from ..services.responses_api.tools_registry import ResponsesToolsRegistry
from ..services.logger_service import logger
from ..services.tool_history_service import get_tool_history_service


class BaseAgent:
    """Базовый класс для всех агентов (использует Responses API)"""
    
    def __init__(
        self,
        langgraph_service,
        instruction: str,
        tools: list = None,
        agent_name: str = None
    ):
        self.langgraph_service = langgraph_service
        self.instruction = instruction
        self.agent_name = agent_name or self.__class__.__name__
        
        # Сохраняем классы инструментов для вызова
        if tools:
            self.tools = {x.__name__: x for x in tools}
        else:
            self.tools = {}
        
        # Создаём регистрацию инструментов
        tools_registry = ResponsesToolsRegistry()
        if tools:
            tools_registry.register_tools_from_list(tools)
        
        # Используем конфигурацию из langgraph_service для избежания дублирования
        from ..services.responses_api.config import ResponsesAPIConfig
        config = langgraph_service.config if hasattr(langgraph_service, 'config') else ResponsesAPIConfig()
        
        # Создаём orchestrator с общей конфигурацией
        self.orchestrator = ResponsesOrchestrator(
            instructions=instruction,
            tools_registry=tools_registry,
            config=config,
            agent_name=self.agent_name,
        )
        
        # Инициализируем список для отслеживания tool_calls
        self._last_tool_calls = []
        
        # Результат CallManager (если был вызван)
        self._call_manager_result = None
        
        # Сохраняем оригинальную инструкцию для восстановления
        self._original_instruction = instruction
    
    def run(self, message: str, history: Optional[List[Dict[str, Any]]] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Выполнение запроса к агенту (нативный метод для LangGraph)
        
        Возвращает словарь с результатами, включая все сгенерированные сообщения.
        Это позволяет LangGraph автоматически добавить их в состояние через add_messages.
        
        Args:
            message: Сообщение для агента
            history: История сообщений (преобразованная из LangGraph messages)
            chat_id: ID чата в Telegram (для передачи в инструменты)
            
        Returns:
            Словарь с ключами:
            - messages: список BaseMessage объектов (AIMessage с tool_calls, ToolMessage, итд)
            - reply: текст финального ответа (для обратной совместимости)
            - tool_calls: список вызовов инструментов (опционально)
            - call_manager: флаг вызова CallManager (опционально)
            - manager_alert: сообщение для менеджера (опционально)
        """
        try:
            # Очищаем предыдущие tool_calls
            self._last_tool_calls = []
            self._call_manager_result = None
            
            # Выполняем запрос через orchestrator
            result = self.orchestrator.run_turn(message, history, chat_id=chat_id)
            
            # Преобразуем новые сообщения из словарей в BaseMessage объекты
            new_messages_dicts = result.get("new_messages", [])
            new_messages = dicts_to_messages(new_messages_dicts) if new_messages_dicts else []
            
            # Сохраняем tool_calls для обратной совместимости
            if result.get("tool_calls"):
                self._last_tool_calls = result["tool_calls"]
            
            # Проверяем CallManager
            if result.get("call_manager"):
                self._call_manager_result = {
                    "user_message": result.get("reply", ""),
                    "manager_alert": result.get("manager_alert"),
                }
                return {
                    "messages": new_messages,
                    "reply": result.get("reply", ""),
                    "tool_calls": result.get("tool_calls", []),
                    "call_manager": True,
                    "manager_alert": result.get("manager_alert"),
                }
            
            reply = result.get("reply", "")
            
            return {
                "messages": new_messages,
                "reply": reply,
                "tool_calls": result.get("tool_calls", []),
            }
        
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            
            logger.error(f"Ошибка в агенте {self.agent_name}: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            logger.error(f"Сообщение агента: {message[:200]}")
            logger.error(f"Traceback:\n{error_traceback}")
            raise
    
    def update_instruction(self, new_instruction: str):
        """Обновляет инструкцию агента (временно для следующего вызова)"""
        self.orchestrator.update_instructions(new_instruction)
    
    def reset_instruction(self):
        """Восстанавливает оригинальную инструкцию агента"""
        self.orchestrator.reset_instructions()
    
    def __call__(self, message: str, history: Optional[List[Dict[str, Any]]] = None, chat_id: Optional[str] = None) -> str:
        """
        Выполнение запроса к агенту (для обратной совместимости)
        
        Этот метод оставлен для обратной совместимости со старым кодом.
        Новый код должен использовать метод run().
        
        :param message: Сообщение для агента
        :param history: История сообщений (преобразованная из LangGraph messages)
        :param chat_id: ID чата в Telegram (для передачи в инструменты)
        :return: Ответ агента (строка)
        """
        result = self.run(message, history, chat_id)
        
        # Проверяем CallManager
        if result.get("call_manager"):
            return "[CALL_MANAGER_RESULT]"
        
        return result.get("reply", "")
