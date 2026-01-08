"""
Система логирования реальных запросов и ответов LLM
Фиксирует ровно то, что получает и отправляет LLM через SDK
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from threading import Lock


class LLMRequestLogger:
    """Логгер для записи реальных запросов и ответов LLM через SDK"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Проверяем, нужно ли сохранять логи в файлы
        # По умолчанию включено, можно отключить через переменную окружения DISABLE_DEBUG_LOGS=true
        self.logging_enabled = os.getenv('DISABLE_DEBUG_LOGS', 'false').lower() != 'true'
        
        if self.logging_enabled:
            # Создаём папку для логов только если включено
            try:
                self.logs_dir = Path("logs")
                self.logs_dir.mkdir(exist_ok=True)
            except (PermissionError, OSError) as e:
                # Если нет прав на создание папки, отключаем файловое логирование
                print(f"⚠️ Не удалось создать папку logs: {e}. Файловое логирование отключено.")
                self.logging_enabled = False
                self.logs_dir = None
        else:
            self.logs_dir = None
        
        # Файл для текущего запроса
        self.current_log_file: Optional[Path] = None
        self.request_start_time: Optional[datetime] = None
        self._file_lock = Lock()
        self._request_counter = 0
        
        self._initialized = True
    
    def start_new_request(self) -> Optional[Path]:
        """Начать новый запрос - создать новый файл лога"""
        if not self.logging_enabled:
            return None
        
        with self._file_lock:
            # Закрываем предыдущий файл если был
            if self.current_log_file:
                try:
                    with open(self.current_log_file, 'a', encoding='utf-8') as f:
                        f.write(f"\n{'='*80}\n")
                        f.write(f"REQUEST COMPLETED\n")
                        f.write(f"{'='*80}\n")
                except:
                    pass
            
            # Создаём новый файл для текущего запроса
            self._request_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            self.current_log_file = self.logs_dir / f"llm_request_{timestamp}.log"
            self.request_start_time = datetime.now()
            
            # Записываем заголовок запроса
            try:
                with open(self.current_log_file, 'w', encoding='utf-8') as f:
                    f.write(f"{'='*80}\n")
                    f.write(f"NEW REQUEST STARTED\n")
                    f.write(f"{'='*80}\n")
                    f.write(f"Request ID: {self._request_counter}\n")
                    f.write(f"Start Time: {self.request_start_time.isoformat()}\n")
                    f.write(f"Log File: {self.current_log_file.name}\n")
                    f.write(f"{'='*80}\n\n")
            except Exception as e:
                print(f"Ошибка создания файла лога: {e}")
            
            return self.current_log_file
    
    def _get_log_file(self) -> Optional[Path]:
        """Получить файл лога для текущего запроса"""
        if not self.logging_enabled:
            return None
        if self.current_log_file is None:
            return self.start_new_request()
        return self.current_log_file
    
    def _write_raw(self, data: str):
        """Записать сырые данные в файл"""
        if not self.logging_enabled:
            return
        
        log_file = self._get_log_file()
        if log_file is None:
            return
        
        with self._file_lock:
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(data)
                    f.write('\n')
                    f.flush()
            except Exception as e:
                print(f"Ошибка записи в лог: {e}")
    
    def log_request_to_llm(
        self,
        agent_name: str,
        thread_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        instruction: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        messages: Optional[List[Any]] = None
    ):
        """
        Логировать запрос к LLM - то, что реально отправляется через API
        
        Args:
            agent_name: Имя агента
            thread_id: ID thread (устаревший параметр, всегда None для Responses API)
            assistant_id: ID assistant (устаревший параметр, всегда None для Responses API)
            instruction: Инструкция для модели
            tools: Список инструментов (классы инструментов)
            messages: Список сообщений (conversation_history)
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"\n{'='*80}\n"
        log_entry += f"[{timestamp}] REQUEST TO LLM (EXACT DATA SENT TO API)\n"
        log_entry += f"{'='*80}\n"
        log_entry += f"Agent: {agent_name}\n"
        log_entry += "\n"
        
        # Формируем JSON структуру запроса, как она реально отправляется в API
        request_data = {}
        
        # Инструкция
        if instruction:
            request_data['instruction'] = instruction
            log_entry += f"--- INSTRUCTION ---\n{instruction}\n\n"
        
        # Инструменты - извлекаем реальную JSON схему
        if tools:
            log_entry += f"--- TOOLS (JSON SCHEMA SENT TO API) ---\n"
            tools_schema = []
            for tool in tools:
                try:
                    # Если это класс Pydantic модели, используем model_json_schema
                    if hasattr(tool, 'model_json_schema'):
                        schema = tool.model_json_schema()
                        tool_json = {
                            'type': 'function',
                            'function': {
                                'name': schema.get('title', tool.__name__),
                                'description': schema.get('description', ''),
                                'parameters': {
                                    'type': 'object',
                                    'properties': schema.get('properties', {}),
                                    'required': schema.get('required', [])
                                }
                            }
                        }
                    else:
                        # Иначе пытаемся извлечь из SDK объекта
                        tool_json = self._extract_tool_schema(tool)
                    
                    tools_schema.append(tool_json)
                    log_entry += json.dumps(tool_json, ensure_ascii=False, indent=2) + "\n\n"
                except Exception as e:
                    log_entry += f"Error extracting tool schema: {e}\n"
                    import traceback
                    log_entry += f"Traceback: {traceback.format_exc()}\n"
            request_data['tools'] = tools_schema
        
        # Сообщения из thread - извлекаем реальный формат
        if messages:
            log_entry += f"--- MESSAGES (EXACT FORMAT SENT TO API) ---\n"
            log_entry += f"Total messages: {len(messages)}\n\n"
            messages_data = []
            for i, msg in enumerate(messages):
                try:
                    msg_json = self._extract_message_data(msg)
                    messages_data.append(msg_json)
                    log_entry += f"Message {i+1}:\n"
                    log_entry += json.dumps(msg_json, ensure_ascii=False, indent=2) + "\n\n"
                except Exception as e:
                    log_entry += f"Error extracting message {i+1}: {e}\n"
            request_data['messages'] = messages_data
        
        # Полный JSON запроса
        log_entry += f"--- FULL REQUEST JSON (AS SENT TO API) ---\n"
        log_entry += json.dumps(request_data, ensure_ascii=False, indent=2) + "\n"
        
        self._write_raw(log_entry)
    
    def log_response_from_llm(
        self,
        agent_name: str,
        response_text: Optional[str] = None,
        tool_calls: Optional[List[Any]] = None,
        raw_response: Optional[Any] = None
    ):
        """
        Логировать ответ от LLM - то, что реально получено от API
        
        Args:
            agent_name: Имя агента
            response_text: Текст ответа
            tool_calls: Список вызовов инструментов
            raw_response: Сырой объект ответа
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"\n{'='*80}\n"
        log_entry += f"[{timestamp}] RESPONSE FROM LLM (EXACT DATA RECEIVED FROM API)\n"
        log_entry += f"{'='*80}\n"
        log_entry += f"Agent: {agent_name}\n\n"
        
        response_data = {}
        
        # Информация о токенах (usage)
        usage_info = self._extract_usage_info(raw_response)
        if usage_info:
            response_data['usage'] = usage_info
            log_entry += f"--- TOKEN USAGE (TOKENS USED IN THIS CYCLE) ---\n"
            log_entry += json.dumps(usage_info, ensure_ascii=False, indent=2) + "\n\n"
        
        # Текст ответа
        if response_text is not None:
            response_data['text'] = response_text
            log_entry += f"--- RESPONSE TEXT ---\n{response_text}\n\n"
        
        # Вызовы инструментов
        if tool_calls:
            log_entry += f"--- TOOL CALLS (EXACT FORMAT FROM API) ---\n"
            tool_calls_data = []
            for i, tool_call in enumerate(tool_calls):
                try:
                    tool_call_json = self._extract_tool_call_data(tool_call)
                    tool_calls_data.append(tool_call_json)
                    log_entry += f"Tool Call {i+1}:\n"
                    log_entry += json.dumps(tool_call_json, ensure_ascii=False, indent=2) + "\n\n"
                except Exception as e:
                    log_entry += f"Error extracting tool call {i+1}: {e}\n"
            response_data['tool_calls'] = tool_calls_data
        
        # Полный необработанный JSON ответа
        log_entry += f"--- FULL RESPONSE JSON (AS RECEIVED FROM API) ---\n"
        if raw_response and hasattr(raw_response, '_raw_json'):
            # Сохраняем полный необработанный JSON из ответа API
            log_entry += json.dumps(raw_response._raw_json, ensure_ascii=False, indent=2) + "\n"
        else:
            # Если нет полного JSON, сохраняем обработанные данные
            log_entry += json.dumps(response_data, ensure_ascii=False, indent=2) + "\n"
        
        self._write_raw(log_entry)
    
    def log_tool_results_to_llm(
        self,
        agent_name: str,
        tool_results: List[Dict[str, Any]]
    ):
        """
        Логировать результаты инструментов, отправляемые обратно в LLM
        
        Args:
            agent_name: Имя агента
            tool_results: Список результатов инструментов
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"\n{'='*80}\n"
        log_entry += f"[{timestamp}] TOOL RESULTS TO LLM (EXACT DATA SENT TO API)\n"
        log_entry += f"{'='*80}\n"
        log_entry += f"Agent: {agent_name}\n\n"
        
        log_entry += f"--- TOOL RESULTS (EXACT FORMAT SENT TO API) ---\n"
        log_entry += json.dumps(tool_results, ensure_ascii=False, indent=2, default=str) + "\n"
        
        self._write_raw(log_entry)
    
    def _extract_tool_schema(self, tool: Any) -> Dict[str, Any]:
        """Извлечь JSON схему инструмента, как она реально отправляется в API"""
        tool_schema = {
            'type': 'function',
            'function': {}
        }
        
        try:
            # Сначала проверяем прямые атрибуты объекта (для FunctionTool из SDK)
            # У FunctionTool атрибуты name, description, parameters находятся напрямую
            if hasattr(tool, 'name'):
                tool_schema['function']['name'] = tool.name
            if hasattr(tool, 'description'):
                tool_schema['function']['description'] = tool.description
            if hasattr(tool, 'parameters'):
                params = tool.parameters
                if isinstance(params, dict):
                    tool_schema['function']['parameters'] = params
                elif hasattr(params, 'model_dump'):
                    tool_schema['function']['parameters'] = params.model_dump()
                elif hasattr(params, 'dict'):
                    tool_schema['function']['parameters'] = params.dict()
                elif hasattr(params, '__dict__'):
                    # Пытаемся получить параметры из __dict__
                    params_dict = {}
                    for key, value in params.__dict__.items():
                        if not key.startswith('_'):
                            try:
                                json.dumps(value, default=str)
                                params_dict[key] = value
                            except:
                                params_dict[key] = str(value)
                    tool_schema['function']['parameters'] = params_dict if params_dict else {}
                else:
                    # Пытаемся преобразовать в dict
                    try:
                        tool_schema['function']['parameters'] = json.loads(json.dumps(params, default=str))
                    except:
                        tool_schema['function']['parameters'] = str(params)
            
            # Если не удалось извлечь через прямые атрибуты, пробуем через function
            if not tool_schema['function'].get('name') and hasattr(tool, 'function'):
                func = tool.function
                
                # Имя функции
                if hasattr(func, 'name'):
                    tool_schema['function']['name'] = func.name
                elif isinstance(func, dict) and 'name' in func:
                    tool_schema['function']['name'] = func['name']
                
                # Описание функции
                if not tool_schema['function'].get('description'):
                    if hasattr(func, 'description'):
                        tool_schema['function']['description'] = func.description
                    elif isinstance(func, dict) and 'description' in func:
                        tool_schema['function']['description'] = func['description']
                
                # Параметры функции
                if not tool_schema['function'].get('parameters'):
                    if hasattr(func, 'parameters'):
                        params = func.parameters
                        if isinstance(params, dict):
                            tool_schema['function']['parameters'] = params
                        elif hasattr(params, 'model_dump'):
                            tool_schema['function']['parameters'] = params.model_dump()
                        elif hasattr(params, 'dict'):
                            tool_schema['function']['parameters'] = params.dict()
                        else:
                            try:
                                tool_schema['function']['parameters'] = json.loads(json.dumps(params, default=str))
                            except:
                                tool_schema['function']['parameters'] = str(params)
                    elif isinstance(func, dict) and 'parameters' in func:
                        tool_schema['function']['parameters'] = func['parameters']
            
            # Если все еще не удалось извлечь, пробуем другие способы
            if not tool_schema['function'].get('name'):
                if hasattr(tool, '__name__'):
                    tool_schema['function']['name'] = tool.__name__
                elif hasattr(tool, '__class__') and hasattr(tool.__class__, '__name__'):
                    tool_schema['function']['name'] = tool.__class__.__name__
            
            # Если все еще пусто, пытаемся получить через model_json_schema из исходного класса
            if not tool_schema['function'].get('name') or not tool_schema['function'].get('parameters'):
                # Пытаемся найти исходный класс инструмента через атрибуты SDK объекта
                if hasattr(tool, '_model') or hasattr(tool, '_pydantic_model'):
                    model = getattr(tool, '_model', None) or getattr(tool, '_pydantic_model', None)
                    if model:
                        try:
                            schema = model.model_json_schema()
                            if not tool_schema['function'].get('name'):
                                tool_schema['function']['name'] = schema.get('title', model.__name__)
                            if not tool_schema['function'].get('description'):
                                tool_schema['function']['description'] = schema.get('description', '')
                            if not tool_schema['function'].get('parameters'):
                                tool_schema['function']['parameters'] = {
                                    'type': 'object',
                                    'properties': schema.get('properties', {}),
                                    'required': schema.get('required', [])
                                }
                        except:
                            pass
            
            # Если все еще пусто, логируем структуру объекта для отладки
            if not tool_schema['function'].get('name'):
                # Пытаемся получить через dir() и getattr
                attrs = [attr for attr in dir(tool) if not attr.startswith('_')]
                if 'name' in attrs:
                    try:
                        tool_schema['function']['name'] = getattr(tool, 'name')
                    except:
                        pass
                
                # Если ничего не помогло, используем строковое представление
                if not tool_schema['function'].get('name'):
                    tool_schema['function']['name'] = str(type(tool).__name__)
                    tool_schema['function']['description'] = f"Tool object: {type(tool)}"
                    tool_schema['function']['parameters'] = {
                        'type': 'object',
                        'properties': {},
                        'required': []
                    }
        
        except Exception as e:
            # В случае ошибки логируем базовую информацию
            tool_schema['function']['name'] = f"Error extracting tool: {type(tool).__name__}"
            tool_schema['function']['description'] = f"Error: {str(e)}"
            tool_schema['function']['parameters'] = {
                'type': 'object',
                'properties': {},
                'required': []
            }
        
        return tool_schema
    
    def _extract_message_data(self, msg: Any) -> Dict[str, Any]:
        """Извлечь данные сообщения, как они реально отправляются в API"""
        message_data = {}
        
        # Роль
        role = None
        if hasattr(msg, 'author') and hasattr(msg.author, 'role'):
            role = msg.author.role
        elif hasattr(msg, 'role'):
            role = msg.role
        
        if role:
            # Нормализуем роль
            role_lower = str(role).lower()
            if role_lower in ['user']:
                message_data['role'] = 'user'
            elif role_lower in ['assistant', 'model']:
                message_data['role'] = 'assistant'
            else:
                message_data['role'] = str(role)
        
        # Содержимое
        content = None
        if hasattr(msg, 'text'):
            content = msg.text
        elif hasattr(msg, 'content'):
            content = msg.content
        elif hasattr(msg, 'parts'):
            parts = msg.parts
            if parts and len(parts) > 0:
                first_part = parts[0]
                if hasattr(first_part, 'text'):
                    content = first_part.text
                elif isinstance(first_part, dict) and 'text' in first_part:
                    content = first_part['text']
        
        if content is not None:
            message_data['content'] = str(content)
        
        return message_data
    
    def _extract_usage_info(self, raw_response: Any) -> Optional[Dict[str, Any]]:
        """
        Извлечь информацию об использовании токенов из ответа LLM
        
        Args:
            raw_response: Сырой объект ответа от LLM
            
        Returns:
            Словарь с информацией о токенах или None
        """
        if not raw_response:
            return None
        
        usage_info = {}
        
        # Проверяем различные возможные атрибуты для информации о токенах
        possible_attrs = [
            'usage',
            'usage_tokens',
            'tokens',
            'token_usage',
            'input_tokens',
            'output_tokens',
            'total_tokens',
            'prompt_tokens',
            'completion_tokens'
        ]
        
        for attr in possible_attrs:
            try:
                value = getattr(raw_response, attr, None)
                if value is not None:
                    # Если это объект с атрибутами, пытаемся извлечь данные
                    if hasattr(value, '__dict__'):
                        usage_info[attr] = {
                            k: v for k, v in value.__dict__.items() 
                            if not k.startswith('_')
                        }
                    elif isinstance(value, dict):
                        usage_info[attr] = value
                    else:
                        usage_info[attr] = value
            except Exception:
                pass
        
        # Также проверяем через dir() все атрибуты, связанные с токенами
        try:
            attrs = [attr for attr in dir(raw_response) if not attr.startswith('_')]
            for attr in attrs:
                attr_lower = attr.lower()
                if 'token' in attr_lower or 'usage' in attr_lower:
                    try:
                        value = getattr(raw_response, attr)
                        if value is not None and attr not in usage_info:
                            if hasattr(value, '__dict__'):
                                usage_info[attr] = {
                                    k: v for k, v in value.__dict__.items() 
                                    if not k.startswith('_')
                                }
                            elif isinstance(value, dict):
                                usage_info[attr] = value
                            else:
                                usage_info[attr] = value
                    except Exception:
                        pass
        except Exception:
            pass
        
        return usage_info if usage_info else None
    
    def _extract_tool_call_data(self, tool_call: Any) -> Dict[str, Any]:
        """Извлечь данные вызова инструмента, как они реально получены от API"""
        tool_call_data = {}
        
        if hasattr(tool_call, 'function'):
            func = tool_call.function
            
            tool_call_data['function'] = {}
            
            # Имя функции
            if hasattr(func, 'name'):
                tool_call_data['function']['name'] = func.name
            elif isinstance(func, dict) and 'name' in func:
                tool_call_data['function']['name'] = func['name']
            
            # Аргументы
            if hasattr(func, 'arguments'):
                args = func.arguments
                if isinstance(args, str):
                    try:
                        tool_call_data['function']['arguments'] = json.loads(args)
                    except:
                        tool_call_data['function']['arguments'] = args
                elif isinstance(args, dict):
                    tool_call_data['function']['arguments'] = args
                else:
                    tool_call_data['function']['arguments'] = str(args)
            elif isinstance(func, dict) and 'arguments' in func:
                tool_call_data['function']['arguments'] = func['arguments']
        
        # ID вызова (если есть)
        if hasattr(tool_call, 'id'):
            tool_call_data['id'] = tool_call.id
        elif isinstance(tool_call, dict) and 'id' in tool_call:
            tool_call_data['id'] = tool_call['id']
        
        return tool_call_data
    
    def log_error(self, agent_name: str, error: Exception, context: Optional[str] = None):
        """Логировать ошибку"""
        timestamp = datetime.now().isoformat()
        log_entry = f"\n{'='*80}\n"
        log_entry += f"[{timestamp}] ERROR\n"
        log_entry += f"{'='*80}\n"
        log_entry += f"Agent: {agent_name}\n"
        if context:
            log_entry += f"Context: {context}\n"
        log_entry += f"Error Type: {type(error).__name__}\n"
        log_entry += f"Error Message: {str(error)}\n"
        import traceback
        log_entry += f"\n--- TRACEBACK ---\n{traceback.format_exc()}\n"
        self._write_raw(log_entry)
    
    def save_request(self, request_data: Dict[str, Any], agent_name: Optional[str] = None):
        """
        Сохранить запрос к LLM как чистый JSON файл (для совместимости с client)
        
        Args:
            request_data: Словарь с данными запроса (то, что реально отправляется в API)
            agent_name: Имя агента (опционально)
        """
        if not self.logging_enabled or not self.logs_dir:
            return None
        
        try:
            with self._file_lock:
                self._request_counter += 1
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                
                # Имя файла с номером запроса и временной меткой
                filename = self.logs_dir / f"request_{self._request_counter}_{timestamp}.json"
                
                # Преобразуем все в словарь
                def to_dict_recursive(obj):
                    if obj is None:
                        return None
                    if isinstance(obj, (str, int, float, bool)):
                        return obj
                    if isinstance(obj, (list, tuple)):
                        return [to_dict_recursive(item) for item in obj]
                    if isinstance(obj, dict):
                        return {k: to_dict_recursive(v) for k, v in obj.items()}
                    if hasattr(obj, 'model_dump'):
                        return to_dict_recursive(obj.model_dump())
                    if hasattr(obj, 'dict'):
                        return to_dict_recursive(obj.dict())
                    if hasattr(obj, '__dict__'):
                        return {k: to_dict_recursive(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
                    return str(obj)
                
                clean_data = to_dict_recursive(request_data)
                
                # Сохраняем ID запроса
                request_id = self._request_counter
                
                # Добавляем метаданные
                final_data = {
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id,
                    "agent_name": agent_name or "Unknown",
                    "request": clean_data
                }
                
                # Сохраняем как форматированный JSON для читаемости
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, ensure_ascii=False, indent=2)
                
                return request_id
                
        except Exception as e:
            print(f"Ошибка сохранения запроса: {e}")
            return None
    
    def save_response(self, response_data: Any, agent_name: Optional[str] = None, request_id: Optional[int] = None):
        """
        Сохранить ответ от LLM как чистый JSON файл (для совместимости с client)
        
        Args:
            response_data: Объект ответа от API
            agent_name: Имя агента (опционально)
            request_id: ID запроса для связи с запросом (опционально)
        """
        if not self.logging_enabled or not self.logs_dir:
            return
        
        try:
            with self._file_lock:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                
                # Имя файла
                if request_id:
                    filename = self.logs_dir / f"response_{request_id}_{timestamp}.json"
                else:
                    filename = self.logs_dir / f"response_{timestamp}.json"
                
                # Преобразуем ответ в словарь
                def to_dict_recursive(obj):
                    if obj is None:
                        return None
                    if isinstance(obj, (str, int, float, bool)):
                        return obj
                    if isinstance(obj, (list, tuple)):
                        return [to_dict_recursive(item) for item in obj]
                    if isinstance(obj, dict):
                        return {k: to_dict_recursive(v) for k, v in obj.items()}
                    if hasattr(obj, 'model_dump'):
                        return to_dict_recursive(obj.model_dump())
                    if hasattr(obj, 'dict'):
                        return to_dict_recursive(obj.dict())
                    if hasattr(obj, '__dict__'):
                        return {k: to_dict_recursive(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
                    return str(obj)
                
                clean_data = to_dict_recursive(response_data)
                
                # Добавляем метаданные
                final_data = {
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id,
                    "agent_name": agent_name or "Unknown",
                    "response": clean_data
                }
                
                # Сохраняем как форматированный JSON для читаемости
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Ошибка сохранения ответа: {e}")


# Глобальный экземпляр логгера
llm_request_logger = LLMRequestLogger()

