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
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
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

try:
    from src.api.models import ChatRequest, WebChatResponse
    from src.api.chat_utils import create_virtual_user, create_virtual_message
    from src.handlers.telegram_handlers import get_admin_service
    from src.services.date_normalizer import normalize_dates_in_text
    from src.services.time_normalizer import normalize_times_in_text
    from src.services.link_converter import convert_yclients_links_in_text
    from src.services.text_formatter import convert_bold_markdown_to_html
    print("✅ chat endpoint модули импортированы", flush=True)
except Exception as e:
    print(f"❌ Ошибка импорта chat endpoint модулей: {e}", flush=True)
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

# Настраиваем CORS для веб-запросов (максимально разрешающий для отладки)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # Разрешить ВСЕ домены (более мощный аналог "*")
    allow_credentials=True,   # Разрешить куки и авторизацию
    allow_methods=["*"],      # Разрешить любые методы (POST, GET, OPTIONS и т.д.)
    allow_headers=["*"],      # Разрешить любые заголовки
    expose_headers=["*"],      # Разрешить доступ к любым заголовкам ответа
)

# Middleware для логирования всех запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирует все входящие запросы"""
    method = request.method
    path = request.url.path
    
    # Для POST запросов логируем тело
    if method == "POST" and path == "/chat":
        try:
            body = await request.body()
            body_str = body.decode('utf-8') if body else "empty"
            print(f"🌐 [REQUEST] {method} {path} | Body: {body_str[:200]}", flush=True)
            logger.info(f"🌐 [REQUEST] {method} {path} | Body: {body_str[:200]}")
        except Exception as e:
            print(f"🌐 [REQUEST] {method} {path} | Error reading body: {e}", flush=True)
    else:
        print(f"🌐 [REQUEST] {method} {path}", flush=True)
        logger.info(f"🌐 [REQUEST] {method} {path}")
    
    response = await call_next(request)
    return response

# Обработчик ошибок валидации Pydantic
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обрабатывает ошибки валидации запросов"""
    error_msg = f"Ошибка валидации запроса: {exc.errors()}"
    print(f"❌ [VALIDATION] {error_msg}", flush=True)
    logger.error(f"Ошибка валидации запроса: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(await request.body())}
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

@app.get("/chat/test", tags=["Chat"])
async def chat_test():
    """Тестовый endpoint для проверки доступности /chat"""
    print("✅ [CHAT] Тестовый запрос GET /chat/test получен", flush=True)
    return {"status": "OK", "message": "Chat endpoint is available"}

@app.options("/chat", tags=["Chat"])
async def chat_options_handler():
    """Принудительный обработчик CORS preflight запросов"""
    print("✅ [CHAT] Ручной OPTIONS запрос обработан", flush=True)
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "*",
        },
        status_code=200
    )

@app.post("/chat", tags=["Chat"], response_model=WebChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Эндпоинт для обработки сообщений от веб-фронтенда.
    
    Обрабатывает сообщения от пользователя и возвращает ответы от AI-агента.
    Поддерживает отправку сообщений в админ-панель и проверку CallManager.
    """
    try:
        # Логируем в stdout для гарантированной видимости
        print(f"📨 [CHAT] Получен POST запрос /chat", flush=True)
        logger.info("📨 [CHAT] Получен POST запрос /chat")
        
        message_text = request.message
        thread_id = request.thread_id
        
        print(f"📨 [CHAT] thread_id={thread_id}, message_length={len(message_text)}", flush=True)
        logger.info(f"Получен запрос /chat: thread_id={thread_id}, message_length={len(message_text)}")
        
        # Создаем виртуального пользователя из thread_id
        virtual_user = create_virtual_user(thread_id)
        user_id = virtual_user.id
        
        # Получаем сервисы
        agent_service = get_agent_service()
        application = get_application()
        admin_service = None
        
        if application:
            admin_service = get_admin_service(application.bot)
        
        # Отправляем сообщение пользователя в админ-панель (если настроено)
        if admin_service:
            try:
                virtual_message = create_virtual_message(message_text, virtual_user)
                await admin_service.forward_message_to_admin(
                    user=virtual_user,
                    message=virtual_message,
                    source="User",
                )
            except Exception as e:
                logger.warning("Не удалось отправить сообщение пользователя в админ-панель: %s", str(e))
        
        # Обрабатываем сообщение через агента
        # Используем thread_id как chat_id для сохранения истории (как в Telegram используется chat_id)
        print(f"🤖 [CHAT] Отправляю сообщение агенту: thread_id={thread_id}", flush=True)
        agent_response = await agent_service.send_to_agent(thread_id, message_text)
        print(f"✅ [CHAT] Получен ответ от агента", flush=True)
        
        # Извлекаем ответ
        if isinstance(agent_response, dict):
            user_message_text = agent_response.get("user_message", "")
            manager_alert = agent_response.get("manager_alert")
        else:
            user_message_text = str(agent_response)
            manager_alert = None
        
        # Нормализуем даты и время в ответе
        user_message_text = normalize_dates_in_text(user_message_text)
        user_message_text = normalize_times_in_text(user_message_text)
        user_message_text = convert_yclients_links_in_text(user_message_text)
        user_message_text = convert_bold_markdown_to_html(user_message_text)
        
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
        if manager_alert:
            logger.info(f"CallManager был вызван для thread_id={thread_id}")
            if admin_service:
                try:
                    # Нормализуем manager_alert
                    manager_alert = normalize_dates_in_text(manager_alert)
                    manager_alert = normalize_times_in_text(manager_alert)
                    manager_alert = convert_yclients_links_in_text(manager_alert)
                    manager_alert = convert_bold_markdown_to_html(manager_alert)
                    
                    # Отправляем уведомление в админ-панель
                    await admin_service.send_call_manager_notification(
                        user=virtual_user,
                        reason="Вызов менеджера через CallManager",
                        recent_messages=[],
                    )
                except Exception as e:
                    logger.warning("Не удалось отправить уведомление CallManager в админ-панель: %s", str(e))
        
        # Возвращаем ответ
        print(f"📤 [CHAT] Отправляю ответ клиенту, длина: {len(user_message_text)}", flush=True)
        return WebChatResponse(response=user_message_text)
        
    except Exception as e:
        error_msg = f"Ошибка при обработке /chat endpoint: {e}"
        print(f"❌ [CHAT] {error_msg}", flush=True)
        import traceback
        print(f"❌ [CHAT] Traceback:\n{traceback.format_exc()}", flush=True)
        logger.error(error_msg, exc_info=True)
        # Возвращаем ошибку пользователю
        error_message = f"Ошибка при обработке сообщения: {str(e)}"
        return WebChatResponse(response=error_message)

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
