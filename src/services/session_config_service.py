"""Сервис для работы с конфигурациями сессий демо-агента в PostgreSQL"""
import json
import logging
import os
from typing import Optional, Dict, Any
import psycopg

logger = logging.getLogger(__name__)


class SessionConfigService:
    """Сервис для работы с конфигурациями сессий демо-агента"""
    
    def __init__(self):
        """
        Инициализирует сервис для работы с конфигурациями сессий.
        """
        self.table_name = "session_configs"
    
    def _get_connection_string(self) -> str:
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
    
    async def ensure_table_exists(self):
        """
        Создает таблицу session_configs если она не существует
        
        Таблица хранит конфигурации демо-сессий:
        - id: thread_id (PRIMARY KEY)
        - user_id: ID пользователя
        - company_name: Название компании
        - niche: Ниша бизнеса
        - persona_instruction: Инструкция для актера
        - welcome_message: Приветственное сообщение
        """
        connection_string = self._get_connection_string()
        
        try:
            async with await psycopg.AsyncConnection.connect(connection_string, autocommit=True) as conn:
                async with conn.cursor() as cur:
                    # Создаем таблицу если не существует
                    await cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.table_name} (
                            id VARCHAR PRIMARY KEY,
                            user_id VARCHAR,
                            company_name VARCHAR,
                            niche VARCHAR,
                            persona_instruction TEXT,
                            welcome_message TEXT,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    logger.info(f"Таблица {self.table_name} создана или уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании таблицы {self.table_name}: {e}")
            raise
    
    async def load_demo_config(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Загружает конфигурацию демо-агента для указанной сессии.
        
        Args:
            thread_id: ID сессии (thread_id)
            
        Returns:
            Словарь с конфигурацией или None, если конфигурация не найдена
        """
        logger.info(f"🔍 [SESSION_CONFIG] Запрос конфигурации из базы данных для thread_id={thread_id}")
        connection_string = self._get_connection_string()
        
        try:
            async with await psycopg.AsyncConnection.connect(connection_string, autocommit=True) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"""
                        SELECT 
                            id,
                            user_id,
                            company_name,
                            niche,
                            persona_instruction,
                            welcome_message
                        FROM {self.table_name}
                        WHERE id = %s
                        """,
                        (thread_id,)
                    )
                    row = await cur.fetchone()
                    
                    if not row:
                        logger.info(f"❌ [SESSION_CONFIG] Конфигурация для thread_id={thread_id} НЕ найдена в базе данных")
                        return None
                    
                    config = {
                        "id": row[0],
                        "user_id": row[1],
                        "company_name": row[2],
                        "niche": row[3],
                        "persona_instruction": row[4],
                        "welcome_message": row[5],
                    }
                    
                    logger.info(f"✅ [SESSION_CONFIG] Конфигурация для thread_id={thread_id} успешно загружена из базы данных")
                    logger.info(f"📋 [SESSION_CONFIG] Данные конфигурации: niche={config.get('niche')}, company_name={config.get('company_name')}")
                    return config
            
        except Exception as e:
            logger.error(f"❌ [SESSION_CONFIG] Ошибка при загрузке конфигурации для thread_id={thread_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def save_demo_config(
        self,
        thread_id: str,
        user_id: Optional[str],
        config_data: Dict[str, Any]
    ) -> bool:
        """
        Сохраняет конфигурацию демо-агента для указанной сессии.
        
        Args:
            thread_id: ID сессии (thread_id)
            user_id: ID пользователя (опционально)
            config_data: Словарь с данными конфигурации:
                - niche: Ниша бизнеса
                - company_name: Название компании
                - persona_instruction: Инструкция для актера
                - welcome_message: Приветственное сообщение
            
        Returns:
            True, если сохранение успешно, иначе False
        """
        logger.info(f"💾 [SESSION_CONFIG] Сохранение конфигурации для thread_id={thread_id}")
        connection_string = self._get_connection_string()
        
        try:
            async with await psycopg.AsyncConnection.connect(connection_string, autocommit=True) as conn:
                async with conn.cursor() as cur:
                    # Используем UPSERT (INSERT ... ON CONFLICT DO UPDATE)
                    await cur.execute(
                        f"""
                        INSERT INTO {self.table_name} 
                            (id, user_id, company_name, niche, persona_instruction, welcome_message, created_at, updated_at)
                        VALUES 
                            (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (id) 
                        DO UPDATE SET
                            user_id = EXCLUDED.user_id,
                            company_name = EXCLUDED.company_name,
                            niche = EXCLUDED.niche,
                            persona_instruction = EXCLUDED.persona_instruction,
                            welcome_message = EXCLUDED.welcome_message,
                            updated_at = NOW()
                        """,
                        (
                            thread_id,
                            user_id,
                            config_data.get("company_name"),
                            config_data.get("niche"),
                            config_data.get("persona_instruction"),
                            config_data.get("welcome_message"),
                        )
                    )
                    
                    logger.info(f"✅ [SESSION_CONFIG] Конфигурация успешно сохранена для thread_id={thread_id}")
                    logger.info(f"📋 [SESSION_CONFIG] Сохраненные данные: niche={config_data.get('niche')}, company_name={config_data.get('company_name')}")
                    return True
            
        except Exception as e:
            logger.error(f"❌ [SESSION_CONFIG] Ошибка при сохранении конфигурации для thread_id={thread_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def process_setup_response(
        self,
        thread_id: str,
        user_id: Optional[str],
        response_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Обрабатывает ответ от DemoSetupAgent и сохраняет конфигурацию
        
        Args:
            thread_id: ID сессии
            user_id: ID пользователя
            response_text: Текст ответа от DemoSetupAgent (должен содержать JSON)
            
        Returns:
            Словарь с конфигурацией или None, если парсинг не удался
        """
        logger.info(f"📝 [SESSION_CONFIG] Обработка ответа от DemoSetupAgent для thread_id={thread_id}")
        
        try:
            # Парсим JSON из ответа
            config_data = self._parse_json_from_response(response_text)
            
            if not config_data:
                logger.error(f"❌ [SESSION_CONFIG] Не удалось распарсить JSON из ответа DemoSetupAgent")
                return None
            
            # Валидация обязательных полей
            required_fields = ["niche", "company_name", "persona_instruction", "welcome_message"]
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                logger.error(f"❌ [SESSION_CONFIG] Отсутствуют обязательные поля в конфигурации: {missing_fields}")
                return None
            
            # Сохраняем конфигурацию
            success = await self.save_demo_config(thread_id, user_id, config_data)
            
            if success:
                logger.info(f"✅ [SESSION_CONFIG] Конфигурация успешно обработана и сохранена для thread_id={thread_id}")
                return config_data
            else:
                logger.error(f"❌ [SESSION_CONFIG] Не удалось сохранить конфигурацию для thread_id={thread_id}")
                return None
            
        except Exception as e:
            logger.error(f"❌ [SESSION_CONFIG] Ошибка при обработке ответа от DemoSetupAgent: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _parse_json_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Парсит JSON из ответа LLM
        
        Пытается найти JSON в ответе, даже если он обернут в markdown или текст
        
        Args:
            response_text: Текст ответа от LLM
            
        Returns:
            Распарсенный JSON словарь или None, если JSON не найден
        """
        if not response_text or not response_text.strip():
            return None
        
        response_text = response_text.strip()
        
        # Убираем markdown code blocks если есть
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Убираем первую строку (```json или ```)
            if len(lines) > 1:
                response_text = "\n".join(lines[1:])
            # Убираем последнюю строку (```)
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Пытаемся найти JSON в тексте
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            # Если не нашли, возвращаем None
            return None


# Глобальный экземпляр сервиса
_service: Optional[SessionConfigService] = None


def get_session_config_service() -> SessionConfigService:
    """
    Получить глобальный экземпляр сервиса конфигураций сессий
    
    Returns:
        Экземпляр SessionConfigService
    """
    global _service
    if _service is None:
        _service = SessionConfigService()
    return _service

