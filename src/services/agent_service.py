"""
Модуль для работы с LangGraph (OpenAI API)
"""
from datetime import datetime
import pytz

from langchain_core.messages import HumanMessage
from .debug_service import DebugService
from .logger_service import logger
from ..graph.main_graph import create_main_graph
from .langgraph_service import LangGraphService
from ..storage.checkpointer import get_postgres_checkpointer, clear_thread_memory


class AgentService:
    """Сервис для работы с LangGraph (OpenAI API)"""
    
    def __init__(self, debug_service: DebugService):
        """Инициализация сервиса с внедрением зависимостей"""
        self.debug_service = debug_service
        
        # Ленивая инициализация LangGraph
        self._langgraph_service = None
    
    @property
    def langgraph_service(self) -> LangGraphService:
        """Ленивая инициализация LangGraphService"""
        if self._langgraph_service is None:
            self._langgraph_service = LangGraphService()
        return self._langgraph_service
    
    async def send_to_agent_langgraph(self, chat_id: str, user_text: str) -> dict:
        """
        Отправка сообщения через LangGraph с использованием нативной памяти PostgreSQL
        """
        thread_id = str(chat_id)
        
        logger.info(f"Обработка сообщения от chat_id={chat_id}")
        
        try:
            async with get_postgres_checkpointer() as checkpointer:
                app = create_main_graph(self.langgraph_service, checkpointer=checkpointer)
                config = {"configurable": {"thread_id": thread_id}}
                
                # Восстанавливаем предыдущее состояние из checkpointer
                previous_extracted_info = None
                previous_demo_config = None
                previous_stage = None
                try:
                    state_snapshot = await checkpointer.aget(config)
                    if state_snapshot:
                        previous_values = state_snapshot.values if hasattr(state_snapshot, 'values') else state_snapshot.get('values', {})
                        previous_extracted_info = previous_values.get("extracted_info")
                        previous_demo_config = previous_values.get("demo_config")
                        previous_stage = previous_values.get("stage")
                        logger.info(f"📥 Восстановлено из checkpointer: extracted_info={bool(previous_extracted_info)}, demo_config={bool(previous_demo_config)}, stage={previous_stage}")
                        if previous_demo_config:
                            logger.info(f"📥 demo_config содержит: niche={previous_demo_config.get('niche')}, company_name={previous_demo_config.get('company_name')}")
                except Exception as e:
                    logger.debug(f"Не удалось восстановить состояние из checkpointer: {e}")
                
                # Формируем входные данные
                input_data = {
                    "messages": [HumanMessage(content=user_text)],
                    "message": user_text,
                    "chat_id": chat_id,
                    "answer": "",
                    "manager_alert": None
                }
                
                # Добавляем восстановленные данные
                if previous_extracted_info is not None:
                    input_data["extracted_info"] = previous_extracted_info
                if previous_demo_config is not None:
                    input_data["demo_config"] = previous_demo_config
                if previous_stage is not None:
                    input_data["stage"] = previous_stage
                
                final_state = await app.ainvoke(input_data, config)
                
                # Извлекаем ответ из финального состояния
                answer = final_state.get("answer", "")
                manager_alert = final_state.get("manager_alert")
                
                # Проверяем, является ли это первым сообщением, используя messages из final_state
                # Считаем ВСЕ сообщения от пользователя (включая текущее)
                messages = final_state.get("messages", [])
                user_messages_count = 0
                for msg in messages:
                    msg_type = getattr(msg, 'type', None) if hasattr(msg, 'type') else msg.get('type', '')
                    if msg_type in ['human', 'user']:
                        user_messages_count += 1
                
                # Если только одно сообщение от пользователя (текущее), значит это первое сообщение
                is_first_message = user_messages_count == 1
                
                # Получаем текущую дату и время в московском часовом поясе для проверки первого сообщения в день
                current_datetime = None
                try:
                    moscow_tz = pytz.timezone('Europe/Moscow')
                    current_datetime = datetime.now(moscow_tz)
                except Exception:
                    # Если не удалось получить время, передаем None (проверка первого сообщения в день не будет работать)
                    pass
                
                # Форматируем ответ агента
                from .text_formatter_service import format_agent_response, format_manager_alert
                
                answer = format_agent_response(answer, is_first_message, messages, current_datetime)
                
                result = {"user_message": answer, "is_first_message": is_first_message}
                if manager_alert:
                    manager_alert = format_manager_alert(manager_alert)
                    result["manager_alert"] = manager_alert
                
                return result
                
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения через LangGraph: {e}", exc_info=True)
            return {
                "user_message": "Извините, произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз."
            }
    
    async def send_to_agent(self, chat_id: str, user_text: str) -> dict:
        """Отправка сообщения агенту через LangGraph"""
        return await self.send_to_agent_langgraph(chat_id, user_text)
    
    async def reset_context(self, chat_id: str):
        """
        Полный сброс контекста для чата через физическое удаление чекпоинтов из БД.
        """
        try:
            thread_id = str(chat_id)
            
            logger.info(f"Полный сброс контекста для chat_id={chat_id}")
            
            await clear_thread_memory(thread_id)
            
            logger.info(f"Память полностью очищена для chat_id={chat_id}")
            
            # Очищаем историю результатов инструментов
            try:
                from .tool_history_service import get_tool_history_service
                tool_history_service = get_tool_history_service()
                tool_history_service.clear_history(chat_id)
                logger.debug(f"История результатов инструментов очищена для chat_id={chat_id}")
            except Exception as e:
                logger.debug(f"Ошибка при очистке истории результатов инструментов: {e}")
                
        except Exception as e:
            logger.error(f"Ошибка при сбросе контекста: {e}", exc_info=True)
            raise

