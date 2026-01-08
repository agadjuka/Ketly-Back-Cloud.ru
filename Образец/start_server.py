#!/usr/bin/env python3
"""
Wrapper скрипт для запуска uvicorn с гарантированным логированием
"""
import os
import sys

# КРИТИЧНО: Все логи должны идти в stdout БЕЗ буферизации
# Отключаем буферизацию для немедленного вывода
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
else:
    # Для старых версий Python
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True)

print("=" * 80, flush=True)
print("🚀 START_SERVER.PY: Начало запуска", flush=True)
print("=" * 80, flush=True)
print(f"📂 Рабочая директория: {os.getcwd()}", flush=True)
print(f"🐍 Python: {sys.version}", flush=True)
print(f"📦 PYTHONPATH: {os.environ.get('PYTHONPATH', 'не задан')}", flush=True)

# Проверяем наличие main.py
main_py_path = "/app/main.py"
if os.path.exists(main_py_path):
    print(f"✅ Файл {main_py_path} найден", flush=True)
    print(f"📏 Размер файла: {os.path.getsize(main_py_path)} байт", flush=True)
else:
    print(f"❌ Файл {main_py_path} НЕ НАЙДЕН!", flush=True)
    print("📂 Содержимое /app:", flush=True)
    try:
        for item in os.listdir("/app"):
            print(f"  - {item}", flush=True)
    except Exception as e:
        print(f"❌ Ошибка чтения директории: {e}", flush=True)
    sys.exit(1)

# Проверяем импорт uvicorn
print("\n🔍 Проверка uvicorn...", flush=True)
try:
    import uvicorn
    print(f"✅ uvicorn импортирован, версия: {uvicorn.__version__}", flush=True)
except ImportError as e:
    print(f"❌ ОШИБКА ИМПОРТА UVICORN: {e}", flush=True)
    sys.exit(1)

# Пробуем импортировать приложение
print("\n🔍 Проверка импорта main:app...", flush=True)
try:
    # Меняем рабочую директорию для гарантии
    if os.path.exists("/app"):
        os.chdir("/app")
        sys.path.insert(0, "/app")
    
    print(f"📂 Текущая директория: {os.getcwd()}", flush=True)
    print(f"📦 sys.path[0]: {sys.path[0]}", flush=True)
    
    # Пробуем импортировать
    import main
    print("✅ Модуль main импортирован", flush=True)
    
    # Проверяем наличие app
    if hasattr(main, 'app'):
        print("✅ Объект app найден в модуле main", flush=True)
        print(f"📝 Тип app: {type(main.app)}", flush=True)
    else:
        print("❌ Объект app НЕ найден в модуле main!", flush=True)
        print(f"📋 Доступные атрибуты: {dir(main)[:20]}", flush=True)
        sys.exit(1)
        
except Exception as e:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА: {e}", flush=True)
    import traceback
    print("📋 Полная трассировка:", flush=True)
    print(traceback.format_exc(), flush=True)
    sys.exit(1)

print("\n" + "=" * 80, flush=True)
print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ, ЗАПУСКАЕМ UVICORN", flush=True)
print("=" * 80 + "\n", flush=True)

# Запускаем uvicorn
try:
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )
except KeyboardInterrupt:
    print("\n⚠️ Получен сигнал остановки", flush=True)
except Exception as e:
    print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА UVICORN: {e}", flush=True)
    import traceback
    print(traceback.format_exc(), flush=True)
    sys.exit(1)

