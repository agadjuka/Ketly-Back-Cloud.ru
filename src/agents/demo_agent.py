"""
Агент для демонстрационных функций
"""
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from ..services.langgraph_service import LangGraphService


# Шаблон промпта для демо-агента
DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE = """# ROLE
Ты - AI-агент в режиме "Симуляция". Сейчас ты играешь роль виртуального сотрудника бизнеса.
Твоя задача - продемонстрировать навыки общения, идеально следуя заданной роли и тональности. В этой роли ты должен стараться продать клиенту услугу или товар, но не быть слишком навязчивым.

# BUSINESS CONTEXT (Данные о бизнесе)
{business_info_block}

# YOUR PERSONALITY & INSTRUCTIONS (Инструкция к роли)
{actor_instruction}

# GUIDELINES (Правила поведения)
1. **Держи образ:** Полностью погрузись в роль. Не пиши "как языковая модель". Ты - живой сотрудник. 
2. Твоя задача быть качественным продажником. Если тебе задают вопрос о наличии товаров или услуг, придумай список товаров, и сразу указывай цены. Подтолкни клиента к покупке. Не задавай слишком много вопросов.
3. **Импровизация:** Если спрашивают о конкретных ценах или товарах, которых нет в инструкции - придумывай реалистичные данные, подходящие под нишу. Твоя цель - показать стиль общения.
4. **Краткость:** Твои ответы должны быть емкими и естественными (1-3 предложения).
5.  Первое сообщение в режиме симуляции сделай следующим: "[[DEMO_START::ниша в родительном падеже]]" (например "магазина сантехники")
Здравствуйте! [Приветственное сообщение]...
"""


def create_demo_actor_agent_with_config(
    langgraph_service: LangGraphService,
    config: Dict[str, Any],
    language: str = "ru"
) -> "DemoAgent":
    """
    Создает демо-агента с заполненным промптом на основе конфигурации.
    
    Args:
        langgraph_service: Сервис LangGraph
        config: Словарь с конфигурацией (должен содержать niche, company_name, persona_instruction, welcome_message)
        language: Язык интерфейса (по умолчанию "ru", английская версия не используется)
        
    Returns:
        Экземпляр DemoAgent с заполненным промптом
    """
    # Используем только русский шаблон
    template = DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE
    
    # Формируем блок с информацией о бизнесе
    business_info_block = f"""Ниша бизнеса: {config.get('niche', 'Не указана')}
Название компании: {config.get('company_name', 'Не указано')}"""
    
    # Формируем инструкцию для актера
    persona_instruction = config.get('persona_instruction', '')
    welcome_message = config.get('welcome_message', '')
    
    actor_instruction = f"""{persona_instruction}

Приветственное сообщение: {welcome_message}"""
    
    # Заполняем шаблон
    instruction = template.format(
        business_info_block=business_info_block,
        actor_instruction=actor_instruction
    )
    
    # Создаем агента с заполненным промптом
    return DemoAgent(langgraph_service, instruction)


class DemoAgent(BaseAgent):
    """Агент для демонстрационных функций"""
    
    def __init__(
        self,
        langgraph_service: LangGraphService,
        instruction: Optional[str] = None
    ):
        # Если инструкция не передана, используем placeholder
        if instruction is None:
            instruction = """Placeholder: Инструкции для демонстрационного агента"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[],
            agent_name="Демонстрационный агент"
        )





