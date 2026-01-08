"""
Фабрика для создания и инициализации сервисов
"""
from src.services import DebugService, EscalationService, LangGraphService
from src.services.agent_service import AgentService


class ServiceFactory:
    """Фабрика для создания сервисов с правильными зависимостями"""
    
    def __init__(self):
        self._debug_service = None
        self._agent_service = None
        self._escalation_service = None
        self._langgraph_service = None
    
    def get_debug_service(self) -> DebugService:
        """Получить экземпляр DebugService"""
        if self._debug_service is None:
            self._debug_service = DebugService()
        return self._debug_service

    def get_escalation_service(self) -> EscalationService:
        """Получить экземпляр EscalationService"""
        if self._escalation_service is None:
            self._escalation_service = EscalationService()
        return self._escalation_service
    
    def get_agent_service(self) -> AgentService:
        """Получить экземпляр AgentService с внедренными зависимостями"""
        if self._agent_service is None:
            debug_service = self.get_debug_service()
            self._agent_service = AgentService(debug_service)
        return self._agent_service
    
    def get_langgraph_service(self) -> LangGraphService:
        """Получить экземпляр LangGraphService"""
        if self._langgraph_service is None:
            self._langgraph_service = LangGraphService()
        return self._langgraph_service


# Глобальный экземпляр фабрики
service_factory = ServiceFactory()


def get_agent_service() -> AgentService:
    """Получение экземпляра AgentService"""
    return service_factory.get_agent_service()
