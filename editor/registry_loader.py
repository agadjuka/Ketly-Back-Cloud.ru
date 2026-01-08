"""
Вспомогательный модуль для загрузки реестров без циклических импортов.
"""

import sys
import importlib.util
import types
from pathlib import Path
from typing import Any


def setup_packages(project_root: Path, packages: list[tuple[str, Path]]) -> None:
    """
    Создает структуру пакетов для корректной работы относительных импортов.
    
    Args:
        project_root: Корень проекта
        packages: Список кортежей (имя_пакета, путь_к_пакету)
    """
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    for pkg_name, pkg_path in packages:
        if pkg_name not in sys.modules:
            pkg = types.ModuleType(pkg_name)
            pkg.__path__ = [str(pkg_path)]
            sys.modules[pkg_name] = pkg
            
            # Связываем с родительским пакетом
            if "." in pkg_name:
                parent_name = ".".join(pkg_name.split(".")[:-1])
                if parent_name in sys.modules:
                    setattr(sys.modules[parent_name], pkg_name.split(".")[-1], pkg)


def load_registry(registry_file: Path, module_name: str, package_name: str) -> Any:
    """
    Загружает реестр из файла без циклических импортов.
    
    Args:
        registry_file: Путь к файлу реестра
        module_name: Полное имя модуля (например, "src.agents.registry")
        package_name: Имя пакета (например, "src.agents")
    
    Returns:
        Загруженный модуль реестра или None
    """
    if not registry_file.exists():
        return None
    
    spec = importlib.util.spec_from_file_location(module_name, registry_file)
    if spec is None or spec.loader is None:
        return None
    
    registry_module = importlib.util.module_from_spec(spec)
    registry_module.__package__ = package_name
    registry_module.__file__ = str(registry_file)
    sys.modules[module_name] = registry_module
    
    try:
        spec.loader.exec_module(registry_module)
        return registry_module
    except Exception:
        return None


