"""
Основной граф состояний для обработки всех стадий диалога (Responses API)
"""
import asyncio
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .conversation_state import ConversationState
from .utils import messages_to_history, filter_history_for_stage_detector
from ..agents.stage_detector_agent import StageDetectorAgent
from ..agents.admin_agent import AdminAgent
from ..agents.demo_agent import DemoAgent, create_demo_actor_agent_with_config
from ..agents.demo_setup_agent import DemoSetupAgent

from ..services.langgraph_service import LangGraphService
from ..services.logger_service import logger
from ..services.session_config_service import get_session_config_service


def create_main_graph(langgraph_service: LangGraphService, checkpointer):
    """
    Создает и компилирует основной граф состояний
    
    Args:
        langgraph_service: Сервис LangGraph
        checkpointer: Обязательный checkpointer для сохранения состояния в PostgreSQL
        
    Returns:
        Скомпилированный граф
        
    Raises:
        ValueError: Если checkpointer не передан
    """
    if checkpointer is None:
        raise ValueError("checkpointer обязателен для работы с PostgreSQL. Граф должен компилироваться с checkpointer.")
    main_graph = MainGraph(langgraph_service, checkpointer=checkpointer)
    return main_graph.compiled_graph


class MainGraph:
    """Основной граф состояний для обработки всех стадий диалога"""
    
    # Кэш для агентов (чтобы не создавать их заново при каждом создании графа)
    _agents_cache = {}
    
    @classmethod
    def clear_cache(cls):
        """Очистить кэш агентов"""
        cls._agents_cache.clear()
    
    def __init__(self, langgraph_service: LangGraphService, checkpointer):
        """
        Инициализация графа с обязательным checkpointer
        
        Args:
            langgraph_service: Сервис LangGraph
            checkpointer: Обязательный checkpointer для сохранения состояния в PostgreSQL
            
        Raises:
            ValueError: Если checkpointer не передан
        """
        if checkpointer is None:
            raise ValueError("checkpointer обязателен для работы с PostgreSQL. Граф должен компилироваться с checkpointer.")
        
        self.langgraph_service = langgraph_service
        self.checkpointer = checkpointer
        
        # Используем кэш для агентов
        cache_key = id(langgraph_service)
        
        if cache_key not in MainGraph._agents_cache:
            # Создаём агентов только если их ещё нет в кэше
            MainGraph._agents_cache[cache_key] = {
                'stage_detector': StageDetectorAgent(langgraph_service),
                'admin': AdminAgent(langgraph_service),
                'demo': DemoAgent(langgraph_service),
                'demo_setup': DemoSetupAgent(langgraph_service),
            }
        
        # Используем агентов из кэша
        agents = MainGraph._agents_cache[cache_key]
        self.stage_detector = agents['stage_detector']
        self.admin_agent = agents['admin']
        self.demo_agent = agents['demo']
        self.demo_setup_agent = agents['demo_setup']
        
        # Создаём граф
        self.graph = self._create_graph()
        # КРИТИЧНО: компилируем граф С checkpointer для сохранения в PostgreSQL
        self.compiled_graph = self.graph.compile(checkpointer=checkpointer)
    
    def _create_graph(self) -> StateGraph:
        """Создание графа состояний"""
        graph = StateGraph(ConversationState)
        
        # Добавляем узлы
        graph.add_node("detect_stage", self._detect_stage)
        graph.add_node("handle_admin", self._handle_admin)
        graph.add_node("handle_demo", self._handle_demo)
        graph.add_node("handle_demo_setup", self._handle_demo_setup)
        
        # Добавляем рёбра
        graph.add_edge(START, "detect_stage")
        graph.add_conditional_edges(
            "detect_stage",
            self._route_after_detect,
            {
                "admin": "handle_admin",
                "demo": "handle_demo",
                "demo_setup": "handle_demo_setup",
                "end": END
            }
        )
        graph.add_conditional_edges(
            "handle_admin",
            self._route_after_admin,
            {
                "demo": "handle_demo",
                "end": END
            }
        )
        graph.add_edge("handle_demo", END)
        graph.add_edge("handle_demo_setup", END)
        return graph
    
    def _detect_stage(self, state: ConversationState) -> ConversationState:
        """
        Узел определения стадии
        
        КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Не использует YDB для хранения стадии.
        Стадия хранится в state["stage"] и автоматически сохраняется через checkpointer.
        """
        logger.info("Определение стадии диалога")
        
        message = state.get("message", "")
        chat_id = state.get("chat_id")
        
        # ОБРАБОТКА КОМАНДЫ "СТОП" - выход из демо-режима
        if message.strip().lower() == "стоп":
            logger.info(f"🛑 Обнаружена команда 'стоп' для chat_id={chat_id}")
            logger.info(f"Переключение с demo на admin для chat_id={chat_id}")
            
            # Обновляем стадию на admin в состоянии
            # Checkpointer автоматически сохранит это в PostgreSQL
            return {
                "stage": "admin",
                "answer": "Понравилась ли вам демонстрация? Если хотите, могу связать Вас с нашим менеджером для обсуждения сотрудничества."
            }
        
        # Получаем текущую стадию из состояния (восстанавливается через checkpointer)
        # КЛЮЧЕВОЕ ОТЛИЧИЕ: Не обращаемся к YDB, используем state["stage"]
        current_stage = state.get("stage")
        
        if current_stage:
            logger.info(f"📌 Найдена сохраненная стадия в checkpointer для chat_id={chat_id}: {current_stage}")
            # Если стадия уже установлена, используем её
            return {"stage": current_stage}
        
        # Если стадии нет (первый запуск), используем "admin" по умолчанию
        logger.info(f"📌 Стадия не найдена в checkpointer, используем по умолчанию: admin")
        return {"stage": "admin"}
    
    def _route_after_detect(self, state: ConversationState) -> Literal[
        "admin", "demo", "demo_setup", "end"
    ]:
        """Маршрутизация после определения стадии"""
        # Если есть answer (например, после команды "стоп"), завершаем граф
        if state.get("answer"):
            logger.info("Answer уже установлен в detect_stage, завершаем граф")
            return "end"
        
        # Маршрутизируем по стадии
        stage = state.get("stage", "admin")
        logger.info(f"🔀 Маршрутизация на стадию: {stage}")
        
        # Валидация стадии
        valid_stages = ["admin", "demo", "demo_setup"]
        
        if stage not in valid_stages:
            logger.warning(f"⚠️ Неизвестная стадия: {stage}, устанавливаю admin")
            return "admin"
        
        return stage
    
    def _route_after_admin(self, state: ConversationState) -> Literal["demo", "end"]:
        """
        Маршрутизация после обработки админом - проверка на переключение в demo
        
        КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Проверяем маркер [SWITCH_TO_DEMO_RESULT] вместо записи в YDB
        """
        # Проверяем использованные инструменты
        used_tools = state.get("used_tools", [])
        answer = state.get("answer", "")
        
        # Проверяем, был ли использован инструмент SwitchToDemoTool
        if "SwitchToDemoTool" in used_tools or "[SWITCH_TO_DEMO_RESULT]" in answer:
            logger.info("🔄 Обнаружен SwitchToDemoTool или маркер, переключаемся на demo")
            # Обновляем стадию в состоянии
            # Checkpointer автоматически сохранит это
            # КРИТИЧНО: Нужно обновить state["stage"] здесь, но это сделает _handle_demo
            return "demo"
        
        # Иначе завершаем граф
        return "end"
    
    def _process_agent_result(self, agent, message: str, history, chat_id: str, state: ConversationState, agent_name: str) -> ConversationState:
        """
        Обработка результата агента с проверкой на CallManager и SwitchToDemoTool
        
        Args:
            agent: Экземпляр агента
            message: Сообщение пользователя
            history: История сообщений
            chat_id: ID чата
            state: Текущее состояние графа
            agent_name: Имя агента
            
        Returns:
            Обновленное состояние графа с messages из orchestrator
        """
        # Используем новый метод run() для получения всех сообщений
        result = agent.run(message, history, chat_id=chat_id)
        
        # Получаем все новые сообщения из результата
        new_messages = result.get("messages", [])
        
        # Получаем полную информацию о tool_calls
        tool_results = result.get("tool_calls", [])
        used_tools = [tool.get("name") for tool in tool_results] if tool_results else []
        
        # Проверяем, был ли вызван CallManager через инструмент
        if result.get("call_manager"):
            escalation_result = agent._call_manager_result if hasattr(agent, '_call_manager_result') and agent._call_manager_result else {}
            chat_id = state.get("chat_id", "unknown")
            
            logger.info(f"📞 CallManager был вызван через инструмент в агенте {agent_name}, chat_id: {chat_id}")
            
            return {
                "messages": new_messages,
                "answer": escalation_result.get("user_message", result.get("reply", "")),
                "manager_alert": escalation_result.get("manager_alert", result.get("manager_alert")),
                "agent_name": agent_name,
                "used_tools": used_tools,
                "tool_results": tool_results,
            }
        
        # Обычный ответ агента
        answer = result.get("reply", "")
        
        return {
            "messages": new_messages,
            "answer": answer,
            "agent_name": agent_name,
            "used_tools": used_tools,
            "tool_results": tool_results,
        }
    
    def _handle_admin(self, state: ConversationState) -> ConversationState:
        """Обработка административных функций"""
        logger.info("🔧 Обработка административных функций")
        message = state["message"]
        # Преобразуем messages в history для обратной совместимости с агентами
        messages = state.get("messages", [])
        history = messages_to_history(messages) if messages else None
        chat_id = state.get("chat_id")
        
        result = self._process_agent_result(self.admin_agent, message, history, chat_id, state, "AdminAgent")
        
        # Сохраняем стадию в состоянии (checkpointer автоматически сохранит)
        result["stage"] = "admin"
        
        return result
    
    def _handle_demo(self, state: ConversationState) -> ConversationState:
        """
        Обработка демонстрационных функций
        
        Логика работы:
        1. Проверяет наличие конфигурации в SessionConfigService для данного thread_id (chat_id)
        2. Если конфигурации нет - вызывает demo-setup агента для создания конфигурации
        3. Demo-setup агент получает текущее сообщение и историю диалога
        4. После получения конфигурации создает demo-агента с заполненным промптом
        """
        message = state["message"]
        messages = state.get("messages", [])
        history = messages_to_history(messages) if messages else None
        chat_id = state.get("chat_id")
        
        logger.info(f"🎯 [DEMO] Обработка демо-режима. chat_id={chat_id}, message={message[:100]}")
        
        # Получаем сервис для работы с конфигурациями сессий
        session_config_service = get_session_config_service()
        
        # Используем chat_id как thread_id
        thread_id = chat_id if chat_id else "unknown"
        
        logger.info(f"🔍 [DEMO] Проверка наличия конфигурации в базе данных для thread_id={thread_id}")
        
        # Проверяем наличие конфигурации в SessionConfigs
        config = asyncio.run(session_config_service.load_demo_config(thread_id))
        
        # Если конфигурации нет, вызываем demo-setup агента
        if not config:
            logger.info(f"❌ [DEMO] Запись в базе данных НЕ найдена для thread_id={thread_id}")
            logger.info(f"📞 [DEMO] Обращаемся к demo-setup агенту для получения конфигурации")
            
            # Вызываем demo-setup агента
            setup_result = self.demo_setup_agent.run(message, history, chat_id=chat_id)
            
            # Извлекаем ответ от demo-setup агента
            setup_answer = setup_result.get("reply", "")
            
            logger.info(f"📥 [DEMO] Demo-setup агент прислал ответ (длина: {len(setup_answer)} символов)")
            logger.debug(f"📥 [DEMO] Ответ demo-setup агента: {setup_answer[:500]}")
            
            # Обрабатываем ответ demo-setup агента и сохраняем конфигурацию
            user_id = chat_id  # Используем chat_id как user_id
            
            logger.info(f"💾 [DEMO] Обрабатываю ответ demo-setup агента и сохраняю в базу данных для thread_id={thread_id}")
            
            saved_config = asyncio.run(session_config_service.process_setup_response(
                thread_id=thread_id,
                user_id=user_id,
                response_text=setup_answer
            ))
            
            if saved_config:
                config = saved_config
                logger.info(f"✅ [DEMO] Конфигурация успешно сохранена и загружена для thread_id={thread_id}")
                logger.info(f"📋 [DEMO] Конфигурация: niche={config.get('niche')}, company_name={config.get('company_name')}")
            else:
                # Если не удалось сохранить, пробуем загрузить еще раз
                logger.warning(f"⚠️ [DEMO] Не удалось сохранить конфигурацию, пробую загрузить еще раз для thread_id={thread_id}")
                config = asyncio.run(session_config_service.load_demo_config(thread_id))
                if not config:
                    logger.error(f"❌ [DEMO] КРИТИЧЕСКАЯ ОШИБКА: Не удалось сохранить или загрузить конфигурацию для thread_id={thread_id}")
                    logger.error(f"❌ [DEMO] Использую базовый demo агент без конфигурации")
                    # В случае ошибки используем базовый demo агент
                    result = self._process_agent_result(self.demo_agent, message, history, chat_id, state, "DemoAgent")
                    result["stage"] = "demo"  # Сохраняем стадию
                    return result
            
            # Ответ от demo-setup агента НЕ отправляется клиенту
            logger.info(f"ℹ️ [DEMO] Ответ от demo-setup агента НЕ отправляется клиенту, продолжаю с созданием demo-агента с конфигурацией")
        else:
            logger.info(f"✅ [DEMO] Запись в базе данных НАЙДЕНА для thread_id={thread_id}")
            logger.info(f"📋 [DEMO] Загруженная конфигурация: niche={config.get('niche')}, company_name={config.get('company_name')}")
        
        # Определяем язык (пока используем "ru" по умолчанию)
        language = "ru"
        
        logger.info(f"🤖 [DEMO] Создаю demo-агента с заполненным промптом на основе конфигурации (язык: {language})")
        
        # Создаем demo-агента с заполненным промптом на основе конфигурации
        demo_agent_with_config = create_demo_actor_agent_with_config(
            langgraph_service=self.langgraph_service,
            config=config,
            language=language
        )
        
        logger.info(f"💬 [DEMO] Вызываю demo-агента с сообщением пользователя")
        
        # Вызываем demo-агента с сообщениями пользователя
        result = self._process_agent_result(demo_agent_with_config, message, history, chat_id, state, "DemoAgent")
        
        # Добавляем префикс "[Демонстрация] " к ответу
        if result.get("answer"):
            answer = result["answer"]
            prefix = "[Демонстрация] "
            # Проверяем, не добавлен ли уже префикс
            if not answer.startswith(prefix):
                result["answer"] = prefix + answer
            logger.info(f"📤 [DEMO] Ответ demo-агента готов (длина: {len(result['answer'])} символов), добавлен префикс '[Демонстрация]'")
        
        # Сохраняем стадию в состоянии (checkpointer автоматически сохранит)
        result["stage"] = "demo"
        
        return result
    
    def _handle_demo_setup(self, state: ConversationState) -> ConversationState:
        """Обработка настройки демонстрации"""
        logger.info("🔧 Обработка настройки демонстрации")
        message = state["message"]
        messages = state.get("messages", [])
        history = messages_to_history(messages) if messages else None
        chat_id = state.get("chat_id")
        
        result = self._process_agent_result(self.demo_setup_agent, message, history, chat_id, state, "DemoSetupAgent")
        
        # Сохраняем стадию в состоянии (checkpointer автоматически сохранит)
        result["stage"] = "demo_setup"
        
        return result
