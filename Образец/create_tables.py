"""Скрипт для создания таблиц adminpanel и chat_threads в YDB"""
import sys
import os

# Загружаем переменные окружения из .env файла
from dotenv import load_dotenv
load_dotenv()

from src.ydb_client import YDBClient


def create_adminpanel_table(client: YDBClient):
    """Создание таблицы adminpanel"""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS adminpanel (
        user_id String,
        topic_id String,
        topic_name String,
        mode String,
        PRIMARY KEY (user_id)
    );
    """
    def _tx(session):
        return session.execute_scheme(create_table_query)
    client.pool.retry_operation_sync(_tx)


def create_chat_threads_table(client: YDBClient):
    """Создание таблицы chat_threads"""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS chat_threads (
        chat_id String,
        last_response_id String,
        updated_at Timestamp,
        PRIMARY KEY (chat_id)
    );
    """
    def _tx(session):
        return session.execute_scheme(create_table_query)
    client.pool.retry_operation_sync(_tx)


def main():
    """Создание таблиц adminpanel и chat_threads в базе данных YDB"""
    try:
        print("🔌 Подключение к YDB...")
        client = YDBClient()
        
        print("📊 Создание таблицы adminpanel...")
        create_adminpanel_table(client)
        print("✅ Таблица adminpanel успешно создана!")
        print("\nСтруктура таблицы adminpanel:")
        print("  - user_id (String) - ID пользователя")
        print("  - topic_id (String) - ID топика")
        print("  - topic_name (String) - Название топика")
        print("  - mode (String) - Режим работы")
        print("  - PRIMARY KEY (user_id)")
        
        print("\n📊 Создание таблицы chat_threads...")
        create_chat_threads_table(client)
        print("✅ Таблица chat_threads успешно создана!")
        print("\nСтруктура таблицы chat_threads:")
        print("  - chat_id (String) - ID чата")
        print("  - last_response_id (String) - ID последнего ответа")
        print("  - updated_at (Timestamp) - Время последнего обновления")
        print("  - PRIMARY KEY (chat_id)")
        
        client.close()
        print("\n🎉 Все таблицы успешно созданы!")
        
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\nУбедитесь, что в переменных окружения заданы:")
        print("  - YDB_ENDPOINT")
        print("  - YDB_DATABASE")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()



