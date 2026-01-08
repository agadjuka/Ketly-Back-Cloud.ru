"""
Фабрика для создания и инициализации сервисов
"""
from src.services import AuthService, DebugService, YandexAgentService, EscalationService, LangGraphService


class ServiceFactory:
    """Фабрика для создания сервисов с правильными зависимостями"""
    
    def __init__(self):
        self._auth_service = None
        self._debug_service = None
        self._yandex_agent_service = None
        self._escalation_service = None
        self._langgraph_service = None
    
    def get_auth_service(self) -> AuthService:
        """Получить экземпляр AuthService"""
        if self._auth_service is None:
            self._auth_service = AuthService()
        return self._auth_service
    
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
    
    def get_yandex_agent_service(self) -> YandexAgentService:
        """Получить экземпляр YandexAgentService с внедренными зависимостями"""
        if self._yandex_agent_service is None:
            auth_service = self.get_auth_service()
            debug_service = self.get_debug_service()
            self._yandex_agent_service = YandexAgentService(auth_service, debug_service)
        return self._yandex_agent_service
    
    def get_langgraph_service(self) -> LangGraphService:
        """Получить экземпляр LangGraphService"""
        if self._langgraph_service is None:
            self._langgraph_service = LangGraphService()
        return self._langgraph_service


# Глобальный экземпляр фабрики
service_factory = ServiceFactory()


def get_yandex_agent_service() -> YandexAgentService:
    """Получение экземпляра YandexAgentService (совместимость с старым API)"""
    return service_factory.get_yandex_agent_service()
