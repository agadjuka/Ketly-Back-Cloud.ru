"""
Обработчик веб-хуков
"""
from fastapi import Request
from telegram import Update

from src.services.logger_service import logger
from src.telegram_app import get_application, process_telegram_update


async def webhook(request: Request):
    """Обработчик webhook от Telegram - ожидает завершения обработки"""
    application = get_application()
    
    try:
        if not application:
            logger.error("Приложение Telegram не инициализировано")
            return {"ok": False, "error": "Application not initialized"}
        
        data = await request.json()
        update = Update.de_json(data, application.bot)
        
        # ОЖИДАЕМ завершения обработки (как в рабочем проекте)
        # Event loop не блокируется, т.к. операции внутри асинхронные
        await process_telegram_update(update)
        
        # Возвращаем ответ только после полной обработки
        return {"ok": True}
    except Exception as e:
        logger.error("Ошибка при обработке webhook: %s", str(e))
        return {"ok": False, "error": str(e)}


async def root_post(request: Request):
    """
    POST обработчик для корневого пути.
    Может обрабатывать как обычные запросы, так и Telegram webhook.
    Ожидает завершения обработки для Telegram updates.
    """
    try:
        # Пытаемся обработать как Telegram webhook
        data = await request.json()
        
        # Проверяем, что это Telegram update
        if "message" in data or "callback_query" in data:
            application = get_application()
            if not application:
                return {"status": "OK", "error": "Application not initialized"}
            
            update = Update.de_json(data, application.bot)
            # ОЖИДАЕМ завершения обработки (как в рабочем проекте)
            await process_telegram_update(update)
            return {"status": "ok"}
        else:
            # Если это не Telegram update, возвращаем обычный ответ
            return {
                "status": "OK",
                "message": "Looktown Bot is running",
                "version": "0.1.0"
            }
    except Exception as e:
        logger.error(f"❌ Ошибка обработки POST запроса: {e}")
        # В случае ошибки возвращаем обычный ответ
        return {
            "status": "OK",
            "message": "Looktown Bot is running",
            "version": "0.1.0"
        }
