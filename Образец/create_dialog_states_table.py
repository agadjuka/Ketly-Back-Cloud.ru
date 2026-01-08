"""Скрипт для создания таблицы dialog_states в YDB"""
import sys
import os

# Загружаем переменные окружения из .env файла
from dotenv import load_dotenv
load_dotenv()

from src.ydb_client import YDBClient


def create_dialog_states_table(client: YDBClient):
    """Создание таблицы dialog_states"""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS dialog_states (
        chat_id String,
        current_stage String,
        PRIMARY KEY (chat_id)
    );
    """
    def _tx(session):
        return session.execute_scheme(create_table_query)
    client.pool.retry_operation_sync(_tx)


def main():
    """Создание таблицы dialog_states в базе данных YDB"""
    try:
        print("🔌 Подключение к YDB...")
        client = YDBClient()
        
        print("📊 Создание таблицы dialog_states...")
        create_dialog_states_table(client)
        print("✅ Таблица dialog_states успешно создана!")
        print("\nСтруктура таблицы dialog_states:")
        print("  - chat_id (String) - ID пользователя")
        print("  - current_stage (String) - Текущая стадия (admin/demo)")
        print("  - PRIMARY KEY (chat_id)")
        
        client.close()
        print("\n🎉 Таблица успешно создана!")
        
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\nУбедитесь, что в переменных окружения заданы:")
        print("  - YDB_ENDPOINT")
        print("  - YDB_DATABASE")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при создании таблицы: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


