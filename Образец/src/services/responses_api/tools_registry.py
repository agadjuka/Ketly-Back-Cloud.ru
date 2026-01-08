"""
Регистрация инструментов для Responses API
"""
import json
from typing import Dict, Callable, Any, List, Optional
from pydantic import BaseModel
from ..logger_service import logger


class ResponsesToolsRegistry:
    """Регистрация и управление инструментами для Responses API"""
    
    def __init__(self):
        self._local_functions: Dict[str, Callable[..., Any]] = {}
        self._tool_classes: Dict[str, type] = {}
    
    def register_tool(self, tool_class: type):
        """
        Регистрация инструмента
        
        Args:
            tool_class: Класс инструмента (Pydantic BaseModel с методом process)
        """
        if not issubclass(tool_class, BaseModel):
            raise ValueError(f"Инструмент {tool_class.__name__} должен быть наследником BaseModel")
        
        if not hasattr(tool_class, 'process'):
            raise ValueError(f"Инструмент {tool_class.__name__} должен иметь метод process")
        
        tool_name = tool_class.__name__
        
        # Проверяем, не зарегистрирован ли уже этот инструмент в этом реестре
        if tool_name in self._tool_classes:
            # Инструмент уже зарегистрирован в этом реестре - не логируем повторно
            return
        
        self._tool_classes[tool_name] = tool_class
        
        # Создаём обёртку для вызова инструмента
        def tool_wrapper(**kwargs):
            """Обёртка для вызова инструмента без Thread"""
            try:
                # Создаём экземпляр инструмента с переданными параметрами
                tool_instance = tool_class(**kwargs)
                
                # Создаём минимальный mock Thread для совместимости
                # Большинство инструментов не используют thread напрямую
                class MockThread:
                    """Минимальный mock Thread для совместимости с Responses API"""
                    def __init__(self, conversation_history=None, chat_id=None):
                        self.id = None
                        self.chat_id = chat_id
                        self._conversation_history = conversation_history or []
                    
                    def __iter__(self):
                        """Для совместимости с инструментами, которые итерируют thread"""
                        # Возвращаем mock-объекты сообщений из conversation_history
                        class MockMessage:
                            def __init__(self, role, content):
                                self.author = type('Author', (), {'role': role.upper()})()
                                self.text = content
                                self.role = role
                                self.content = content
                        
                        messages = []
                        for msg in self._conversation_history:
                            if isinstance(msg, dict):
                                role = msg.get("role", "user")
                                content = msg.get("content", "")
                                messages.append(MockMessage(role, content))
                        
                        return iter(messages)
                
                # Получаем conversation_history и chat_id из kwargs, если переданы
                conversation_history = kwargs.pop('_conversation_history', None)
                chat_id = kwargs.pop('_chat_id', None)
                
                # Если у инструмента есть поля storage или chat_id, передаем их в экземпляр
                if hasattr(tool_class, 'model_fields'):
                    if 'chat_id' in tool_class.model_fields and chat_id:
                        # Обновляем chat_id в экземпляре, если поле есть
                        tool_instance.chat_id = chat_id
                    if 'storage' in tool_class.model_fields:
                        # Получаем storage через фабрику, если поле есть
                        try:
                            from ...storage.dialog_state_storage_factory import get_dialog_state_storage
                            tool_instance.storage = get_dialog_state_storage()
                        except Exception as e:
                            logger.debug(f"Не удалось получить storage для {tool_name}: {e}")
                
                mock_thread = MockThread(conversation_history=conversation_history, chat_id=chat_id)
                
                # Вызываем process
                result = tool_instance.process(mock_thread)
                return result
            except Exception as e:
                # Пробрасываем CallManagerException дальше
                from ...agents.tools.call_manager_tools import CallManagerException
                if isinstance(e, CallManagerException):
                    raise
                
                logger.error(f"Ошибка при вызове инструмента {tool_name}: {e}", exc_info=True)
                return f"Ошибка при выполнении инструмента {tool_name}: {str(e)}"
        
        self._local_functions[tool_name] = tool_wrapper
        # Логируем только при первой регистрации в реестре
        logger.debug(f"Зарегистрирован инструмент: {tool_name}")
    
    def register_tools_from_list(self, tool_classes: List[type]):
        """
        Регистрация нескольких инструментов
        
        Args:
            tool_classes: Список классов инструментов
        """
        for tool_class in tool_classes:
            self.register_tool(tool_class)
    
    def call_tool(self, name: str, arguments: Dict[str, Any], conversation_history: Optional[List[Dict[str, Any]]] = None, chat_id: Optional[str] = None) -> Any:
        """
        Вызов зарегистрированного инструмента
        
        Args:
            name: Имя инструмента
            arguments: Аргументы для инструмента
            conversation_history: История диалога (для передачи в MockThread)
            chat_id: ID чата в Telegram (для передачи в MockThread)
            
        Returns:
            Результат выполнения инструмента
        """
        fn = self._local_functions.get(name)
        if fn is None:
            raise RuntimeError(f"Инструмент '{name}' не зарегистрирован")
        
        # Передаём conversation_history и chat_id в tool_wrapper через специальные параметры
        if conversation_history is not None:
            arguments['_conversation_history'] = conversation_history
        if chat_id is not None:
            arguments['_chat_id'] = chat_id
        
        return fn(**arguments)
    
    def get_tool_schema(self, tool_class: type) -> Dict[str, Any]:
        """
        Получение JSON схемы инструмента в формате OpenAI function tool
        
        Args:
            tool_class: Класс инструмента
            
        Returns:
            Схема инструмента в формате OpenAI function tool
        """
        try:
            # Получаем JSON схему Pydantic модели
            pydantic_schema = tool_class.model_json_schema()
            
            # Извлекаем описание из docstring
            description = tool_class.__doc__ or ""
            if description:
                description = description.strip()
            
            # Формируем схему в формате OpenAI function tool
            tool_schema = {
                "type": "function",
                "name": tool_class.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                "strict": True,
            }
            
            # Заполняем properties из Pydantic схемы
            properties = pydantic_schema.get("properties", {})
            required = pydantic_schema.get("required", [])
            
            for prop_name, prop_info in properties.items():
                # Пропускаем служебные поля
                if prop_name.startswith("_"):
                    continue
                
                # Определяем тип параметра
                param_type = prop_info.get("type")
                if isinstance(param_type, list):
                    # Для Optional типов берём первый не-None тип
                    param_type = next((t for t in param_type if t != "null"), "string")
                
                # Маппинг типов Python -> JSON Schema
                type_mapping = {
                    "string": "string",
                    "integer": "integer",
                    "number": "number",
                    "boolean": "boolean",
                    "array": "array",
                    "object": "object",
                }
                
                json_type = type_mapping.get(param_type, "string")
                
                # Формируем описание параметра
                param_description = prop_info.get("description", "")
                
                # Добавляем параметр в properties
                tool_schema["parameters"]["properties"][prop_name] = {
                    "type": json_type,
                    "description": param_description,
                }
                
                # Добавляем в required если нужно
                if prop_name in required:
                    tool_schema["parameters"]["required"].append(prop_name)
            
            return tool_schema
            
        except Exception as e:
            logger.error(f"Ошибка при создании схемы инструмента {tool_class.__name__}: {e}", exc_info=True)
            raise
    
    def get_all_tools_schemas(self) -> List[Dict[str, Any]]:
        """
        Получение схем всех зарегистрированных инструментов
        
        Returns:
            Список схем инструментов в формате OpenAI function tools
        """
        schemas = []
        for tool_name, tool_class in self._tool_classes.items():
            try:
                schema = self.get_tool_schema(tool_class)
                schemas.append(schema)
            except Exception as e:
                logger.error(f"Ошибка при получении схемы для {tool_name}: {e}")
        
        return schemas
    
    def get_registered_tools(self) -> List[str]:
        """Получить список зарегистрированных инструментов"""
        return list(self._local_functions.keys())

