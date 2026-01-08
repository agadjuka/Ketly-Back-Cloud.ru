"""
Основной модуль Telegram приложения
"""
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.services.logger_service import logger
from src.config.admin_config import get_telegram_admin_group_id
from src.handlers.telegram_handlers import start, new_chat, handle_message
from src.handlers.admin_handlers import handle_admin_message, handle_manager_command, handle_bot_command

# Глобальная переменная для приложения Telegram
application: Application = None


def setup_application(telegram_token: str) -> Application:
    """Настройка приложения Telegram"""
    global application
    
    if not telegram_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в переменных окружения")
    
    logger.info("🚀 Инициализация бота с LangGraph")
    
    application = Application.builder().token(telegram_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_chat))
    
    # Обработчики для админ-панели
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
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.success("✅ Бот инициализирован и готов к работе")
    
    return application


async def set_bot_commands(bot) -> None:
    """Устанавливает команды бота для разных групп пользователей."""
    try:
        try:
            from telegram import BotCommandScopeChat, BotCommandScopeDefault
        except ImportError:
            try:
                from telegram.constants import BotCommandScopeChat, BotCommandScopeDefault
            except ImportError:
                from telegram.helpers import BotCommandScopeChat, BotCommandScopeDefault
        
        default_commands = [BotCommand("new", "Сбросить историю переписки")]
        await bot.set_my_commands(commands=default_commands, scope=BotCommandScopeDefault())
        
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
    except Exception as e:
        logger.error("Ошибка при установке команд бота: %s", str(e), exc_info=True)


async def process_telegram_update(update):
    """Обработка Telegram update"""
    global application
    if not application:
        logger.error("Приложение Telegram не инициализировано")
        return
    
    await application.process_update(update)


def get_application() -> Application:
    """Получить глобальный экземпляр приложения Telegram"""
    return application
