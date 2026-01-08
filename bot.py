import os
import sys

# Настройка event loop policy для Windows (нужно для psycopg)
# Должно быть ДО любых импортов, которые используют asyncio
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TimedOut
from service_factory import get_agent_service
from src.services.logger_service import logger
from src.services.date_normalizer import normalize_dates_in_text
from src.services.time_normalizer import normalize_times_in_text
from src.services.link_converter import convert_yclients_links_in_text
from src.services.text_formatter import convert_bold_markdown_to_html
from src.services.retry_service import RetryService
from src.services.call_manager_service import CallManagerException
from src.services.escalation_service import EscalationService

try:
    from src.config.admin_config import get_telegram_admin_group_id
    from src.storage import get_topic_storage
    from src.services.admin_service import AdminPanelService
except Exception as e:
    logger.warning(f"Админ-панель недоступна: {e}")

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Глобальная переменная для админ-панели
_admin_service = None

def _get_admin_service(bot):
    """Получает или создает экземпляр AdminPanelService."""
    global _admin_service
    if _admin_service is None:
        try:
            admin_group_id = get_telegram_admin_group_id()
            if admin_group_id is None:
                logger.debug("Админ-панель не настроена (TELEGRAM_ADMIN_GROUP_ID не установлен)")
                return None

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
    admin_service = _get_admin_service(context.bot)
    
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
    
    # Пытаемся показать индикатор печати, но не критично, если не получится
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except TimedOut:
        logger.warning("Таймаут при отправке send_chat_action, продолжаем обработку", chat_id)
    except Exception as e:
        logger.warning(f"Ошибка при отправке send_chat_action: {e}, продолжаем обработку", chat_id)
    
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

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает сообщения от админов в админской группе."""
    if not update.message:
        return

    message = update.message
    chat_id = update.effective_chat.id
    try:
        admin_group_id = get_telegram_admin_group_id()
    except:
        return

    if admin_group_id is None or chat_id != admin_group_id:
        return
    if message.message_thread_id is None:
        return
    if message.from_user and message.from_user.is_bot:
        return
    if message.text and message.text.startswith("/"):
        return

    topic_id = message.message_thread_id

    try:
        admin_service = _get_admin_service(context.bot)
        if admin_service is None:
            logger.warning("AdminPanelService не инициализирован. Сообщение не будет обработано.")
            return

        user_id = admin_service.storage.get_user_id(topic_id)
        if user_id is None:
            logger.warning("Не найден user_id для topic_id=%s. Сообщение не будет переслано.", topic_id)
            return

        mode = admin_service.storage.get_mode(user_id)

        if mode == "auto":
            await context.bot.send_message(
                chat_id=admin_group_id,
                text="⚠️ Включен автоматический режим. Сообщение не переслано клиенту.\n"
                     "Используйте команду /manager для переключения в ручной режим.",
                message_thread_id=topic_id,
                reply_to_message_id=message.message_id,
            )
        else:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=admin_group_id,
                message_id=message.message_id,
            )
    except Exception as e:
        logger.error("Ошибка при пересылке сообщения от админа: %s", str(e), exc_info=True)

async def handle_manager_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /manager для включения ручного режима."""
    if not update.message:
        return

    message = update.message
    chat_id = update.effective_chat.id
    try:
        admin_group_id = get_telegram_admin_group_id()
    except:
        return

    if admin_group_id is None or chat_id != admin_group_id:
        return
    if message.message_thread_id is None:
        return

    topic_id = message.message_thread_id

    try:
        admin_service = _get_admin_service(context.bot)
        if admin_service is None:
            logger.warning("AdminPanelService не инициализирован. Команда /manager не выполнена.")
            return

        await admin_service.enable_manual_mode(topic_id)
    except Exception as e:
        logger.error("Ошибка при выполнении команды /manager: %s", str(e), exc_info=True)

async def handle_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /bot для включения автоматического режима."""
    if not update.message:
        return

    message = update.message
    chat_id = update.effective_chat.id
    try:
        admin_group_id = get_telegram_admin_group_id()
    except:
        return

    if admin_group_id is None or chat_id != admin_group_id:
        return
    if message.message_thread_id is None:
        return

    topic_id = message.message_thread_id

    try:
        admin_service = _get_admin_service(context.bot)
        if admin_service is None:
            logger.warning("AdminPanelService не инициализирован. Команда /bot не выполнена.")
            return

        await admin_service.enable_auto_mode(topic_id)
    except Exception as e:
        logger.error("Ошибка при выполнении команды /bot: %s", str(e), exc_info=True)

async def set_bot_commands(bot) -> None:
    """Устанавливает команды бота для разных групп пользователей."""
    try:
        from telegram import BotCommand
        try:
            from telegram import BotCommandScopeChat, BotCommandScopeDefault
        except ImportError:
            try:
                from telegram.constants import BotCommandScopeChat, BotCommandScopeDefault
            except ImportError:
                from telegram.helpers import BotCommandScopeChat, BotCommandScopeDefault
        
        default_commands = [BotCommand("new", "Сбросить историю переписки")]
        await bot.set_my_commands(commands=default_commands, scope=BotCommandScopeDefault())
        
        try:
            admin_group_id = get_telegram_admin_group_id()
            if admin_group_id is not None:
                admin_commands = [
                    BotCommand("manager", "👨‍💻 Включить ручной режим"),
                    BotCommand("bot", "🤖 Включить авто-режим ИИ"),
                ]
                await bot.set_my_commands(
                    commands=admin_commands,
                    scope=BotCommandScopeChat(chat_id=admin_group_id),
                )
        except:
            pass
    except Exception as e:
        logger.error("Ошибка при установке команд бота: %s", str(e), exc_info=True)

def main():
    """Основная функция запуска бота"""
    logger.info("🚀 Запуск бота с LangGraph")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_chat))
    
    # Обработчики для админ-панели
    try:
        admin_group_id = get_telegram_admin_group_id()
        if admin_group_id is not None:
            admin_chat_filter = filters.Chat(chat_id=admin_group_id)
            application.add_handler(
                CommandHandler("manager", handle_manager_command, filters=admin_chat_filter)
            )
            application.add_handler(
                CommandHandler("bot", handle_bot_command, filters=admin_chat_filter)
            )
            application.add_handler(
                MessageHandler(admin_chat_filter & ~filters.COMMAND, handle_admin_message)
            )
    except:
        pass
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Устанавливаем команды бота после инициализации
    async def post_init(app: Application) -> None:
        await set_bot_commands(app.bot)
    
    application.post_init = post_init
    
    logger.success("✅ Бот запущен и готов к работе")
    application.run_polling()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")