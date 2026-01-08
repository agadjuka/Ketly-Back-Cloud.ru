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

"""Flask приложение для редактирования промптов агента."""

from flask import Flask, render_template, request, jsonify
from pathlib import Path
import sys

# Добавляем родительскую директорию в путь для импорта модулей
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Добавляем Editor в путь для импорта
editor_path = Path(__file__).parent
sys.path.insert(0, str(editor_path))

from parser import PromptParser
from updater import PromptUpdater
from tools_helper import get_all_tools, get_tool_info, execute_tool

# Указываем путь к шаблонам
template_dir = Path(__file__).parent / "templates"
app = Flask(__name__, template_folder=str(template_dir))

# Путь к корню проекта (относительный)
parser = PromptParser(project_root)
updater = PromptUpdater(project_root)


@app.route("/")
def index():
    """Главная страница редактора."""
    return render_template("index.html")


@app.route("/api/prompts", methods=["GET"])
def get_prompts():
    """Получить все промпты и стадии."""
    try:
        data = parser.parse()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompts/router", methods=["PUT"])
def update_router_prompt():
    """Обновить промпт роутера."""
    try:
        new_prompt = request.json.get("prompt")
        if not new_prompt:
            return jsonify({"error": "Промпт не может быть пустым"}), 400
        
        updater.update_router_prompt(new_prompt)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stages/<stage_name>/prompt", methods=["PUT"])
def update_stage_prompt(stage_name):
    """Обновить промпт стадии."""
    try:
        new_prompt = request.json.get("prompt")
        if not new_prompt:
            return jsonify({"error": "Промпт не может быть пустым"}), 400
        
        updater.update_stage_prompt(stage_name, new_prompt)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tools", methods=["GET"])
def get_tools():
    """Получить список всех инструментов."""
    try:
        tools = get_all_tools()
        tools_info = [get_tool_info(tool) for tool in tools]
        
        # Логируем для отладки
        print(f"[DEBUG API] Запрошены инструменты, возвращено: {len(tools_info)}")
        if tools_info:
            print(f"[DEBUG API] Имена инструментов: {[t['name'] for t in tools_info]}")
        
        return jsonify({"tools": tools_info})
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR API] Ошибка получения инструментов: {error_msg}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/tools/<tool_name>/execute", methods=["POST"])
def execute_tool_endpoint(tool_name):
    """Выполнить инструмент с заданными аргументами."""
    try:
        args = request.json.get("args", {})
        result = execute_tool(tool_name, args)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="localhost", port=5000, debug=True)

