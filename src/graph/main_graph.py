"""
Основной граф состояний для обработки всех стадий диалога (Responses API)
"""
import json
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .conversation_state import ConversationState
from .utils import messages_to_history, filter_history_for_stage_detector, get_agent_history
from ..agents.stage_detector_agent import StageDetectorAgent
from ..agents.admin_agent import AdminAgent
from ..agents.demo_agent import DemoAgent, create_demo_actor_agent_with_config
from ..agents.demo_setup_agent import DemoSetupAgent

from ..services.langgraph_service import LangGraphService
from ..services.logger_service import logger


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
        
        # Получаем текущую стадию из состояния (восстанавливается через checkpointer)
        # КЛЮЧЕВОЕ ОТЛИЧИЕ: Не обращаемся к YDB, используем state["stage"]
        current_stage = state.get("stage")
        
        # ОБРАБОТКА КОМАНДЫ "СТОП" - выход из демо-режима
        # Работает только если мы в demo режиме
        if current_stage == "demo" and message.strip().lower() == "стоп":
            logger.info(f"🛑 Обнаружена команда 'стоп' для chat_id={chat_id} в demo режиме")
            logger.info(f"Переключение с demo на admin для chat_id={chat_id}")
            
            # Просто переключаем стадию на admin, граф продолжит работу и вызовет admin агента
            # Системное сообщение будет добавлено в _handle_admin после сообщения пользователя
            # Checkpointer автоматически сохранит это в PostgreSQL
            return {
                "stage": "admin",
            }
        
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
        
        КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Проверяем вызов SwitchToDemoTool в used_tools
        """
        # Проверяем использованные инструменты
        used_tools = state.get("used_tools", [])
        
        # Проверяем, был ли использован инструмент SwitchToDemoTool
        if "SwitchToDemoTool" in used_tools:
            logger.info("🔄 Обнаружен SwitchToDemoTool, переключаемся на demo")
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
        
        # Определяем, в какую историю сохранять сообщения
        # demo_setup сохраняет в общую историю messages, остальные - в изолированные
        update_dict = {}
        if agent_name == "DemoSetupAgent":
            # demo_setup использует общую историю
            update_dict["messages"] = new_messages
        elif agent_name == "AdminAgent":
            # admin использует изолированную историю
            update_dict["admin_messages"] = new_messages
        elif agent_name == "DemoAgent":
            # demo использует изолированную историю
            update_dict["demo_messages"] = new_messages
        
        # Проверяем, был ли вызван CallManager через инструмент
        if result.get("call_manager"):
            escalation_result = agent._call_manager_result if hasattr(agent, '_call_manager_result') and agent._call_manager_result else {}
            chat_id = state.get("chat_id", "unknown")
            
            logger.info(f"📞 CallManager был вызван через инструмент в агенте {agent_name}, chat_id: {chat_id}")
            
            # КРИТИЧНО: Сохраняем все существующие поля из state
            return {
                **state,  # Сохраняем все существующие поля
                **update_dict,  # Обновляем правильную историю
                "answer": escalation_result.get("user_message", result.get("reply", "")),
                "manager_alert": escalation_result.get("manager_alert", result.get("manager_alert")),
                "agent_name": agent_name,
                "used_tools": used_tools,
                "tool_results": tool_results,
            }
        
        # Обычный ответ агента
        answer = result.get("reply", "")
        
        # КРИТИЧНО: Сохраняем все существующие поля из state, чтобы не потерять demo_config, extracted_info и т.д.
        return {
            **state,  # Сохраняем все существующие поля
            **update_dict,  # Обновляем правильную историю
            "answer": answer,
            "agent_name": agent_name,
            "used_tools": used_tools,
            "tool_results": tool_results,
        }
    
    def _handle_admin(self, state: ConversationState) -> ConversationState:
        """Обработка административных функций"""
        logger.info("🔧 Обработка административных функций")
        message = state["message"]
        chat_id = state.get("chat_id")
        
        # Получаем изолированную историю для admin агента
        admin_messages = state.get("admin_messages", [])
        
        # Преобразуем в history для обратной совместимости с агентами
        # Orchestrator сам добавит сообщение пользователя, если его там нет
        history = messages_to_history(admin_messages) if admin_messages else None
        
        result = self._process_agent_result(self.admin_agent, message, history, chat_id, state, "AdminAgent")
        
        # Если сообщение - это "стоп" и мы только что переключились с demo, добавляем системное сообщение В КОНЕЦ
        # Проверяем, что предыдущая стадия была demo (можно проверить по наличию demo_config)
        if message.strip().lower() == "стоп" and state.get("demo_config"):
            logger.info(f"📝 Добавляю системное сообщение о завершении демонстрации в конец истории admin агента")
            from langchain_core.messages import SystemMessage
            
            # Получаем обновленную историю из результата (там уже есть сообщение "стоп" от orchestrator)
            updated_admin_messages = result.get("admin_messages", admin_messages)
            
            # Добавляем системное сообщение В САМЫЙ КОНЕЦ истории
            system_message = SystemMessage(content="Демонстрация проведена. Клиент завершил демонстрацию командой 'стоп'.")
            updated_admin_messages = list(updated_admin_messages) + [system_message]
            
            # Обновляем результат с новой историей
            result["admin_messages"] = updated_admin_messages
    
        # НЕ устанавливаем stage="admin" здесь, если будет переход в demo
        # stage будет установлен в _handle_demo, если произойдёт переключение
        # Если не будет перехода в demo, то stage останется "admin" из предыдущего состояния
        
        return result
    
    def _handle_demo(self, state: ConversationState) -> ConversationState:
        """
        Обработка демонстрационных функций
        
        КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Конфигурация хранится в state["demo_config"]
        
        Логика работы:
        1. Проверяет наличие конфигурации в state["demo_config"]
        2. Если конфигурации нет - вызывает demo-setup агента для создания конфигурации
        3. Demo-setup агент получает текущее сообщение и историю диалога
        4. После получения конфигурации сохраняет её в state["demo_config"]
        5. Создает demo-агента с заполненным промптом на основе конфигурации
        """
        message = state["message"]
        chat_id = state.get("chat_id")
        
        logger.info(f"🎯 [DEMO] Обработка демо-режима. chat_id={chat_id}, message={message[:100]}")
        
        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Получаем конфигурацию из состояния
        config = state.get("demo_config")
        
        # Если конфигурации нет, вызываем demo-setup агента
        if not config:
            logger.info(f"❌ [DEMO] Конфигурация НЕ найдена в состоянии для chat_id={chat_id}")
            logger.info(f"📞 [DEMO] Обращаемся к demo-setup агенту для получения конфигурации")
            
            # demo_setup получает ВСЮ общую историю (messages)
            setup_messages = state.get("messages", [])
            setup_history = messages_to_history(setup_messages) if setup_messages else None
            
            # Вызываем demo-setup агента
            setup_result = self.demo_setup_agent.run(message, setup_history, chat_id=chat_id)
            
            # Извлекаем ответ от demo-setup агента
            setup_answer = setup_result.get("reply", "")
            
            logger.info(f"📥 [DEMO] Demo-setup агент прислал ответ (длина: {len(setup_answer)} символов)")
            logger.debug(f"📥 [DEMO] Ответ demo-setup агента: {setup_answer[:500]}")
            
            # Парсим JSON из ответа
            config = self._parse_json_from_response(setup_answer)
            
            if config:
                # Валидация обязательных полей
                required_fields = ["niche", "company_name", "persona_instruction", "welcome_message"]
                missing_fields = [field for field in required_fields if field not in config]
                
                if missing_fields:
                    logger.error(f"❌ [DEMO] Отсутствуют обязательные поля в конфигурации: {missing_fields}")
                    logger.error(f"❌ [DEMO] Использую базовый demo агент без конфигурации")
                    # Используем изолированную историю для demo агента
                    # Orchestrator сам добавит текущее сообщение пользователя, если его там нет
                    demo_messages = state.get("demo_messages", [])
                    demo_history = messages_to_history(demo_messages) if demo_messages else None
                    result = self._process_agent_result(self.demo_agent, message, demo_history, chat_id, state, "DemoAgent")
                    result["stage"] = "demo"
                    return result
                
                logger.info(f"✅ [DEMO] Конфигурация успешно извлечена из ответа demo-setup агента")
                logger.info(f"📋 [DEMO] Конфигурация: niche={config.get('niche')}, company_name={config.get('company_name')}")
            else:
                logger.error(f"❌ [DEMO] Не удалось распарсить JSON из ответа demo-setup агента")
                logger.error(f"❌ [DEMO] Использую базовый demo агент без конфигурации")
                # Используем изолированную историю для demo агента
                # Orchestrator сам добавит текущее сообщение пользователя, если его там нет
                demo_messages = state.get("demo_messages", [])
                demo_history = messages_to_history(demo_messages) if demo_messages else None
                result = self._process_agent_result(self.demo_agent, message, demo_history, chat_id, state, "DemoAgent")
                result["stage"] = "demo"
                return result
            
            # Ответ от demo-setup агента НЕ отправляется клиенту
            logger.info(f"ℹ️ [DEMO] Ответ от demo-setup агента НЕ отправляется клиенту, продолжаю с созданием demo-агента с конфигурацией")
        else:
            logger.info(f"✅ [DEMO] Конфигурация НАЙДЕНА в состоянии для chat_id={chat_id}")
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
        
        # Используем изолированную историю для demo агента
        # Orchestrator сам добавит текущее сообщение пользователя, если его там нет
        demo_messages = state.get("demo_messages", [])
        demo_history = messages_to_history(demo_messages) if demo_messages else None
        
        # Вызываем demo-агента с сообщениями пользователя
        result = self._process_agent_result(demo_agent_with_config, message, demo_history, chat_id, state, "DemoAgent")
        
        # Добавляем префикс "[Демонстрация] " к ответу
        if result.get("answer"):
            answer = result["answer"]
            prefix = "[Демонстрация] "
            # Проверяем, не добавлен ли уже префикс
            if not answer.startswith(prefix):
                result["answer"] = prefix + answer
            logger.info(f"📤 [DEMO] Ответ demo-агента готов (длина: {len(result['answer'])} символов), добавлен префикс '[Демонстрация]'")
        
        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Сохраняем конфигурацию в состоянии
        # Checkpointer автоматически сохранит это в PostgreSQL
        result["stage"] = "demo"
        result["demo_config"] = config
        
        # Логируем для отладки
        logger.info(f"💾 [DEMO] Сохраняю в result: stage={result.get('stage')}, demo_config={bool(result.get('demo_config'))}")
        if result.get("demo_config"):
            logger.info(f"💾 [DEMO] demo_config содержит: niche={result['demo_config'].get('niche')}, company_name={result['demo_config'].get('company_name')}")
        
        return result
    
    def _parse_json_from_response(self, response_text: str) -> dict:
        """
        Парсит JSON из ответа LLM
        
        Args:
            response_text: Текст ответа от LLM
            
        Returns:
            Распарсенный JSON словарь или None
        """
        if not response_text or not response_text.strip():
            return None
        
        response_text = response_text.strip()
        
        # Убираем markdown code blocks если есть
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            if len(lines) > 1:
                response_text = "\n".join(lines[1:])
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Пытаемся найти JSON в тексте
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            return None
    
    def _handle_demo_setup(self, state: ConversationState) -> ConversationState:
        """Обработка настройки демонстрации"""
        logger.info("🔧 Обработка настройки демонстрации")
        message = state["message"]
        # demo_setup получает ВСЮ общую историю (messages)
        messages = state.get("messages", [])
        history = messages_to_history(messages) if messages else None
        chat_id = state.get("chat_id")
        
        result = self._process_agent_result(self.demo_setup_agent, message, history, chat_id, state, "DemoSetupAgent")

        # Сохраняем стадию в состоянии (checkpointer автоматически сохранит)
        result["stage"] = "demo_setup"
        
        return result
