"""Модуль для работы с YDB"""
import os
import ydb
import ydb.iam
from typing import Optional


class YDBClient:
    """Клиент для работы с YDB"""
    
    def __init__(self):
        self.endpoint = os.getenv("YDB_ENDPOINT")
        self.database = os.getenv("YDB_DATABASE")
        
        if not self.endpoint or not self.database:
            raise ValueError("Не заданы YDB_ENDPOINT и YDB_DATABASE в переменных окружения")
        
        # Получаем IAM токен или используем service account
        iam_token = os.getenv("YC_IAM_TOKEN")
        service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
        
        if iam_token:
            # Используем IAM токен
            credentials = ydb.AccessTokenCredentials(iam_token)
        elif os.path.exists(service_account_key_file):
            # Используем service account key файл (для локальной разработки)
            try:
                credentials = ydb.iam.ServiceAccountCredentials.from_file(service_account_key_file)
            except Exception as e:
                # Если не удалось загрузить из файла, пробуем метаданные
                print(f"⚠️ Не удалось загрузить ключ из {service_account_key_file}: {e}")
                print("Пробую использовать метаданные Yandex Cloud...")
                credentials = ydb.iam.MetadataUrlCredentials()
        else:
            # Пытаемся получить креды из метаданных окружения (Serverless Containers)
            # Это работает только в контейнерах Yandex Cloud
            credentials = ydb.iam.MetadataUrlCredentials()
        
        # Инициализация драйвера YDB
        self.driver = ydb.Driver(
            endpoint=self.endpoint,
            database=self.database,
            credentials=credentials
        )
        self.driver.wait(fail_fast=True, timeout=10)
        self.pool = ydb.SessionPool(self.driver)
    
    def _execute_query(self, query: str, params: dict = None):
        """Выполнение запроса к YDB"""
        def _tx(session):
            prepared_query = session.prepare(query)
            # Преобразуем строки в байты для параметров
            if params:
                byte_params = {}
                for key, value in params.items():
                    if isinstance(value, str):
                        byte_params[key] = value.encode('utf-8')
                    else:
                        byte_params[key] = value
                return session.transaction().execute(prepared_query, byte_params, commit_tx=True)
            else:
                return session.transaction().execute(prepared_query, {}, commit_tx=True)
        return self.pool.retry_operation_sync(_tx)
    
    def init_schema(self):
        """Создание таблиц для маппинга chat_id -> last_response_id и conversation_history"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS chat_threads (
            chat_id String,
            last_response_id String,
            conversation_history String,
            updated_at Timestamp,
            PRIMARY KEY (chat_id)
        );
        """
        def _tx(session):
            return session.execute_scheme(create_table_query)
        self.pool.retry_operation_sync(_tx)
    
    def get_last_response_id(self, chat_id: str) -> Optional[str]:
        """Получение last_response_id по chat_id"""
        query = """
        DECLARE $id AS String; 
        SELECT last_response_id FROM chat_threads WHERE chat_id = $id;
        """
        result = self._execute_query(query, {"$id": chat_id})
        rows = result[0].rows
        return rows[0].last_response_id.decode() if rows and rows[0].last_response_id else None
    
    def save_response_id(self, chat_id: str, response_id: str):
        """Сохранение маппинга chat_id -> last_response_id"""
        query = """
        DECLARE $cid AS String; 
        DECLARE $rid AS String;
        UPSERT INTO chat_threads (chat_id, last_response_id, updated_at)
        VALUES ($cid, $rid, CurrentUtcTimestamp());
        """
        self._execute_query(query, {
            "$cid": chat_id, 
            "$rid": response_id
        })
    
    def reset_context(self, chat_id: str):
        """Сброс контекста для чата (очистка last_response_id)"""
        query = """
        DECLARE $cid AS String;
        UPDATE chat_threads SET last_response_id = NULL, updated_at = CurrentUtcTimestamp()
        WHERE chat_id = $cid;
        """
        self._execute_query(query, {"$cid": chat_id})
    
    def get_conversation_history(self, chat_id: str) -> Optional[str]:
        """Получение conversation_history по chat_id"""
        query = """
        DECLARE $cid AS String;
        SELECT conversation_history FROM chat_threads WHERE chat_id = $cid;
        """
        result = self._execute_query(query, {"$cid": chat_id})
        rows = result[0].rows
        if rows and rows[0].conversation_history:
            return rows[0].conversation_history.decode('utf-8')
        return None
    
    def save_conversation_history(self, chat_id: str, history_json: str):
        """Сохранение conversation_history"""
        query = """
        DECLARE $cid AS String;
        DECLARE $history AS String;
        UPSERT INTO chat_threads (chat_id, conversation_history, updated_at)
        VALUES ($cid, $history, CurrentUtcTimestamp());
        """
        self._execute_query(query, {
            "$cid": chat_id,
            "$history": history_json.encode('utf-8')
        })
    
    def reset_conversation_history(self, chat_id: str):
        """Сброс conversation_history для чата"""
        query = """
        DECLARE $cid AS String;
        UPDATE chat_threads SET conversation_history = NULL, updated_at = CurrentUtcTimestamp()
        WHERE chat_id = $cid;
        """
        self._execute_query(query, {"$cid": chat_id})
    
    def create_adminpanel_table(self):
        """Создание таблицы adminpanel для хранения данных административной панели"""
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
        self.pool.retry_operation_sync(_tx)
    
    def close(self):
        """Закрытие соединения с YDB"""
        if self.driver:
            self.driver.stop()


# Глобальный экземпляр клиента
ydb_client = None

def get_ydb_client() -> YDBClient:
    """Получение глобального экземпляра YDB клиента"""
    global ydb_client
    if ydb_client is None:
        ydb_client = YDBClient()
        ydb_client.init_schema()
    return ydb_client

