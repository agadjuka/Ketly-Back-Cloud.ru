"""
Реестр агентов для управления списком доступных агентов.

Этот реестр используется эдитором для получения списка всех агентов.
При создании нового агента он автоматически обнаруживается из папки агентов.
"""

from typing import Dict, List, Optional
from pathlib import Path


class AgentRegistry:
    """Реестр агентов."""
    
    def __init__(self):
        """Инициализация реестра."""
        self._agents: Dict[str, Dict[str, str]] = {}
        self._load_agents()
    
    def _load_agents(self) -> None:
        """Загружает информацию об агентах из папки агентов."""
        # Получаем путь к папке агентов
        agents_dir = Path(__file__).parent
        
        # Исключаем файлы, которые не являются агентами
        excluded_files = {'base_agent.py', 'stage_detector_agent.py', '__init__.py', 'registry.py', 'dialogue_stages.py'}
        
        # Маппинг ключей агентов на читаемые имена
        agent_names = {
            'admin_agent': 'Административный агент',
            'demo_agent': 'Демонстрационный агент',
            'demo_setup_agent': 'Агент настройки демонстрации',
        }
        
        # Находим все файлы агентов
        for agent_file in agents_dir.glob('*_agent.py'):
            if agent_file.name in excluded_files:
                continue
            
            # Получаем ключ агента из имени файла (без расширения)
            file_name = agent_file.stem  # например, 'greeting_agent'
            key = file_name.replace('_agent', '')  # например, 'greeting'
            
            # Получаем читаемое имя
            name = agent_names.get(file_name, file_name.replace('_', ' ').title())
            
            self._agents[key] = {
                "file": agent_file.name,
                "name": name,
            }
    
    def get_agent_info(self, key: str) -> Optional[Dict[str, str]]:
        """
        Получить информацию об агенте по ключу.
        
        Args:
            key: Ключ агента (например, "greeting")
            
        Returns:
            Словарь с информацией об агенте или None
        """
        return self._agents.get(key)
    
    def get_all_agents(self) -> List[Dict[str, str]]:
        """
        Получить список всех зарегистрированных агентов.
        
        Returns:
            Список словарей с информацией об агентах
        """
        return [
            {"key": key, **info}
            for key, info in self._agents.items()
        ]
    
    def get_agent_file(self, key: str) -> Optional[str]:
        """
        Получить имя файла агента по ключу.
        
        Args:
            key: Ключ агента
            
        Returns:
            Имя файла или None
        """
        info = self.get_agent_info(key)
        return info.get("file") if info else None


# Глобальный экземпляр реестра
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """
    Получить глобальный экземпляр реестра.
    
    Returns:
        Экземпляр реестра агентов
    """
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
