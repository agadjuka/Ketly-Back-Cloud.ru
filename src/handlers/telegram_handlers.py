"""
Обработчики Telegram сообщений
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from service_factory import get_agent_service
from src.services.logger_service import logger
from src.services.date_normalizer import normalize_dates_in_text
from src.services.time_normalizer import normalize_times_in_text
from src.services.link_converter import convert_yclients_links_in_text
from src.services.text_formatter import convert_bold_markdown_to_html
from src.services.retry_service import RetryService
from src.services.call_manager_service import CallManagerException
from src.services.escalation_service import EscalationService
from src.config.admin_config import get_telegram_admin_group_id
from src.storage import get_topic_storage
from src.services.admin_service import AdminPanelService

# Глобальная переменная для админ-панели
_admin_service = None


def get_admin_service(bot):
    """Получает или создает экземпляр AdminPanelService."""
    global _admin_service
    if _admin_service is None:
        admin_group_id = get_telegram_admin_group_id()
        if admin_group_id is None:
            logger.debug("Админ-панель не настроена (TELEGRAM_ADMIN_GROUP_ID не установлен)")
            return None

        try:
            storage = get_topic_storage()
            _admin_service = AdminPanelService(
                bot=bot,
                storage=storage,
                admin_group_id=admin_group_id,
            )
            logger.debug("Инициализирован AdminPanelService")
        except Exception as e:
            logger.warning("Не удалось инициализировать AdminPanelService: %s", str(e))
            return None

    return _admin_service


async def send_to_agent(message_text, chat_id):
    """Отправка сообщения агенту через LangGraph с retry на нижнем уровне"""
    async def _execute_agent_request():
        """Внутренняя функция для выполнения запроса к агенту"""
        logger.agent("Обработка сообщения", chat_id)
        agent_service = get_agent_service()
        response = await agent_service.send_to_agent(chat_id, message_text)
        logger.agent("Ответ получен", chat_id)
        return response
    
    try:
        # Используем RetryService для retry на нижнем уровне (async версия)
        response = await RetryService.execute_with_retry_async(
            operation=_execute_agent_request,
            max_retries=3,
            operation_name="отправка сообщения агенту",
            context_info={
                "chat_id": chat_id,
                "message": message_text
            }
        )
        return response
    except CallManagerException as e:
        # Обрабатываем вызов CallManager - возвращаем результат эскалации
        logger.info("CallManager был вызван из-за критической ошибки")
        return e.escalation_result
    except Exception as e:
        logger.error("Ошибка при обращении к агенту", str(e))
        return {"user_message": f"Ошибка при обращении к агенту: {str(e)}"}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    chat_id = str(update.effective_chat.id)
    logger.telegram("Команда /start", chat_id)
    await update.message.reply_text('Добрый день!\nНа связи менеджер LOOKTOWN 🌻\n\nЧем я могу вам помочь?')


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /new - сброс контекста"""
    chat_id = str(update.effective_chat.id)
    logger.telegram("Команда /new", chat_id)
    try:
        agent_service = get_agent_service()
        await agent_service.reset_context(chat_id)
        logger.success("Контекст сброшен", chat_id)
        await update.message.reply_text('Контекст сброшен. Начинаем новый диалог!')
    except Exception as e:
        logger.error("Ошибка при сбросе контекста", str(e))
        await update.message.reply_text(f'Ошибка при сбросе контекста: {str(e)}')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_message = update.message.text
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    logger.telegram("Получено сообщение", chat_id)
    
    # Получаем админ-сервис
    admin_service = get_admin_service(context.bot)
    
    # Отправляем сообщение пользователя в админ-панель (если настроено)
    if admin_service and update.effective_user and update.message:
        try:
            await admin_service.forward_message_to_admin(
                user=update.effective_user,
                message=update.message,
                source="User",
            )
        except Exception as e:
            logger.warning("Не удалось отправить сообщение пользователя в админ-панель: %s", str(e))
    
    # Проверяем режим работы: если ручной режим, прерываем выполнение
    if admin_service:
        if admin_service.is_user_in_manual_mode(user_id):
            logger.info("Пользователь user_id=%s в ручном режиме. ИИ пропускает обработку сообщения.", user_id)
            return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    agent_response = await send_to_agent(user_message, chat_id)
    # Ожидаем словарь: {"user_message": str, "manager_alert": Optional[str]}
    user_message_text = agent_response.get("user_message") if isinstance(agent_response, dict) else str(agent_response)
    
    # Проверяем на эскалацию [CALL_MANAGER] перед отправкой в Telegram
    if user_message_text and user_message_text.strip().startswith('[CALL_MANAGER]'):
        escalation_service = EscalationService()
        escalation_result = escalation_service.handle(user_message_text, chat_id)
        user_message_text = escalation_result.get("user_message", user_message_text)
        # Обновляем agent_response с результатом эскалации
        agent_response = {
            "user_message": user_message_text,
            "manager_alert": escalation_result.get("manager_alert")
        }
    
    # Нормализуем даты и время в ответе
    user_message_text = normalize_dates_in_text(user_message_text)
    user_message_text = normalize_times_in_text(user_message_text)
    # Преобразуем ссылки yclients.com в HTML-гиперссылки
    user_message_text = convert_yclients_links_in_text(user_message_text)
    # Заменяем Markdown жирный текст (**текст**) на HTML теги (<b>текст</b>)
    user_message_text = convert_bold_markdown_to_html(user_message_text)
    await update.message.reply_text(user_message_text, parse_mode=ParseMode.HTML)

    # Отправляем ответ AI в админ-панель (если настроено)
    if admin_service:
        try:
            await admin_service.send_ai_response_to_topic(
                user_id=user_id,
                ai_text=user_message_text,
            )
        except Exception as e:
            logger.warning("Не удалось отправить ответ AI в админ-панель: %s", str(e))

    # Обработка уведомления CallManager
    if isinstance(agent_response, dict) and agent_response.get("manager_alert"):
        manager_alert = normalize_dates_in_text(agent_response["manager_alert"])
        manager_alert = normalize_times_in_text(manager_alert)
        manager_alert = convert_yclients_links_in_text(manager_alert)
        manager_alert = convert_bold_markdown_to_html(manager_alert)
        
        # Отправляем уведомление в админ-панель (если настроено)
        if admin_service and update.effective_user:
            try:
                # Получаем историю сообщений для уведомления
                # Пока используем упрощенную версию - только причину из manager_alert
                reason = "Вызов менеджера через CallManager"
                recent_messages = []  # Пока пустой список, можно расширить позже
                
                await admin_service.send_call_manager_notification(
                    user=update.effective_user,
                    reason=reason,
                    recent_messages=recent_messages,
                )
            except Exception as e:
                logger.warning("Не удалось отправить уведомление CallManager в админ-панель: %s", str(e))
                # Fallback: отправляем через старый метод
                try:
                    await update.message.reply_text(manager_alert, parse_mode=ParseMode.HTML)
                except Exception as e2:
                    logger.warning(f"Ошибка при отправке manager_alert с HTML: {e2}, отправляю без форматирования")
                    await update.message.reply_text(manager_alert, parse_mode=None)
        else:
            # Если админ-панель не настроена, используем старый метод
            try:
                await update.message.reply_text(manager_alert, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.warning(f"Ошибка при отправке manager_alert с HTML: {e}, отправляю без форматирования")
                await update.message.reply_text(manager_alert, parse_mode=None)
    
    logger.telegram("Ответ отправлен", chat_id)

