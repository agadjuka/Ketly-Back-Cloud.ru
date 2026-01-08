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

"""Обновление промптов и стадий в структуре проекта."""

from pathlib import Path
from typing import Optional
from registry_loader import setup_packages, load_registry
from prompt_utils import update_prompt


class PromptUpdater:
    """Класс для обновления промптов в структуре проекта."""
    
    def __init__(self, project_root: Path):
        """Инициализация обновлятора.
        
        Args:
            project_root: Корневая директория проекта
        """
        self.project_root = Path(project_root)
        self.router_file = self.project_root / "src" / "agents" / "stage_detector_agent.py"
        self.agents_dir = self.project_root / "src" / "agents"
    
    def _read_content(self, file_path: Path) -> str:
        """Читает содержимое файла."""
        return file_path.read_text(encoding="utf-8")
    
    def _write_content(self, file_path: Path, content: str) -> None:
        """Записывает содержимое в файл."""
        file_path.write_text(content, encoding="utf-8")
    
    def update_system_prompt(self, new_prompt: str) -> None:
        """Обновляет основной системный промпт (в текущей структуре не используется)."""
        # В текущей структуре нет отдельного системного промпта
        # Каждый агент имеет свой собственный промпт
        pass
    
    def update_router_prompt(self, new_prompt: str) -> None:
        """Обновляет промпт роутера в stage_detector_agent.py."""
        content = self._read_content(self.router_file)
        new_content = update_prompt(content, new_prompt)
        self._write_content(self.router_file, new_content)
    
    def update_stage_prompt(self, stage_key: str, new_prompt: str) -> None:
        """Обновляет промпт стадии в файле агента."""
        try:
            setup_packages(self.project_root, [
                ("src", self.project_root / "src"),
                ("src.agents", self.agents_dir),
            ])
            
            registry_file = self.agents_dir / "registry.py"
            registry_module = load_registry(registry_file, "src.agents.registry", "src.agents")
            
            if registry_module is None:
                raise FileNotFoundError(f"Файл реестра не найден: {registry_file}")
            
            registry = registry_module.get_registry()
            agent_info = registry.get_agent_info(stage_key)
            
            if not agent_info:
                raise ValueError(f"Неизвестная стадия: {stage_key}. Агент должен быть автоматически обнаружен в папке src/agents/")
            
            file_name = agent_info.get("file")
            if not file_name:
                raise ValueError(f"Для стадии {stage_key} не указан файл в реестре")
            
            stage_file = self.agents_dir / file_name
            if not stage_file.exists():
                raise FileNotFoundError(f"Файл агента не найден: {stage_file}")
            
            content = self._read_content(stage_file)
            new_content = update_prompt(content, new_prompt)
            self._write_content(stage_file, new_content)
        except Exception as e:
            raise ValueError(f"Не удалось загрузить реестр агентов. Убедитесь, что src/agents/registry.py существует. Ошибка: {e}")
    
