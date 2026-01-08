"""
Сервис обработки эскалации диалога на менеджера.
"""

from typing import Dict


class EscalationService:
    """Отвечает только за обработку сигнала эскалации [CALL_MANAGER]."""

    def handle(self, llm_response_text: str, client_telegram_id: str) -> Dict[str, str]:
        """
        Обработать сигнал эскалации и сформировать раздельные сообщения.

        :param llm_response_text: Полный текст ответа LLM, начинающийся с [CALL_MANAGER]
        :param client_telegram_id: Идентификатор клиента в Telegram
        :return: Словарь с сообщением для пользователя и алертом для менеджера
        """
        text = llm_response_text or ""
        prefix = "[CALL_MANAGER]"
        manager_report_text = text[text.find(prefix) + len(prefix):].lstrip()
        
        # Переворачиваем порядок строк с сообщениями (старое сверху, новое снизу)
        manager_report_text = self._reverse_message_history(manager_report_text)
        
        # Формируем кликабельную ссылку в формате Markdown
        user_link = f"[{client_telegram_id}](tg://user?id={client_telegram_id})"

        return {
            "user_message": "Пару минут, уточняю ваш вопрос и вернусь в ближайшее время 🤍",
            "manager_alert": f"--- MANAGER ALERT ---\nКлиент: {user_link}\n\n{manager_report_text}",
        }
    
    def _reverse_message_history(self, text: str) -> str:
        """
        Переворачивает порядок строк с сообщениями и форматирует текст.
        
        :param text: Текст с историей сообщений (новое сверху, старое снизу)
        :return: Отформатированный текст с историей сообщений (старое сверху, новое снизу)
        """
        if not text:
            return text
        
        lines = text.split('\n')
        message_lines = []
        report_header = ""
        history_header = ""
        reason_block = []
        
        in_messages = False
        in_reason = False
        
        for line in lines:
            stripped = line.strip()
            
            # Заголовок отчета
            if 'Отчет для менеджера' in stripped:
                report_header = "**Отчет для менеджера:**"
                continue
            
            # Заголовок истории
            if 'История последних' in stripped:
                history_header = f"**{stripped}**"
                in_messages = True
                in_reason = False
                continue
            
            # Блок причины
            if stripped.startswith('Причина:'):
                in_reason = True
                in_messages = False
                # Делаем "Причина:" жирным
                reason_text = stripped.replace('Причина:', '**Причина:**', 1)
                reason_block.append(reason_text)
                continue
            
            # Строки с сообщениями
            if stripped.startswith('- user:') or stripped.startswith('- assistant:'):
                in_messages = True
                in_reason = False
                message_lines.append(line)
            elif in_reason and stripped:
                reason_block.append(line)
            elif in_messages and stripped:
                # Продолжение сообщения
                message_lines.append(line)
        
        # Переворачиваем строки с сообщениями
        if message_lines:
            message_lines = message_lines[::-1]
        
        # Собираем результат с пустыми строками между блоками
        result = []
        
        if report_header:
            result.append(report_header)
            result.append("")  # Пустая строка
        
        if history_header:
            result.append(history_header)
        
        if message_lines:
            result.extend(message_lines)
            result.append("")  # Пустая строка
        
        if reason_block:
            result.extend(reason_block)
        
        return '\n'.join(result)

