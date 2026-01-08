"""
Обработчики административных команд
"""
from telegram import Update
from telegram.ext import ContextTypes

from src.config.admin_config import get_telegram_admin_group_id
from src.services.logger_service import logger
from src.storage import get_topic_storage
from src.services.admin_service import AdminPanelService

# Глобальная переменная для админ-панели
_admin_service = None


def _get_admin_service(bot):
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


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает сообщения от админов в админской группе."""
    if not update.message:
        return

    message = update.message
    chat_id = update.effective_chat.id
    admin_group_id = get_telegram_admin_group_id()

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
    admin_group_id = get_telegram_admin_group_id()

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
    admin_group_id = get_telegram_admin_group_id()

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

