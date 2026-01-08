"""
Сервис для retry логики на нижнем уровне (после выполнения всего графа)
"""
from typing import Callable, TypeVar, Optional
import inspect
import asyncio
from ..services.error_checker import ErrorChecker
from ..services.logger_service import logger
from ..services.call_manager_service import CallManagerService, CallManagerException

T = TypeVar('T')


class RetryService:
    """Сервис для повторных попыток выполнения операций при Internal Server Error"""
    
    @staticmethod
    def execute_with_retry(
        operation: Callable[[], T],
        max_retries: int = 3,
        operation_name: str = "операция",
        context_info: Optional[dict] = None
    ) -> T:
        """
        Синхронная версия: выполняет операцию с retry логикой для Internal Server Error
        
        :param operation: Функция для выполнения (может быть async или sync)
        :param max_retries: Максимальное количество попыток (по умолчанию 3)
        :param operation_name: Имя операции для логирования
        :param context_info: Дополнительная информация для контекста (chat_id, message и т.д.)
        :return: Результат выполнения операции
        """
        # Если операция async, создаем новый event loop для синхронного контекста
        # В async контексте нужно использовать execute_with_retry_async напрямую
        if inspect.iscoroutinefunction(operation):
            return asyncio.run(RetryService.execute_with_retry_async(
                operation, max_retries, operation_name, context_info
            ))
        
        # Синхронная версия
        return RetryService._execute_with_retry_sync(
            operation, max_retries, operation_name, context_info
        )
    
    @staticmethod
    async def execute_with_retry_async(
        operation: Callable[[], T],
        max_retries: int = 3,
        operation_name: str = "операция",
        context_info: Optional[dict] = None
    ) -> T:
        """
        Асинхронная версия: выполняет операцию с retry логикой для Internal Server Error
        
        :param operation: Async функция для выполнения
        :param max_retries: Максимальное количество попыток (по умолчанию 3)
        :param operation_name: Имя операции для логирования
        :param context_info: Дополнительная информация для контекста (chat_id, message и т.д.)
        :return: Результат выполнения операции
        """
        return await RetryService._execute_with_retry_async(
            operation, max_retries, operation_name, context_info
        )
    
    @staticmethod
    def _execute_with_retry_sync(
        operation: Callable[[], T],
        max_retries: int,
        operation_name: str,
        context_info: Optional[dict]
    ) -> T:
        """Внутренняя синхронная реализация retry логики"""
        last_error = None
        last_error_message = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # Выполняем синхронную операцию
                result = operation()
                return result
                
            except RuntimeError as e:
                error_message = str(e)
                # Получаем информацию об ошибке из res.error если доступна
                res_error = getattr(e, 'res_error', None) if hasattr(e, 'res_error') else None
                error_to_check = res_error if res_error else error_message
                
                # Проверяем, нужно ли эскалировать ошибку менеджеру (без retry)
                if ErrorChecker.should_escalate_to_manager(error_to_check) or ErrorChecker.should_escalate_to_manager(error_message):
                    logger.error(
                        f"{operation_name}: обнаружена ошибка, требующая эскалации менеджеру. "
                        f"Вызываем CallManager без retry."
                    )
                    
                    # Извлекаем информацию из контекста для CallManager
                    chat_id = context_info.get('chat_id') if context_info else None
                    message = context_info.get('message') if context_info else None
                    agent_name = context_info.get('agent_name') if context_info else operation_name
                    
                    # Вызываем CallManager и получаем результат эскалации
                    escalation_result = CallManagerService.handle_critical_error(
                        error_message=error_to_check or error_message,
                        agent_name=agent_name,
                        message=message or "Не указано",
                        chat_id=chat_id
                    )
                    # Выбрасываем специальное исключение с результатом эскалации
                    # Это исключение будет обработано на нижнем уровне (bot)
                    raise CallManagerException(escalation_result)
                
                # Проверяем, является ли это InternalServerError
                if ErrorChecker.is_internal_server_error(error_to_check):
                    last_error = e
                    last_error_message = error_to_check
                    
                    logger.warning(
                        f"Попытка {attempt}/{max_retries} для {operation_name}: "
                        f"InternalServerError - повторяем операцию"
                    )
                    
                    if attempt < max_retries:
                        continue
                    else:
                        # После всех неудачных попыток вызываем CallManager
                        logger.error(
                            f"{operation_name}: все {max_retries} попытки завершились "
                            f"InternalServerError. Вызываем CallManager."
                        )
                        
                        # Извлекаем информацию из контекста для CallManager
                        chat_id = context_info.get('chat_id') if context_info else None
                        message = context_info.get('message') if context_info else None
                        agent_name = context_info.get('agent_name') if context_info else operation_name
                        
                        # Вызываем CallManager и получаем результат эскалации
                        escalation_result = CallManagerService.handle_critical_error(
                            error_message=last_error_message or error_message,
                            agent_name=agent_name,
                            message=message or "Не указано",
                            chat_id=chat_id
                        )
                        # Выбрасываем специальное исключение с результатом эскалации
                        # Это исключение будет обработано на нижнем уровне (bot)
                        raise CallManagerException(escalation_result)
                else:
                    # Если это не InternalServerError, сразу выбрасываем исключение
                    raise
            except Exception as e:
                # Для других типов ошибок не делаем retry
                raise
        
        # Если дошли сюда (не должно произойти, но на всякий случай)
        if last_error:
            raise last_error
        raise RuntimeError(f"Не удалось выполнить {operation_name} после {max_retries} попыток")
    
    @staticmethod
    async def _execute_with_retry_async(
        operation: Callable[[], T],
        max_retries: int,
        operation_name: str,
        context_info: Optional[dict]
    ) -> T:
        """Внутренняя асинхронная реализация retry логики"""
        last_error = None
        last_error_message = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # Выполняем асинхронную операцию
                result = await operation()
                return result
            except RuntimeError as e:
                error_message = str(e)
                # Получаем информацию об ошибке из res.error если доступна
                res_error = getattr(e, 'res_error', None) if hasattr(e, 'res_error') else None
                error_to_check = res_error if res_error else error_message
                
                # Проверяем, нужно ли эскалировать ошибку менеджеру (без retry)
                if ErrorChecker.should_escalate_to_manager(error_to_check) or ErrorChecker.should_escalate_to_manager(error_message):
                    logger.error(
                        f"{operation_name}: обнаружена ошибка, требующая эскалации менеджеру. "
                        f"Вызываем CallManager без retry."
                    )
                    
                    # Извлекаем информацию из контекста для CallManager
                    chat_id = context_info.get('chat_id') if context_info else None
                    message = context_info.get('message') if context_info else None
                    agent_name = context_info.get('agent_name') if context_info else operation_name
                    
                    # Вызываем CallManager и получаем результат эскалации
                    escalation_result = CallManagerService.handle_critical_error(
                        error_message=error_to_check or error_message,
                        agent_name=agent_name,
                        message=message or "Не указано",
                        chat_id=chat_id
                    )
                    # Выбрасываем специальное исключение с результатом эскалации
                    # Это исключение будет обработано на нижнем уровне (bot)
                    raise CallManagerException(escalation_result)
                
                # Проверяем, является ли это InternalServerError
                if ErrorChecker.is_internal_server_error(error_to_check):
                    last_error = e
                    last_error_message = error_to_check
                    
                    logger.warning(
                        f"Попытка {attempt}/{max_retries} для {operation_name}: "
                        f"InternalServerError - повторяем операцию"
                    )
                    
                    if attempt < max_retries:
                        continue
                    else:
                        # После всех неудачных попыток вызываем CallManager
                        logger.error(
                            f"{operation_name}: все {max_retries} попытки завершились "
                            f"InternalServerError. Вызываем CallManager."
                        )
                        
                        # Извлекаем информацию из контекста для CallManager
                        chat_id = context_info.get('chat_id') if context_info else None
                        message = context_info.get('message') if context_info else None
                        agent_name = context_info.get('agent_name') if context_info else operation_name
                        
                        # Вызываем CallManager и получаем результат эскалации
                        escalation_result = CallManagerService.handle_critical_error(
                            error_message=last_error_message or error_message,
                            agent_name=agent_name,
                            message=message or "Не указано",
                            chat_id=chat_id
                        )
                        # Выбрасываем специальное исключение с результатом эскалации
                        # Это исключение будет обработано на нижнем уровне (bot)
                        raise CallManagerException(escalation_result)
                else:
                    # Если это не InternalServerError, сразу выбрасываем исключение
                    raise
            except Exception as e:
                # Для других типов ошибок не делаем retry
                raise
        
        # Если дошли сюда (не должно произойти, но на всякий случай)
        if last_error:
            raise last_error
        raise RuntimeError(f"Не удалось выполнить {operation_name} после {max_retries} попыток")

