import os
import sys

# Настройка event loop policy для Windows (нужно для psycopg)
# Должно быть ДО любых импортов, которые используют asyncio
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Ранние логи ДО любых импортов
print("=" * 60, flush=True)
print("🚀 НАЧАЛО ИМПОРТА МОДУЛЕЙ", flush=True)
print("=" * 60, flush=True)

try:
    from dotenv import load_dotenv
    print("✅ dotenv импортирован", flush=True)
except Exception as e:
    print(f"❌ Ошибка импорта dotenv: {e}", flush=True)
    sys.exit(1)

load_dotenv()
print("✅ .env загружен", flush=True)

try:
    from fastapi import FastAPI, Request
    print("✅ FastAPI импортирован", flush=True)
except Exception as e:
    print(f"❌ Ошибка импорта FastAPI: {e}", flush=True)
    sys.exit(1)

try:
    from service_factory import get_agent_service
    print("✅ service_factory импортирован", flush=True)
except Exception as e:
    print(f"❌ Ошибка импорта service_factory: {e}", flush=True)
    sys.exit(1)

try:
    from src.services.logger_service import logger
    print("✅ logger импортирован", flush=True)
except Exception as e:
    print(f"❌ Ошибка импорта logger: {e}", flush=True)
    sys.exit(1)

try:
    from src.telegram_app import setup_application, set_bot_commands, get_application
    print("✅ telegram_app импортирован", flush=True)
except Exception as e:
    print(f"❌ Ошибка импорта telegram_app: {e}", flush=True)
    sys.exit(1)

try:
    from src.api.webhook import webhook, root_post
    print("✅ webhook импортирован", flush=True)
except Exception as e:
    print(f"❌ Ошибка импорта webhook: {e}", flush=True)
    sys.exit(1)

print("✅ ВСЕ ИМПОРТЫ УСПЕШНЫ", flush=True)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/webhook')

# Создаем FastAPI приложение
app = FastAPI(
    title="Looktown Bot",
    version="0.1.0"
)

@app.on_event("startup")
async def startup_event():
    """Выполняется при запуске приложения"""
    # Логируем в stdout для гарантированной видимости
    print("╔═══════════════════════════════════════════════════════════", flush=True)
    print("║ 🚀 FastAPI startup: Приложение запускается...", flush=True)
    print("╚═══════════════════════════════════════════════════════════", flush=True)
    
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ 🚀 Приложение запускается...")
    logger.info("╚═══════════════════════════════════════════════════════════")
    
    # При локальной разработке используем переменные окружения
    # В контейнерах cloud.ru переменные передаются автоматически
    print("✅ Конфигурация загружена", flush=True)
    
    # Настраиваем приложение Telegram
    try:
        print("🔧 Настройка приложения Telegram...", flush=True)
        application = setup_application(TELEGRAM_TOKEN)
        print("✅ Приложение Telegram настроено", flush=True)
        
        # Инициализируем и запускаем приложение Telegram (без polling)
        print("🚀 Инициализация Telegram приложения...", flush=True)
        await application.initialize()
        await application.start()
        print("✅ Приложение Telegram запущено", flush=True)
        
        # Устанавливаем команды бота
        try:
            await set_bot_commands(application.bot)
            print("✅ Команды бота установлены", flush=True)
        except Exception as e:
            print(f"⚠️ Ошибка при установке команд бота: {e}", flush=True)
            logger.warning("Ошибка при установке команд бота: %s", str(e))
        
        logger.success("✅ Приложение Telegram запущено")
    except Exception as e:
        error_msg = f"❌ Ошибка при запуске приложения Telegram: {e}"
        print(error_msg, flush=True)
        import traceback
        tb = traceback.format_exc()
        print(f"Трассировка:\n{tb}", flush=True)
        logger.error(error_msg)
        logger.error(f"Трассировка:\n{tb}")
        # НЕ делаем raise - пусть приложение запустится даже с ошибкой
        # raise
    
    # Настраиваем webhook
    application = get_application()
    if application and WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
        try:
            await application.bot.set_webhook(url=webhook_url)
            logger.success(f"✅ Webhook установлен: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Ошибка при установке webhook: {str(e)}")
            logger.warning("⚠️ Бот будет работать, но обновления не будут приходить до установки webhook")
    else:
        logger.warning("⚠️ WEBHOOK_URL не задан, webhook не установлен")
        logger.info("💡 Webhook будет установлен автоматически через GitHub Actions или вручную")
    
    # Проверяем подключение к PostgreSQL при старте (lazy инициализация при первом запросе)
    try:
        logger.info("🔍 Проверка сервисов...")
        get_agent_service()
        logger.success("✅ Все сервисы готовы")
    except Exception as e:
        logger.warning(f"⚠️ Предупреждение при инициализации сервисов: {str(e)}")
        import traceback
        logger.warning(f"Детали ошибки:\n{traceback.format_exc()}")
        logger.warning("⚠️ Сервисы будут инициализированы при первом запросе")

@app.on_event("shutdown")
async def shutdown_event():
    """Выполняется при остановке приложения"""
    logger.info("🛑 Остановка бота...")
    application = get_application()
    if application:
        try:
            await application.stop()
            await application.shutdown()
            if WEBHOOK_URL:
                await application.bot.delete_webhook()
        except Exception as e:
            logger.warning(f"Ошибка при остановке: {str(e)}")
    logger.success("✅ Бот остановлен")

@app.get("/", tags=["Root"])
def root():
    """Корневой эндпоинт для проверки доступности сервиса"""
    return {
        "status": "OK",
        "message": "Looktown Bot is running",
        "version": "0.1.0",
        "service": "telegram-bot"
    }

@app.get("/health", tags=["Health Check"])
@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """Простой эндпоинт для проверки работоспособности сервиса"""
    return {
        "status": "OK",
        "service": "telegram-bot",
        "webhook": "enabled" if WEBHOOK_URL else "pending"
    }

# Регистрация эндпоинтов из webhook.py
@app.post(WEBHOOK_PATH, tags=["Telegram"])
async def webhook_handler(request: Request):
    """Обработчик webhook от Telegram"""
    return await webhook(request)

@app.post("/", tags=["Root"])
async def root_post_handler(request: Request):
    """POST обработчик для корневого пути"""
    return await root_post(request)

if __name__ == '__main__':
    import uvicorn
    
    # Проверяем обязательные переменные окружения
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не задан в переменных окружения")
        sys.exit(1)
    
    # Получаем хост и порт (для локального запуска)
    host = os.getenv('WEBAPP_HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8080'))  # В контейнере порт фиксированный 8080
    
    logger.info(f"🚀 Запуск FastAPI сервера на {host}:{port}")
    print(f"🚀 Запуск FastAPI на {host}:{port}", flush=True)
    
    # Запускаем через uvicorn
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info"
    )
