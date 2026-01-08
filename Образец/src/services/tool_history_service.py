"""
Сервис для управления историей результатов инструментов
Сохраняет результаты инструментов из последних N циклов для использования в контексте
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque
from ..services.logger_service import logger


class ToolHistoryService:
    """Сервис для управления историей результатов инструментов"""
    
    def __init__(self, max_cycles: int = 3):
        """
        Инициализация сервиса
        
        Args:
            max_cycles: Количество циклов для хранения истории (по умолчанию 3)
        """
        self.max_cycles = max_cycles
        # Словарь для хранения истории по chat_id: {chat_id: deque([{cycle_data}, ...])}
        self._history: Dict[str, deque] = {}
    
    def save_tool_results(self, chat_id: str, tool_results: List[Dict[str, Any]], cycle_metadata: Optional[Dict[str, Any]] = None):
        """
        Сохраняет результаты инструментов для текущего цикла
        
        Args:
            chat_id: ID чата
            tool_results: Список результатов инструментов в формате [{"name": str, "args": dict, "result": str}, ...]
            cycle_metadata: Дополнительные метаданные цикла (например, agent_name, timestamp)
        """
        if not chat_id:
            logger.warning("ToolHistoryService: chat_id не указан, пропускаем сохранение")
            return
        
        # Инициализируем историю для chat_id, если её ещё нет
        if chat_id not in self._history:
            self._history[chat_id] = deque(maxlen=self.max_cycles)
        
        # Формируем данные цикла
        cycle_data = {
            "timestamp": datetime.now().isoformat(),
            "tool_results": tool_results.copy() if tool_results else [],
            "metadata": cycle_metadata.copy() if cycle_metadata else {}
        }
        
        # Добавляем в историю (deque автоматически ограничивает размер до max_cycles)
        self._history[chat_id].append(cycle_data)
        
        logger.debug(f"ToolHistoryService: Сохранены результаты инструментов для chat_id={chat_id}, циклов в истории: {len(self._history[chat_id])}")
    
    def get_last_cycles_tool_results(self, chat_id: str, cycles: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Получает результаты инструментов из последних N циклов
        
        Args:
            chat_id: ID чата
            cycles: Количество циклов для получения (по умолчанию max_cycles)
            
        Returns:
            Список данных циклов с результатами инструментов
        """
        if not chat_id or chat_id not in self._history:
            return []
        
        cycles_to_get = cycles if cycles is not None else self.max_cycles
        history = self._history[chat_id]
        
        # Получаем последние N циклов
        cycles_data = list(history)[-cycles_to_get:] if len(history) > cycles_to_get else list(history)
        
        return cycles_data
    
    def format_tool_results_for_context(self, chat_id: str, cycles: Optional[int] = None) -> str:
        """
        Форматирует результаты инструментов из последних циклов для добавления в контекст
        
        Args:
            chat_id: ID чата
            cycles: Количество циклов для получения (по умолчанию max_cycles)
            
        Returns:
            Отформатированная строка с результатами инструментов для добавления в контекст
        """
        cycles_data = self.get_last_cycles_tool_results(chat_id, cycles)
        
        if not cycles_data:
            return ""
        
        formatted_parts = []
        formatted_parts.append("=== История результатов инструментов из последних циклов ===\n")
        
        for idx, cycle_data in enumerate(cycles_data, 1):
            timestamp = cycle_data.get("timestamp", "Неизвестно")
            metadata = cycle_data.get("metadata", {})
            agent_name = metadata.get("agent_name", "Неизвестный агент")
            tool_results = cycle_data.get("tool_results", [])
            
            formatted_parts.append(f"\n--- Цикл {idx} ({timestamp}) ---")
            formatted_parts.append(f"Агент: {agent_name}")
            
            if tool_results:
                formatted_parts.append("Результаты инструментов:")
                for tool_result in tool_results:
                    tool_name = tool_result.get("name", "Неизвестный инструмент")
                    tool_args = tool_result.get("args", {})
                    tool_result_text = tool_result.get("result", "")
                    
                    formatted_parts.append(f"\n  Инструмент: {tool_name}")
                    if tool_args:
                        formatted_parts.append(f"  Аргументы: {tool_args}")
                    formatted_parts.append(f"  Результат: {tool_result_text[:500]}")  # Ограничиваем длину
            else:
                formatted_parts.append("Инструменты не использовались")
            
            formatted_parts.append("")  # Пустая строка между циклами
        
        formatted_parts.append("=== Конец истории результатов инструментов ===\n")
        
        return "\n".join(formatted_parts)
    
    def clear_history(self, chat_id: str):
        """
        Очищает историю результатов инструментов для указанного чата
        
        Args:
            chat_id: ID чата
        """
        if chat_id in self._history:
            del self._history[chat_id]
            logger.debug(f"ToolHistoryService: История очищена для chat_id={chat_id}")
    
    def get_history_summary(self, chat_id: str) -> Dict[str, Any]:
        """
        Получает краткую сводку истории для указанного чата
        
        Args:
            chat_id: ID чата
            
        Returns:
            Словарь с информацией о истории
        """
        if not chat_id or chat_id not in self._history:
            return {
                "cycles_count": 0,
                "total_tools": 0,
                "tools_by_name": {}
            }
        
        history = self._history[chat_id]
        total_tools = 0
        tools_by_name = {}
        
        for cycle_data in history:
            tool_results = cycle_data.get("tool_results", [])
            total_tools += len(tool_results)
            
            for tool_result in tool_results:
                tool_name = tool_result.get("name", "Unknown")
                tools_by_name[tool_name] = tools_by_name.get(tool_name, 0) + 1
        
        return {
            "cycles_count": len(history),
            "total_tools": total_tools,
            "tools_by_name": tools_by_name
        }


# Глобальный экземпляр сервиса
_tool_history_service: Optional[ToolHistoryService] = None


def get_tool_history_service() -> ToolHistoryService:
    """Получение глобального экземпляра ToolHistoryService"""
    global _tool_history_service
    if _tool_history_service is None:
        _tool_history_service = ToolHistoryService(max_cycles=3)
    return _tool_history_service











