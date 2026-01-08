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
        
        Граф сам управляет историей через checkpointer, нам нужно только передать новое сообщение.
        """
        # Получаем telegram_user_id из chat_id (они равны для личных чатов)
        try:
            telegram_user_id = int(chat_id)
        except ValueError:
            logger.error(f"Не удалось преобразовать chat_id={chat_id} в telegram_user_id")
            telegram_user_id = 0
        
        # Используем сообщение пользователя без изменений
        user_message_text = user_text
        
        logger.info(f"Обработка сообщения от chat_id={chat_id}, telegram_user_id={telegram_user_id}")
        
        try:
            # Используем checkpointer для работы с нативной памятью LangGraph
            async with get_postgres_checkpointer() as checkpointer:
                # Создаем граф с checkpointer
                app = create_main_graph(self.langgraph_service, checkpointer=checkpointer)
                
                # Используем ID пользователя как thread_id для изоляции сессий
                config = {"configurable": {"thread_id": str(telegram_user_id)}}
                
                # Пытаемся восстановить предыдущее состояние из checkpointer
                # чтобы сохранить extracted_info и demo_config между вызовами
                previous_extracted_info = None
                previous_demo_config = None
                previous_stage = None
                try:
                    # Получаем последнее состояние из checkpointer
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
                
                # Формируем входные данные - ТОЛЬКО новое сообщение
                # История граф подтянет сам из БД через checkpointer!
                # extracted_info не передаем, чтобы не перезаписать восстановленное значение
                # ВАЖНО: НЕ передаем stage, чтобы не перезаписать сохранённое значение!
                input_data = {
                    "messages": [HumanMessage(content=user_message_text)],
                    "message": user_message_text,  # Для обратной совместимости с узлами
                    "chat_id": chat_id,
                    # НЕ передаем stage - оно должно восстановиться из checkpointer автоматически
                    # НЕ передаем extracted_info - оно должно восстановиться из checkpointer автоматически
                    # Если нужно явно установить, используем previous_extracted_info
                    "answer": "",
                    "manager_alert": None
                }
                
                # Если удалось восстановить данные, добавляем их в input_data
                # Это нужно, чтобы LangGraph правильно объединил состояние
                if previous_extracted_info is not None:
                    input_data["extracted_info"] = previous_extracted_info
                if previous_demo_config is not None:
                    input_data["demo_config"] = previous_demo_config
                if previous_stage is not None:
                    input_data["stage"] = previous_stage
                
                # Запускаем граф и обрабатываем поток событий
                # Используем ainvoke для получения финального состояния
                # (astream используется для потоковой обработки, но нам нужен финальный результат)
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
        
        Удаляет все записи чекпоинтов для пользователя из PostgreSQL,
        что обеспечивает полную очистку памяти, как будто пользователь пишет впервые.
        """
        try:
            # Получаем telegram_user_id из chat_id
            try:
                telegram_user_id = int(chat_id)
            except ValueError:
                logger.error(f"Не удалось преобразовать chat_id={chat_id} в telegram_user_id")
                telegram_user_id = 0
            
            logger.info(f"Полный сброс контекста для chat_id={chat_id}, telegram_user_id={telegram_user_id}")
            
            # Физически удаляем все чекпоинты из БД для этого thread_id
            await clear_thread_memory(str(telegram_user_id))
            
            logger.info(f"Память полностью очищена для telegram_user_id={telegram_user_id}")
            
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

