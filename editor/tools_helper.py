"""
Вспомогательный модуль для работы с инструментами в редакторе.
"""

from typing import Dict, List, Any, Type
from pydantic import BaseModel
from pathlib import Path
from registry_loader import setup_packages, load_registry


def get_all_tools() -> List[Type[BaseModel]]:
    """
    Получить все инструменты из реестра инструментов.
    
    Returns:
        Список всех инструментов (классы Pydantic BaseModel)
    """
    try:
        project_root = Path(__file__).parent.parent
        tools_dir = project_root / "src" / "agents" / "tools"
        
        setup_packages(project_root, [
            ("src", project_root / "src"),
            ("src.agents", project_root / "src" / "agents"),
            ("src.agents.tools", tools_dir),
        ])
        
        registry_file = tools_dir / "registry.py"
        registry_module = load_registry(registry_file, "src.agents.tools.registry", "src.agents.tools")
        
        if registry_module is None:
            print(f"[WARNING] Не удалось загрузить реестр инструментов из {registry_file}")
            return []
        
        registry = registry_module.get_registry()
        tools = registry.get_all_tools()
        
        print(f"[DEBUG] Загружено инструментов из реестра: {len(tools)}")
        if tools:
            print(f"[DEBUG] Имена инструментов: {[t.__name__ for t in tools]}")
        
        return tools
    except Exception as e:
        import traceback
        print(f"[ERROR] Ошибка загрузки инструментов из реестра: {str(e)}\n{traceback.format_exc()}")
        return []


def get_tool_info(tool: Type[BaseModel]) -> Dict[str, Any]:
    """
    Получить информацию об инструменте для отображения в редакторе.
    
    Args:
        tool: Класс инструмента (Pydantic BaseModel)
    
    Returns:
        Словарь с информацией об инструменте
    """
    info = {
        "name": tool.__name__,
        "description": tool.__doc__ or "",
        "parameters": []
    }
    
    # Получаем схему Pydantic модели
    try:
        schema = tool.model_json_schema()
        
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            
            # Обрабатываем разные типы
            if param_type == 'integer':
                param_type = 'number'
            elif param_type == 'boolean':
                param_type = 'boolean'
            elif 'enum' in param_info:
                param_type = 'enum'
            
            param_data = {
                "name": param_name,
                "type": param_type,
                "description": param_info.get('description', ''),
                "required": param_name in required,
                "default": param_info.get('default')
            }
            
            # Добавляем enum значения если есть
            if 'enum' in param_info:
                param_data['enum'] = param_info['enum']
            
            info["parameters"].append(param_data)
    except Exception as e:
        # Если не удалось получить схему, пробуем через inspect
        try:
            # Пробуем получить поля модели
            if hasattr(tool, 'model_fields'):
                for field_name, field_info in tool.model_fields.items():
                    param_type = 'string'
                    if hasattr(field_info, 'annotation'):
                        ann = field_info.annotation
                        if ann == int:
                            param_type = 'number'
                        elif ann == bool:
                            param_type = 'boolean'
                    
                    param_data = {
                        "name": field_name,
                        "type": param_type,
                        "description": getattr(field_info, 'description', '') or '',
                        "required": field_info.is_required() if hasattr(field_info, 'is_required') else True,
                        "default": field_info.default if hasattr(field_info, 'default') else None
                    }
                    info["parameters"].append(param_data)
        except Exception as inner_e:
            # Если ничего не получилось, просто возвращаем базовую информацию
            print(f"[WARNING] Не удалось получить параметры для инструмента {tool.__name__}: {inner_e}")
    
    return info


def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Выполнить инструмент с заданными аргументами.
    
    Args:
        tool_name: Имя инструмента
        args: Аргументы для инструмента
        
    Returns:
        Результат выполнения инструмента
    """
    try:
        tools = get_all_tools()
        
        if not tools:
            return {
                "success": False,
                "error": "Не удалось загрузить инструменты. Убедитесь, что модули src доступны."
            }
        
        # Находим инструмент по имени
        tool_class = None
        for t in tools:
            if t.__name__ == tool_name:
                tool_class = t
                break
        
        if not tool_class:
            return {
                "success": False,
                "error": f"Инструмент '{tool_name}' не найден"
            }
        
        # Создаем экземпляр инструмента с переданными аргументами
        tool_instance = tool_class(**args)
        
        # Выполняем инструмент через метод process
        # Создаем заглушку для Thread
        class MockThread:
            """Заглушка для Thread при тестировании инструментов"""
            def __init__(self):
                self.id = "test_thread"
                self.chat_id = None
            
            def get_messages(self):
                return []
        
        try:
            from src.common.thread import Thread
            try:
                thread = Thread()
            except Exception:
                thread = MockThread()
        except ImportError:
            thread = MockThread()
        
        result = tool_instance.process(thread)
        
        return {
            "success": True,
            "result": str(result) if result else "Инструмент выполнен успешно, но не вернул результат"
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": f"{str(e)}\n\n{traceback.format_exc()}"
        }

