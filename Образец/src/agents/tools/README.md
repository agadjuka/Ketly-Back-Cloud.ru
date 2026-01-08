# Работа с инструментами (Tools)

## Создание нового инструмента

### 1. Создайте файл с инструментом

Создайте новый файл в папке `src/agents/tools/`, например `my_tool.py`:

```python
from pydantic import BaseModel, Field
from yandex_cloud_ml_sdk._threads.thread import Thread

try:
    from ..services.logger_service import logger
except ImportError:
    class SimpleLogger:
        def error(self, msg, *args, **kwargs):
            print(f"ERROR: {msg}")
    logger = SimpleLogger()


class MyTool(BaseModel):
    """
    Описание инструмента для LLM.
    Укажите, когда и как использовать этот инструмент.
    """
    
    param1: str = Field(
        description="Описание параметра для LLM"
    )
    
    param2: Optional[int] = Field(
        default=None,
        description="Опциональный параметр"
    )
    
    def process(self, thread: Thread) -> str:
        """
        Основная логика инструмента.
        
        Args:
            thread: Thread с историей диалога
            
        Returns:
            Строка с результатом выполнения
        """
        try:
            # Ваша логика здесь
            result = f"Результат работы с {self.param1}"
            return result
        except Exception as e:
            logger.error(f"Ошибка в MyTool: {e}")
            return f"Ошибка: {str(e)}"
```

### 2. Зарегистрируйте инструмент в `__init__.py`

Добавьте импорт в `src/agents/tools/__init__.py`:

```python
from .my_tool import MyTool

__all__ = [
    "GetServices",
    "CallManager",
    "MyTool",  # Добавьте новый инструмент
]
```

### 3. Зарегистрируйте в реестре `registry.py`

Добавьте в `src/agents/tools/registry.py`:

```python
def _load_tools(self) -> None:
    try:
        from .service_tools import GetServices
        from .call_manager_tools import CallManager
        from .my_tool import MyTool  # Добавьте импорт
        
        tools_list = [
            GetServices,
            CallManager,
            MyTool,  # Добавьте в список
        ]
        # ... остальной код
```

## Подключение инструмента к агенту

В файле агента (например, `src/agents/my_agent.py`):

```python
from .tools.my_tool import MyTool
from .tools.call_manager_tools import CallManager
from .base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, langgraph_service):
        super().__init__(
            langgraph_service=langgraph_service,
            instruction="Инструкция для агента",
            tools=[MyTool, CallManager],  # Список инструментов
            agent_name="Мой агент"
        )
```

## Удаление инструмента

### 1. Удалите файл инструмента

```bash
rm src/agents/tools/my_tool.py
```

### 2. Удалите из `__init__.py`

Удалите строки:
```python
from .my_tool import MyTool
# и из __all__
"MyTool",
```

### 3. Удалите из `registry.py`

Удалите из `_load_tools()`:
```python
from .my_tool import MyTool  # Удалить
# и из tools_list
MyTool,  # Удалить
```

### 4. Удалите из всех агентов

Найдите все использования:
```bash
grep -r "MyTool" src/agents/
```

Удалите `MyTool` из списка `tools=[]` во всех агентах.

### 5. Удалите связанные файлы (если есть)

Если у инструмента есть отдельные файлы логики или data_loader, удалите их тоже.

## Импорт инструментов

### В агентах

```python
from .tools.service_tools import GetServices
from .tools.call_manager_tools import CallManager
```

### В других модулях

```python
from src.agents.tools import GetServices, CallManager
```

### Через реестр

```python
from src.agents.tools.registry import get_registry

registry = get_registry()
all_tools = registry.get_all_tools()
tool = registry.get_tool("GetServices")
```

## Требования к инструменту

1. **Наследование**: Должен наследоваться от `pydantic.BaseModel`
2. **Метод process**: Обязательный метод `process(self, thread: Thread) -> str`
3. **Документация**: Docstring класса используется LLM для понимания назначения
4. **Поля**: Используйте `Field` с `description` для всех параметров
5. **Обработка ошибок**: Всегда обрабатывайте исключения и возвращайте понятные сообщения

## Примеры существующих инструментов

- `service_tools.py` - `GetServices` - получение услуг
- `call_manager_tools.py` - `CallManager` - передача менеджеру

Изучите эти файлы для понимания структуры.



