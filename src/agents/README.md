# Руководство по работе с агентами

## Архитектура агентов

Проект использует архитектуру на основе LangGraph с системой роутинга через `StageDetectorAgent`. 

### Основные компоненты:

1. **BaseAgent** (`base_agent.py`) - базовый класс для всех агентов
   - Все агенты наследуются от `BaseAgent`
   - Использует OpenAI-совместимый API (cloud.ru)
   - Поддерживает инструменты (tools) и логирование

2. **StageDetectorAgent** (`stage_detector_agent.py`) - роутер, определяющий стадию диалога
   - Анализирует сообщение пользователя
   - Определяет, к какому агенту направить запрос
   - Использует enum `DialogueStage` для определения стадий

3. **MainGraph** (`src/graph/main_graph.py`) - основной граф состояний
   - Управляет маршрутизацией между агентами
   - Создает и кэширует экземпляры агентов
   - Обрабатывает результаты работы агентов

4. **DialogueStage** (`dialogue_stages.py`) - enum со всеми стадиями диалога
   - Каждая стадия соответствует одному агенту
   - Используется для маршрутизации в графе

### Текущие агенты:

- **GreetingAgent** - обработка приветствия
- **ViewMyBookingAgent** - просмотр записей клиента

---

## Создание нового агента

### Шаг 1: Создание файла агента

Создайте файл `{название}_agent.py` в папке `src/agents/`.

**Пример структуры:**

```python
"""
Агент для [описание назначения]
"""
from .tools.ваш_инструмент import YourTool
from .tools.call_manager_tools import CallManager
from .base_agent import BaseAgent
from ..services.langgraph_service import LangGraphService


class YourAgent(BaseAgent):
    """Агент для [описание]"""
    
    def __init__(self, langgraph_service: LangGraphService):
        instruction = """[Ваши инструкции для агента]"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[YourTool, CallManager],  # Список инструментов
            agent_name="Название агента"
        )
```

**Важно:**
- Имя класса должно заканчиваться на `Agent`
- Имя файла должно заканчиваться на `_agent.py`
- Всегда включайте `CallManager` в список инструментов

### Шаг 2: Добавление стадии в DialogueStage

Откройте `dialogue_stages.py` и добавьте новую стадию в enum:

```python
class DialogueStage(str, Enum):
    """Стадии диалога"""
    GREETING = "greeting"
    VIEW_MY_BOOKING = "view_my_booking"
    YOUR_STAGE = "your_stage"  # Добавьте здесь
```

**Важно:** Значение стадии должно быть в нижнем регистре и совпадать с ключом, который будет использоваться в графе.

### Шаг 3: Обновление MainGraph

Откройте `src/graph/main_graph.py` и выполните следующие изменения:

#### 3.1. Добавьте импорт агента

```python
from ..agents.your_agent import YourAgent
```

#### 3.2. Добавьте создание агента в кэш

В методе `__init__`, в блоке создания кэша агентов:

```python
MainGraph._agents_cache[cache_key] = {
    'stage_detector': StageDetectorAgent(langgraph_service),
    'greeting': GreetingAgent(langgraph_service),
    'view_my_booking': ViewMyBookingAgent(langgraph_service),
    'your_stage': YourAgent(langgraph_service),  # Добавьте здесь
}
```

#### 3.3. Добавьте атрибут агента

После блока с кэшем:

```python
self.stage_detector = agents['stage_detector']
self.greeting_agent = agents['greeting']
self.view_my_booking_agent = agents['view_my_booking']
self.your_agent = agents['your_stage']  # Добавьте здесь
```

#### 3.4. Добавьте узел в граф

В методе `_create_graph`, в блоке добавления узлов:

```python
graph.add_node("detect_stage", self._detect_stage)
graph.add_node("handle_greeting", self._handle_greeting)
graph.add_node("handle_view_my_booking", self._handle_view_my_booking)
graph.add_node("handle_your_stage", self._handle_your_stage)  # Добавьте здесь
```

#### 3.5. Добавьте маршрутизацию

В методе `_create_graph`, в блоке `add_conditional_edges`:

```python
graph.add_conditional_edges(
    "detect_stage",
    self._route_after_detect,
    {
        "greeting": "handle_greeting",
        "view_my_booking": "handle_view_my_booking",
        "your_stage": "handle_your_stage",  # Добавьте здесь
        "end": END
    }
)
```

#### 3.6. Добавьте ребро к END

```python
graph.add_edge("handle_greeting", END)
graph.add_edge("handle_view_my_booking", END)
graph.add_edge("handle_your_stage", END)  # Добавьте здесь
```

#### 3.7. Обновите тип возврата маршрутизации

В методе `_route_after_detect`, обновите тип:

```python
def _route_after_detect(self, state: ConversationState) -> Literal[
    "greeting", "view_my_booking", "your_stage", "end"  # Добавьте здесь
]:
```

#### 3.8. Добавьте стадию в список валидных стадий

```python
valid_stages = [
    "greeting", "view_my_booking", "your_stage"  # Добавьте здесь
]
```

#### 3.9. Создайте обработчик агента

Добавьте метод обработки в конец класса:

