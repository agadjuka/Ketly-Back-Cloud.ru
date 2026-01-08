"""
Агент для определения стадии диалога (Responses API)
"""
import json
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .base_agent import BaseAgent
from .dialogue_stages import DialogueStage
from ..services.langgraph_service import LangGraphService
from ..services.logger_service import logger
from .tools.call_manager_tools import CallManager


class StageDetection(BaseModel):
    """Структура для определения стадии"""
    stage: str = Field(
        description="Стадия диалога из DialogueStage enum"
    )


class StageDetectorAgent(BaseAgent):
    """Агент для определения стадии диалога"""
    
    def __init__(self, langgraph_service: LangGraphService):
        instruction = """**СПИСОК СТАДИЙ:**

- morning: Если в сообщении есть цифра от 0 до 10 (включительно).
- evening: Если в сообщении есть цифра от 11 до 20 (включительно).

Верни ТОЛЬКО одно слово - название стадии. 
"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[CallManager],
            agent_name="Определитель стадий диалога"
        )
    
    def detect_stage(self, message: str, history: Optional[List[Dict[str, Any]]] = None, chat_id: Optional[str] = None) -> StageDetection:
        """Определение стадии диалога"""
        logger.debug(f"Начало определения стадии для сообщения: {message[:100]}")
        
        # Вызываем базовый метод агента
        response = self(message, history, chat_id=chat_id)
        
        logger.debug(f"Получен ответ от агента определения стадии: {response[:200] if response else 'None/Empty'}")
        
        # Если CallManager был вызван, BaseAgent вернет "[CALL_MANAGER_RESULT]"
        if response == "[CALL_MANAGER_RESULT]":
            logger.info("CallManager был вызван в StageDetectorAgent")
            return StageDetection(stage=DialogueStage.MORNING.value)
        
        # Парсим ответ
        detection = self._parse_response(response)
        
        logger.debug(f"Распознана стадия: {detection.stage}")
        
        # Валидируем стадию
        if detection.stage not in [stage.value for stage in DialogueStage]:
            logger.warning(f"Неизвестная стадия: {detection.stage}, устанавливаю morning")
            logger.warning(f"Доступные стадии: {[stage.value for stage in DialogueStage]}")
            detection.stage = DialogueStage.MORNING.value
        
        return detection
    
    def _parse_response(self, response: str) -> StageDetection:
        """Парсинг ответа агента в StageDetection"""
        if not response:
            logger.warning("Пустой ответ от агента определения стадии")
            return StageDetection(stage=DialogueStage.MORNING.value)
        
        # Убираем лишние пробелы и переносы строк, приводим к нижнему регистру
        response_clean = response.strip().lower()
        
        # Получаем все возможные стадии
        valid_stages = [stage.value for stage in DialogueStage]
        
        # ШАГ 1: Проверяем точное совпадение (самый надежный способ)
        if response_clean in valid_stages:
            logger.debug(f"Найдено точное совпадение стадии: {response_clean}")
            return StageDetection(stage=response_clean)
        
        # ШАГ 2: Извлекаем первое слово из ответа (агент должен вернуть только название стадии)
        first_word = response_clean.split()[0] if response_clean.split() else ""
        if first_word in valid_stages:
            logger.debug(f"Найдена стадия в первом слове: {first_word}")
            return StageDetection(stage=first_word)
        
        # ШАГ 3: Ищем стадию как целое слово через регулярные выражения
        sorted_stages = sorted(valid_stages, key=len, reverse=True)
        for stage in sorted_stages:
            pattern = r'\b' + re.escape(stage) + r'\b'
            if re.search(pattern, response_clean):
                logger.debug(f"Найдена стадия через regex: {stage}")
                return StageDetection(stage=stage)
        
        # ШАГ 4: Пытаемся найти в JSON
        json_start = response_clean.find('{')
        json_end = response_clean.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_clean[json_start:json_end]
            try:
                data = json.loads(json_str)
                stage = data.get('stage', '').lower().strip()
                if stage in valid_stages:
                    logger.debug(f"Найдена стадия в JSON: {stage}")
                    return StageDetection(stage=stage)
            except json.JSONDecodeError:
                pass
        
        # ШАГ 5: Последняя попытка - ищем подстроку
        for stage in sorted_stages:
            if stage in response_clean:
                logger.warning(f"Найдена стадия как подстрока (может быть неточно): {stage} в ответе: {response_clean}")
                return StageDetection(stage=stage)
        
        # Fallback
        logger.warning(f"Не удалось определить стадию из ответа: {response_clean}")
        logger.warning(f"Доступные стадии: {valid_stages}")
        return StageDetection(stage=DialogueStage.MORNING.value)
