"""
Скрипт для запуска эдитора промптов и инструментов.
"""

from pathlib import Path
import sys
import importlib.util

# Добавляем корень проекта в путь
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Добавляем путь к Editor для корректных импортов внутри app.py
editor_path = project_root / "Editor"
if str(editor_path) not in sys.path:
    sys.path.insert(0, str(editor_path))

# Загружаем Flask приложение напрямую из файла
app_path = editor_path / "app.py"
spec = importlib.util.spec_from_file_location("editor_app", app_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Не удалось загрузить модуль из {app_path}")

editor_module = importlib.util.module_from_spec(spec)
# Устанавливаем правильные атрибуты модуля для корректных импортов
editor_module.__file__ = str(app_path)
editor_module.__package__ = "Editor"
spec.loader.exec_module(editor_module)
app = editor_module.app

if __name__ == "__main__":
    print("=" * 60)
    print("Эдитор промптов и инструментов")
    print("=" * 60)
    print(f"Доступен по адресу: http://localhost:5000")
    print("=" * 60)
    app.run(host="localhost", port=5000, debug=True)