```python
def _handle_your_stage(self, state: ConversationState) -> ConversationState:
    """Обработка [описание стадии]"""
    logger.info("Обработка [описание стадии]")
    message = state["message"]
    previous_response_id = state.get("previous_response_id")
    chat_id = state.get("chat_id")
    
    agent_result = self.your_agent(message, previous_response_id, chat_id=chat_id)
    return self._process_agent_result(self.your_agent, agent_result, state, "YourAgent")
```

### Шаг 4: Обновление StageDetectorAgent

Откройте `stage_detector_agent.py` и добавьте описание новой стадии в инструкцию:

```python
instruction = """...

**СПИСОК СТАДИЙ:**

- greeting: Клиент только начинает диалог, здоровается или пишет впервые за долгое время.
- view_my_booking: Клиент хочет посмотреть свои предстоящие записи ("на когда я записан?", "какие у меня записи?").
- your_stage: [Описание, когда использовать эту стадию]  # Добавьте здесь

Верни ТОЛЬКО одно слово - название стадии. 
ИСКЛЮЧЕНИЕ: используй инструмент CallManager, если клиент явно просит позвать менеджера либо ругается."""
```

### Шаг 5: Добавление экспорта в __init__.py

Откройте `src/agents/__init__.py` и добавьте:

```python
from .your_agent import YourAgent

__all__ = [
    "BaseAgent",
    "DialogueStage",
    "StageDetectorAgent",
    "StageDetection",
    "GreetingAgent",
    "ViewMyBookingAgent",
    "YourAgent",  # Добавьте здесь
]
```

### Шаг 6: Обновление registry.py

Откройте `src/agents/registry.py` и добавьте в маппинг `agent_names`:

```python
agent_names = {
    'greeting_agent': 'Приветствие',
    'view_my_booking_agent': 'Просмотр моей записи',
    'your_agent': 'Читаемое название',  # Добавьте здесь
}
```

---

## Удаление агента

### Шаг 1: Удаление файла агента

Удалите файл `{название}_agent.py` из папки `src/agents/`.

### Шаг 2: Удаление стадии из DialogueStage

Откройте `dialogue_stages.py` и удалите соответствующую стадию из enum.

### Шаг 3: Очистка MainGraph

Откройте `src/graph/main_graph.py` и выполните обратные действия:

1. Удалите импорт агента
2. Удалите создание агента из кэша
3. Удалите атрибут агента
4. Удалите узел из графа
5. Удалите маршрутизацию из `add_conditional_edges`
6. Удалите ребро к END
7. Удалите стадию из типа возврата `_route_after_detect`
8. Удалите стадию из списка валидных стадий
9. Удалите метод обработчика `_handle_*`

### Шаг 4: Очистка StageDetectorAgent

Откройте `stage_detector_agent.py` и удалите описание стадии из инструкции.

### Шаг 5: Удаление экспорта из __init__.py

Откройте `src/agents/__init__.py` и удалите импорт и экспорт агента.

### Шаг 6: Очистка registry.py

Откройте `src/agents/registry.py` и удалите запись из маппинга `agent_names`.

---

## Чеклист при создании агента

- [ ] Создан файл `*_agent.py` с классом, наследующимся от `BaseAgent`
- [ ] Добавлена стадия в `dialogue_stages.py`
- [ ] Добавлен импорт в `main_graph.py`
- [ ] Добавлено создание агента в кэш
- [ ] Добавлен атрибут агента
- [ ] Добавлен узел в граф
- [ ] Добавлена маршрутизация
- [ ] Добавлено ребро к END
- [ ] Обновлен тип возврата `_route_after_detect`
- [ ] Добавлена стадия в список валидных стадий
- [ ] Создан обработчик `_handle_*`
- [ ] Обновлена инструкция в `stage_detector_agent.py`
- [ ] Добавлен экспорт в `__init__.py`
- [ ] Добавлена запись в `registry.py`

## Чеклист при удалении агента

- [ ] Удален файл агента
- [ ] Удалена стадия из `dialogue_stages.py`
- [ ] Удален импорт из `main_graph.py`
- [ ] Удалено создание агента из кэша
- [ ] Удален атрибут агента
- [ ] Удален узел из графа
- [ ] Удалена маршрутизация
- [ ] Удалено ребро к END
- [ ] Удалена стадия из типа возврата `_route_after_detect`
- [ ] Удалена стадия из списка валидных стадий
- [ ] Удален обработчик `_handle_*`
- [ ] Удалено описание из `stage_detector_agent.py`
- [ ] Удален экспорт из `__init__.py`
- [ ] Удалена запись из `registry.py`

---

## Важные замечания

1. **Именование:** Имя стадии должно быть в нижнем регистре и совпадать во всех файлах
2. **Инструменты:** Всегда включайте `CallManager` в список инструментов агента
3. **Кэш:** После изменений в `main_graph.py` может потребоваться перезапуск приложения для очистки кэша
4. **Тестирование:** После создания агента обязательно протестируйте маршрутизацию через `StageDetectorAgent`
5. **Логирование:** Имя агента в `agent_name` будет использоваться в логах

