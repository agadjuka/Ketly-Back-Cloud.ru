#!/usr/bin/env python3
"""
Скрипт для создания таблицы админ-панели в PostgreSQL.

Создает таблицу для хранения связей между user_id (Telegram ID или UUID для веб) 
и topic_id (ID топика в Telegram Forum).

Использование:
    python create_admin_panel_table.py

Переменные окружения:
    ADMIN_TOPICS_TABLE - название таблицы (по умолчанию "adminpanel_ketly")
    DATABASE_URL - полная строка подключения к PostgreSQL
    ИЛИ отдельные параметры:
        PG_HOST - хост PostgreSQL (по умолчанию "localhost")
        PG_PORT - порт PostgreSQL (по умолчанию "5432")
        PG_DB - название базы данных (по умолчанию "ai_db")
        PG_USER - пользователь PostgreSQL (по умолчанию "postgres")
        PG_PASSWORD - пароль PostgreSQL
"""
import os
import sys
from dotenv import load_dotenv
import psycopg

# Загружаем переменные окружения
load_dotenv()


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


def get_admin_topics_table() -> str:
    """
    Получает название таблицы для хранения топиков в БД.
    
    Returns:
        Название таблицы (по умолчанию "adminpanel_ketly")
    """
    return os.getenv("ADMIN_TOPICS_TABLE", "adminpanel_ketly")


def create_admin_panel_table():
    """Создает таблицу для админ-панели в PostgreSQL."""
    table_name = get_admin_topics_table()
    connection_string = _get_connection_string()
    
    print(f"🔧 Создание таблицы '{table_name}' для админ-панели...")
    print(f"📡 Подключение к PostgreSQL...")
    
    try:
        with psycopg.connect(connection_string, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Проверяем, существует ли таблица
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, (table_name,))
                
                table_exists = cur.fetchone()[0]
                
                if table_exists:
                    print(f"⚠️  Таблица '{table_name}' уже существует.")
                    response = input("Пересоздать таблицу? (y/N): ").strip().lower()
                    if response == 'y':
                        print(f"🗑️  Удаление существующей таблицы '{table_name}'...")
                        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
                        print("✅ Таблица удалена.")
                    else:
                        print("ℹ️  Используется существующая таблица.")
                        return
                
                # Создаем таблицу с правильной структурой
                # user_id - TEXT для поддержки и int (Telegram) и UUID (веб)
                create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    user_id TEXT PRIMARY KEY,
                    topic_id INTEGER NOT NULL,
                    topic_name TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'auto',
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
                
                cur.execute(create_table_query)
                
                # Создаем индекс для быстрого поиска по topic_id
                create_index_query = f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_topic_id 
                ON {table_name}(topic_id);
                """
                
                cur.execute(create_index_query)
                
                # Создаем индекс для updated_at (для возможной очистки старых записей)
                create_index_updated_query = f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_updated_at 
                ON {table_name}(updated_at);
                """
                
                cur.execute(create_index_updated_query)
                
                print(f"✅ Таблица '{table_name}' успешно создана!")
                print(f"📊 Структура таблицы:")
                print(f"   - user_id: TEXT (PRIMARY KEY) - поддерживает int и UUID")
                print(f"   - topic_id: INTEGER - ID топика в Telegram Forum")
                print(f"   - topic_name: TEXT - название топика")
                print(f"   - mode: TEXT - режим работы ('auto' или 'manual')")
                print(f"   - updated_at: TIMESTAMP - время последнего обновления")
                print(f"📈 Индексы созданы для topic_id и updated_at")
                
    except psycopg.Error as e:
        print(f"❌ Ошибка PostgreSQL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Создание таблицы админ-панели")
    print("=" * 60)
    create_admin_panel_table()
    print("=" * 60)
    print("✅ Готово!")
    print("=" * 60)

