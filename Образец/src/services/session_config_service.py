"""Сервис для работы с конфигурациями сессий демо-агента в YDB"""
import json
import logging
from typing import Optional, Dict, Any

from src.ydb_client import get_ydb_client

logger = logging.getLogger(__name__)


class SessionConfigService:
    """Сервис для работы с конфигурациями сессий демо-агента"""
    
    def __init__(self, ydb_client=None):
        """
        Инициализирует сервис для работы с конфигурациями сессий.
        
        Args:
            ydb_client: Экземпляр YDBClient (если None, будет получен при первом использовании)
        """
        self._ydb_client = ydb_client
        self.table_name = "session_configs"
    
    @property
    def ydb_client(self):
        """Получает или создает экземпляр YDBClient."""
        if self._ydb_client is None:
            self._ydb_client = get_ydb_client()
        return self._ydb_client
    
    def load_demo_config(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Загружает конфигурацию демо-агента для указанной сессии.
        
        Args:
            thread_id: ID сессии (thread_id)
            
        Returns:
            Словарь с конфигурацией или None, если конфигурация не найдена
        """
        logger.info(f"🔍 [SESSION_CONFIG] Запрос конфигурации из базы данных для thread_id={thread_id}")
        try:
            query = """
            DECLARE $id AS String;
            SELECT 
                id,
                user_id,
                company_name,
                niche,
                persona_instruction,
                welcome_message
            FROM session_configs 
            WHERE id = $id;
            """
            
            result = self.ydb_client._execute_query(query, {"$id": thread_id})
            rows = result[0].rows
            
            if not rows:
                logger.info(f"❌ [SESSION_CONFIG] Конфигурация для thread_id={thread_id} НЕ найдена в базе данных")
                return None
            
            row = rows[0]
            
            # Декодируем строки из bytes, если необходимо
            def decode_field(field):
                if field is None:
                    return None
                if isinstance(field, bytes):
                    return field.decode('utf-8')
                return field
            
            config = {
                "id": decode_field(row.id),
                "user_id": decode_field(row.user_id),
                "company_name": decode_field(row.company_name),
                "niche": decode_field(row.niche),
                "persona_instruction": decode_field(row.persona_instruction),
                "welcome_message": decode_field(row.welcome_message),
            }
            
            logger.info(f"✅ [SESSION_CONFIG] Конфигурация для thread_id={thread_id} успешно загружена из базы данных")
            logger.info(f"📋 [SESSION_CONFIG] Данные конфигурации: niche={config.get('niche')}, company_name={config.get('company_name')}")
            return config
            
        except Exception as e:
            logger.error(f"❌ [SESSION_CONFIG] Ошибка при загрузке конфигурации для thread_id={thread_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def save_demo_config(
        self,
        thread_id: str,
        user_id: Optional[str],
        config_data: Dict[str, Any]
    ) -> bool:
        """
        Сохраняет конфигурацию демо-агента для указанной сессии.
        
        Args:
            thread_id: ID сессии (thread_id)
            user_id: ID пользователя (может быть None)
            config_data: Словарь с данными конфигурации (должен содержать niche, company_name, persona_instruction, welcome_message)
            
        Returns:
            True, если сохранение успешно, False в противном случае
        """
        logger.info(f"💾 [SESSION_CONFIG] Начинаю сохранение конфигурации в базу данных для thread_id={thread_id}")
        logger.info(f"📋 [SESSION_CONFIG] Данные для сохранения: niche={config_data.get('niche')}, company_name={config_data.get('company_name')}")
        
        try:
            # Проверяем наличие обязательного поля niche
            if "niche" not in config_data:
                logger.error(f"❌ [SESSION_CONFIG] Отсутствует обязательное поле 'niche' в config_data для thread_id={thread_id}")
                return False
            
            query = """
            DECLARE $id AS String;
            DECLARE $user_id AS String?;
            DECLARE $company_name AS String?;
            DECLARE $niche AS String;
            DECLARE $persona_instruction AS String?;
            DECLARE $welcome_message AS String?;
            
            UPSERT INTO session_configs (
                id,
                user_id,
                company_name,
                niche,
                persona_instruction,
                welcome_message,
                updated_at
            )
            VALUES (
                $id,
                $user_id,
                $company_name,
                $niche,
                $persona_instruction,
                $welcome_message,
                CurrentUtcTimestamp()
            );
            """
            
            self.ydb_client._execute_query(query, {
                "$id": thread_id,
                "$user_id": str(user_id) if user_id else None,
                "$company_name": config_data.get("company_name"),
                "$niche": config_data["niche"],
                "$persona_instruction": config_data.get("persona_instruction"),
                "$welcome_message": config_data.get("welcome_message"),
            })
            
            logger.info(f"✅ [SESSION_CONFIG] Конфигурация успешно сохранена в базу данных для thread_id={thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ [SESSION_CONFIG] Ошибка при сохранении конфигурации для thread_id={thread_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Извлекает JSON из текста, ища первую { и последнюю }.
        
        Args:
            text: Текст, из которого нужно извлечь JSON
            
        Returns:
            Распарсенный словарь или None, если не удалось извлечь
        """
        try:
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            
            if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
                return None
            
            json_str = text[start_idx:end_idx + 1]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Ошибка при извлечении JSON из текста: {e}")
            return None
    
    def process_setup_response(
        self,
        thread_id: str,
        user_id: Optional[str],
        response_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Обрабатывает ответ от demo-setup агента, извлекает JSON и сохраняет в YDB.
        
        Args:
            thread_id: ID сессии (thread_id)
            user_id: ID пользователя (может быть None)
            response_text: Текст ответа от demo-setup агента
            
        Returns:
            Словарь с сохраненной конфигурацией или None, если не удалось обработать
        """
        logger.info(f"🔄 [SESSION_CONFIG] Начинаю обработку ответа demo-setup агента для thread_id={thread_id}")
        logger.debug(f"📝 [SESSION_CONFIG] Ответ demo-setup агента (первые 500 символов): {response_text[:500]}")
        
        try:
            # Пытаемся распарсить JSON напрямую
            logger.info(f"🔍 [SESSION_CONFIG] Пытаюсь распарсить JSON из ответа demo-setup агента")
            try:
                config_data = json.loads(response_text)
                logger.info(f"✅ [SESSION_CONFIG] JSON успешно распарсен напрямую")
            except json.JSONDecodeError:
                # Если не удалось, пытаемся извлечь JSON из текста
                logger.warning(f"⚠️ [SESSION_CONFIG] Не удалось распарсить JSON напрямую, пытаюсь извлечь из текста")
                config_data = self._extract_json_from_text(response_text)
                if config_data:
                    logger.info(f"✅ [SESSION_CONFIG] JSON успешно извлечен из текста")
            
            if not config_data:
                logger.error(f"❌ [SESSION_CONFIG] Не удалось извлечь JSON из ответа demo-setup агента для thread_id={thread_id}")
                return None
            
            logger.info(f"📋 [SESSION_CONFIG] Извлеченные данные: niche={config_data.get('niche')}, company_name={config_data.get('company_name')}")
            
            # Проверяем наличие обязательного поля niche
            if "niche" not in config_data:
                logger.error(f"❌ [SESSION_CONFIG] Отсутствует обязательное поле 'niche' в ответе demo-setup агента для thread_id={thread_id}")
                return None
            
            # Сохраняем конфигурацию
            logger.info(f"💾 [SESSION_CONFIG] Сохраняю конфигурацию в базу данных")
            if self.save_demo_config(thread_id, user_id, config_data):
                # Загружаем сохраненную конфигурацию для возврата
                logger.info(f"🔍 [SESSION_CONFIG] Загружаю сохраненную конфигурацию для проверки")
                saved_config = self.load_demo_config(thread_id)
                if saved_config:
                    logger.info(f"✅ [SESSION_CONFIG] Успешно обработан и сохранен ответ demo-setup агента для thread_id={thread_id}")
                    return saved_config
                else:
                    # Если не удалось загрузить сразу после сохранения, пробуем еще раз
                    logger.warning(f"⚠️ [SESSION_CONFIG] Не удалось загрузить сохраненную конфигурацию для thread_id={thread_id}, пробую еще раз...")
                    return self.load_demo_config(thread_id)
            else:
                logger.error(f"❌ [SESSION_CONFIG] Не удалось сохранить конфигурацию для thread_id={thread_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [SESSION_CONFIG] Ошибка при обработке ответа demo-setup агента для thread_id={thread_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


# Глобальный экземпляр сервиса
_session_config_service = None


def get_session_config_service() -> SessionConfigService:
    """Получение глобального экземпляра сервиса конфигураций сессий"""
    global _session_config_service
    if _session_config_service is None:
        _session_config_service = SessionConfigService()
    return _session_config_service

