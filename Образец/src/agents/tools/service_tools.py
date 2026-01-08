"""
Инструменты для работы с каталогом услуг
"""
import json
from pydantic import BaseModel, Field
from yandex_cloud_ml_sdk._threads.thread import Thread

# Импорты
from .services_data_loader import _data_loader

try:
    from ..services.logger_service import logger
except ImportError:
    # Простой logger для случаев, когда logger_service недоступен
    class SimpleLogger:
        def error(self, msg, *args, **kwargs):
            print(f"ERROR: {msg}")
    logger = SimpleLogger()


class GetServices(BaseModel):
    """
    Получить список услуг указанной категории с ценами и ID услуг.
    Используй когда клиент спрашивает "какие виды маникюра?" или "что есть в категории массаж?"
    """
    
    category_id: str = Field(
        description="ID категории (строка). Доступные категории: '1' - Маникюр, '2' - Педикюр, '3' - Услуги для мужчин, '4' - Брови, '5' - Ресницы, '6' - Макияж, '7' - Парикмахерские услуги, '8' - Пирсинг, '9' - Лазерная эпиляция, '10' - Косметология, '11' - Депиляция, '12' - Массаж, '13' - LOOKTOWN SPA."
    )
    
    def process(self, thread: Thread) -> str:
        """
        Получение списка услуг указанной категории
        
        Args:
            category_id: ID категории из списка категорий
            
        Returns:
            Отформатированный список услуг категории
        """
        try:
            data = _data_loader.load_data()
            
            if not data:
                return "Данные об услугах не найдены"
            
            # Получаем категорию по ID
            category = data.get(self.category_id)
            if not category:
                available_ids = ", ".join(sorted(data.keys(), key=int))
                return (
                    f"Категория с ID '{self.category_id}' не найдена.\n"
                    f"Доступные ID категорий: {available_ids}"
                )
            
            category_name = category.get('category_name', 'Неизвестно')
            services = category.get('services', [])
            
            if not services:
                return f"В категории '{category_name}' нет доступных услуг"
            
            # Форматируем услуги
            result_lines = [f"Услуги категории '{category_name}':\n"]
            
            for service in services:
                name = service.get('name', 'Неизвестно')
                price = service.get('prices', 'Не указана')
                master_level = service.get('master_level')
                service_id = service.get('id', 'Не указан')
                
                service_line = f"  • {name} (ID: {service_id}) - {price} руб."
                if master_level:
                    service_line += f" ({master_level})"
                
                result_lines.append(service_line)
            
            return "\n".join(result_lines)
            
        except FileNotFoundError as e:
            logger.error(f"Файл с услугами не найден: {e}")
            return "Файл с данными об услугах не найден"
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return "Ошибка при чтении данных об услугах"
        except Exception as e:
            logger.error(f"Ошибка при получении услуг: {e}")
            return f"Ошибка при получении услуг: {str(e)}"
