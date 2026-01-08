"""Модуль для работы с PostgreSQL Checkpointer для LangGraph"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import psycopg
from ..services.logger_service import logger

# Флаг для отслеживания, был ли выполнен setup
_setup_completed = False


async def initialize_checkpointer_tables():
    """
    Инициализирует таблицы для checkpointer один раз при старте приложения.
    Должна быть вызвана один раз при запуске приложения, вне транзакций.
    
    Эта функция создает таблицы и индексы для LangGraph Checkpointer.
    """
    global _setup_completed
    
    if _setup_completed:
        logger.debug("Таблицы checkpointer уже инициализированы")
        return
    
    connection_string = _get_connection_string()
    pool: AsyncConnectionPool | None = None
    
    try:
        logger.info("Инициализация таблиц для LangGraph Checkpointer...")
        print("🔧 Инициализация таблиц для LangGraph Checkpointer...", flush=True)
        
        # Создаем временный пул соединений для инициализации
        pool = AsyncConnectionPool(conninfo=connection_string, open=False)
        await pool.open()
        
        # Создаем экземпляр checkpointer
        checkpointer = AsyncPostgresSaver(pool)
        
        # Вызываем setup() для создания таблиц
        await checkpointer.setup()
        
        _setup_completed = True
        logger.info("✅ Таблицы и индексы для LangGraph Checkpointer успешно созданы")
        print("✅ Таблицы для LangGraph Checkpointer успешно созданы", flush=True)
        
    except Exception as e:
        error_str = str(e)
        
        # Игнорируем ошибки, если таблицы уже существуют
        if "already exists" in error_str.lower() or "duplicate" in error_str.lower():
            logger.info("Таблицы уже существуют, инициализация не требуется")
            print("ℹ️ Таблицы уже существуют, инициализация не требуется", flush=True)
            _setup_completed = True
        elif "CONCURRENTLY" in error_str and "transaction" in error_str.lower():
            # Ошибка CONCURRENTLY - это известная проблема, но таблицы могут быть созданы частично
            logger.warning(f"⚠️ Предупреждение при инициализации (CONCURRENTLY): {e}")
            logger.warning("Таблицы могут быть созданы частично. Проверьте вручную.")
            print(f"⚠️ Предупреждение: {e}", flush=True)
            # Устанавливаем флаг, чтобы не блокировать работу
            _setup_completed = True
        else:
            logger.error(f"Ошибка при инициализации таблиц checkpointer: {e}")
            print(f"❌ Ошибка при инициализации таблиц: {e}", flush=True)
            raise
    finally:
        # Закрываем пул соединений
        if pool is not None:
            try:
                await pool.close()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии пула при инициализации: {e}")


def _get_connection_string() -> str:
    """Получить строку подключения к PostgreSQL из переменных окружения"""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    database = os.getenv("PG_DB", "ai_db")
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


async def clear_thread_memory(thread_id: str) -> None:
    """
    Полностью очищает память для конкретного thread_id из базы данных PostgreSQL.
    
    Удаляет все записи из таблиц checkpointer для указанного thread_id:
    - checkpoint_writes
    - checkpoint_blobs
    - checkpoints
    
    Args:
        thread_id: Идентификатор треда (chat_id или UUID сессии)
        
    Raises:
        Exception: При ошибках подключения или выполнения SQL-запросов
    """
    connection_string = _get_connection_string()
    
    try:
        logger.info(f"Очистка памяти для thread_id={thread_id}")
        
        # Подключаемся к БД с autocommit=True для выполнения DELETE
        async with await psycopg.AsyncConnection.connect(connection_string, autocommit=True) as conn:
            # Удаляем записи в правильном порядке (с учетом возможных Foreign Keys)
            # Порядок: сначала зависимые таблицы, потом основная
            
            # 1. Удаляем checkpoint_writes
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = %s",
                    (thread_id,)
                )
                deleted_writes = cur.rowcount
                logger.debug(f"Удалено записей из checkpoint_writes: {deleted_writes}")
            
            # 2. Удаляем checkpoint_blobs
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM checkpoint_blobs WHERE thread_id = %s",
                    (thread_id,)
                )
                deleted_blobs = cur.rowcount
                logger.debug(f"Удалено записей из checkpoint_blobs: {deleted_blobs}")
            
            # 3. Удаляем checkpoints (основная таблица)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM checkpoints WHERE thread_id = %s",
                    (thread_id,)
                )
                deleted_checkpoints = cur.rowcount
                logger.debug(f"Удалено записей из checkpoints: {deleted_checkpoints}")
            
            logger.info(
                f"Память очищена для thread_id={thread_id}: "
                f"checkpoints={deleted_checkpoints}, "
                f"checkpoint_writes={deleted_writes}, "
                f"checkpoint_blobs={deleted_blobs}"
            )
        
    except Exception as e:
        logger.error(f"Ошибка при очистке памяти для thread_id={thread_id}: {e}", exc_info=True)
        raise


@asynccontextmanager
async def get_postgres_checkpointer() -> AsyncGenerator[AsyncPostgresSaver, None]:
    """
    Асинхронный контекстный менеджер для получения AsyncPostgresSaver.
    
    Создает пул соединений и инициализирует checkpointer.
    Таблицы должны быть созданы вручную через SQL.
    
    Yields:
        AsyncPostgresSaver: Экземпляр checkpointer для LangGraph
        
    Raises:
        Exception: При ошибках подключения
        
    Example:
        async with get_postgres_checkpointer() as checkpointer:
            # Использование checkpointer
            graph = graph.compile(checkpointer=checkpointer)
    """
    connection_string = _get_connection_string()
    
    # Создаем пул соединений
    pool = AsyncConnectionPool(conninfo=connection_string, open=False)
    await pool.open()
    
    try:
        # Создаем checkpointer
        checkpointer = AsyncPostgresSaver(pool)
        yield checkpointer
    finally:
        # Закрываем пул соединений
        await pool.close()
