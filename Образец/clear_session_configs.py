"""Скрипт для полной очистки таблицы session_configs в YDB"""
import sys
import os

# Загружаем переменные окружения из .env файла
from dotenv import load_dotenv
load_dotenv()

from src.ydb_client import YDBClient


def clear_session_configs_table(client: YDBClient):
    """Полная очистка таблицы session_configs"""
    delete_query = """
    DELETE FROM session_configs;
    """
    def _tx(session):
        prepared_query = session.prepare(delete_query)
        return session.transaction().execute(prepared_query, {}, commit_tx=True)
    client.pool.retry_operation_sync(_tx)


def main():
    """Полная очистка таблицы session_configs в базе данных YDB"""
    try:
        print("🔌 Подключение к YDB...")
        client = YDBClient()
        
        print("⚠️  ВНИМАНИЕ: Вы собираетесь полностью очистить таблицу session_configs!")
        print("Это действие необратимо. Все данные будут удалены.")
        
        confirmation = input("\nВведите 'ДА' для подтверждения: ")
        
        if confirmation != "ДА":
            print("❌ Операция отменена.")
            client.close()
            return
        
        print("\n🗑️  Очистка таблицы session_configs...")
        clear_session_configs_table(client)
        print("✅ Таблица session_configs успешно очищена!")
        
        client.close()
        print("\n🎉 Операция завершена!")
        
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\nУбедитесь, что в переменных окружения заданы:")
        print("  - YDB_ENDPOINT")
        print("  - YDB_DATABASE")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при очистке таблицы: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

