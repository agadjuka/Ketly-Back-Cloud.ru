"""
Сервис для вызова CallManager при критических ошибках
"""
from ..services.logger_service import logger
from ..services.escalation_service import EscalationService


class CallManagerException(Exception):
    """Исключение для обработки вызова CallManager на нижнем уровне"""
    def __init__(self, escalation_result: dict):
        """
        :param escalation_result: Результат эскалации с полями user_message и manager_alert
        """
        self.escalation_result = escalation_result
        super().__init__("CallManager был вызван из-за критической ошибки")


class CallManagerService:
    """Сервис для обработки критических ошибок через CallManager"""
    
    @staticmethod
    def handle_critical_error(
        error_message: str,
        agent_name: str,
        message: str,
        chat_id: str = None
    ) -> dict:
        """
        Обработка критических ошибок через CallManager
        
        :param error_message: Сообщение об ошибке
        :param agent_name: Имя агента, в котором произошла ошибка
        :param message: Исходное сообщение пользователя
        :param chat_id: ID чата (опционально)
        :return: Результат эскалации с полями user_message и manager_alert
        """
        logger.error(f"CallManager вызван для агента {agent_name}")
        logger.error(f"Ошибка: {error_message}")
        logger.error(f"Исходное сообщение: {message[:200]}")
        if chat_id:
            logger.error(f"Chat ID: {chat_id}")
        
        # Формируем отчет для менеджера
        manager_report = f"Отчет для менеджера:\n"
        manager_report += f"Причина: Критическая ошибка после всех попыток retry\n"
        manager_report += f"Агент: {agent_name}\n"
        manager_report += f"Ошибка: {error_message}\n"
        manager_report += f"Исходное сообщение пользователя: {message}"
        
        # Используем EscalationService для формирования ответа
        escalation_service = EscalationService()
        call_manager_text = f"[CALL_MANAGER]\n{manager_report}"
        
        # Обрабатываем через EscalationService
        escalation_result = escalation_service.handle(call_manager_text, str(chat_id) if chat_id else "unknown")
        
        return escalation_result









