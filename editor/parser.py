# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Парсер для извлечения промптов и стадий из структуры проекта."""

from pathlib import Path
from typing import Dict, List, Any
from registry_loader import setup_packages, load_registry
from prompt_utils import extract_prompt


class PromptParser:
    """Класс для парсинга промптов из структуры проекта."""
    
    def __init__(self, project_root: Path):
        """Инициализация парсера.
        
        Args:
            project_root: Корневая директория проекта
        """
        self.project_root = Path(project_root)
        self.router_file = self.project_root / "src" / "agents" / "stage_detector_agent.py"
        self.agents_dir = self.project_root / "src" / "agents"
    
    def parse(self) -> Dict[str, Any]:
        """Извлекает все промпты и стадии из проекта.
        
        Returns:
            Словарь с промптами и стадиями
        """
        router_content = self.router_file.read_text(encoding="utf-8")
        
        return {
            "router_prompt": self._extract_router_prompt(router_content),
            "stages": self._extract_stages(router_content)
        }
    
    def _extract_router_prompt(self, content: str) -> str:
        """Извлекает промпт роутера из stage_detector_agent.py."""
        return extract_prompt(content)
    
    def _extract_stages(self, router_content: str) -> List[Dict[str, str]]:
        """Извлекает информацию о стадиях из реестра агентов."""
        try:
            setup_packages(self.project_root, [
                ("src", self.project_root / "src"),
                ("src.agents", self.agents_dir),
            ])
            
            registry_file = self.agents_dir / "registry.py"
            registry_module = load_registry(registry_file, "src.agents.registry", "src.agents")
            
            if registry_module is None:
                print(f"[WARNING] Не удалось загрузить реестр из {registry_file}")
                return []
            
            registry = registry_module.get_registry()
            agents = registry.get_all_agents()
            
            stages = []
            for agent in agents:
                if agent["key"] == "stage_detector":
                    continue
                    
                prompt = self._extract_stage_prompt_from_file(agent["key"], agent["file"])
                stages.append({
                    "key": agent["key"],
                    "name": agent["name"],
                    "prompt": prompt
                })
                print(f"[DEBUG] Добавлена стадия: {agent['key']} - {agent['name']}, промпт: {'найден' if prompt else 'НЕ НАЙДЕН'}")
            
            print(f"[DEBUG] Всего найдено стадий: {len(stages)}")
            return stages
        except Exception as e:
            import traceback
            print(f"[WARNING] Не удалось загрузить агентов из реестра: {e}")
            print(f"[WARNING] Traceback: {traceback.format_exc()}")
            return []
    
    def _extract_stage_prompt_from_file(self, stage_key: str, file_name: str) -> str:
        """Извлекает промпт для конкретной стадии из файла агента."""
        stage_file = self.agents_dir / file_name
        if not stage_file.exists():
            print(f"[WARNING] Файл агента не найден: {stage_file}")
            return ""
        
        try:
            content = stage_file.read_text(encoding="utf-8")
            prompt = extract_prompt(content)
            if prompt:
                print(f"[DEBUG] Найден промпт для {stage_key} в {file_name}")
            else:
                print(f"[WARNING] Промпт не найден в файле {file_name}")
            return prompt
        except Exception as e:
            print(f"[ERROR] Ошибка при чтении файла {file_name}: {e}")
            return ""
