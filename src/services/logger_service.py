"""
Красивая система логирования для бота
"""
import os
import sys
import traceback
from datetime import datetime
from typing import Optional


class Colors:
    """ANSI цветовые коды для терминала"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Основные цвета
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Яркие цвета
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


class Logger:
    """Красивый логгер для бота"""
    
    def __init__(self, name: str = "Bot"):
        self.name = name
        self.enable_colors = self._should_enable_colors()
    
    def _should_enable_colors(self) -> bool:
        """Проверяет, поддерживает ли терминал цвета"""
        # Отключаем цвета в Windows CMD (но оставляем в PowerShell и других терминалах)
        if os.name == 'nt':
            return 'ANSICON' in os.environ or 'WT_SESSION' in os.environ
        return True
    
    def _format_time(self) -> str:
        """Форматирует текущее время"""
        return datetime.now().strftime("%H:%M:%S")
    
    def _colorize(self, text: str, color: str) -> str:
        """Применяет цвет к тексту"""
        if self.enable_colors:
            return f"{color}{text}{Colors.RESET}"
        return text
    
    def _log(self, level: str, emoji: str, color: str, message: str, details: Optional[str] = None, use_stderr: bool = False):
        """Базовый метод логирования"""
        timestamp = self._format_time()
        level_colored = self._colorize(f"[{level}]", color)
        emoji_colored = self._colorize(emoji, color)
        
        # Основное сообщение
        main_msg = f"{timestamp} {level_colored} {emoji_colored} {message}"
        
        # Дополнительные детали (если есть)
        if details:
            details_colored = self._colorize(f"({details})", Colors.DIM)
            main_msg += f" {details_colored}"
        
        # Выводим в stderr для ошибок и предупреждений, иначе в stdout
        output_stream = sys.stderr if use_stderr else sys.stdout
        print(main_msg, file=output_stream, flush=True)
    
    def info(self, message: str, details: Optional[str] = None):
        """Информационное сообщение"""
        self._log("INFO", "ℹ️", Colors.BLUE, message, details)
    
    def success(self, message: str, details: Optional[str] = None):
        """Сообщение об успехе"""
        self._log("SUCCESS", "✅", Colors.GREEN, message, details)
    
    def warning(self, message: str, details: Optional[str] = None):
        """Предупреждение"""
        self._log("WARNING", "⚠️", Colors.YELLOW, message, details, use_stderr=True)
    
    def error(self, message: str, details: Optional[str] = None, exc_info: bool = False):
        """Ошибка - выводится в stderr для гарантированной видимости"""
        self._log("ERROR", "❌", Colors.RED, message, details, use_stderr=True)
        if exc_info:
            # Выводим traceback в stderr
            traceback.print_exc(file=sys.stderr)
    
    def debug(self, message: str, details: Optional[str] = None):
        """Отладочное сообщение (только если включен DEBUG режим)"""
        if os.getenv("DEBUG", "false").lower() == "true":
            self._log("DEBUG", "🐛", Colors.MAGENTA, message, details)
    
    def telegram(self, action: str, chat_id: Optional[str] = None):
        """Логирование действий Telegram бота"""
        if chat_id:
            self.info(f"Telegram: {action}", f"chat_id={chat_id}")
        else:
            self.info(f"Telegram: {action}")
    
    def api(self, action: str, latency: Optional[float] = None, response_id: Optional[str] = None):
        """Логирование API запросов"""
        details_parts = []
        if latency:
            details_parts.append(f"latency={latency:.2f}s")
        if response_id:
            details_parts.append(f"id={response_id[:8]}...")
        
        details = ", ".join(details_parts) if details_parts else None
        self.info(f"API: {action}", details)
    
    def agent(self, action: str, chat_id: Optional[str] = None, context: Optional[str] = None):
        """Логирование работы агента"""
        details_parts = []
        if chat_id:
            details_parts.append(f"chat_id={chat_id}")
        if context:
            details_parts.append(f"context={context}")
        
        details = ", ".join(details_parts) if details_parts else None
        self.info(f"Agent: {action}", details)


# Глобальный экземпляр логгера
logger = Logger("BeautyBot")
