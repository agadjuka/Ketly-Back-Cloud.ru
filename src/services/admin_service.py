"""Сервис для работы с админ-панелью на базе Telegram Forum Topics."""

import logging
from typing import Optional

from telegram import Bot, Message, User
from telegram.error import TelegramError

from src.storage.topic_storage import BaseTopicStorage

logger = logging.getLogger(__name__)


class AdminPanelService:
    """Сервис для управления админ-панелью через Forum Topics."""

    def __init__(
        self,
        bot: Bot,
        storage: BaseTopicStorage,
        admin_group_id: int,
    ) -> None:
        """
        Инициализирует сервис админ-панели.

        Args:
            bot: Экземпляр Telegram бота
            storage: Хранилище для связей user_id и topic_id
            admin_group_id: ID группы Telegram для админ-панели
        """
        self.bot = bot
        self.storage = storage
        self.admin_group_id = admin_group_id

    async def get_or_create_topic(self, user: User) -> int:
        """
        Получает или создает топик для пользователя.

        Args:
            user: Объект пользователя Telegram

        Returns:
            ID топика (message_thread_id)

        Raises:
            RuntimeError: Если не удалось создать топик и он не существует в хранилище
        """
        user_id = user.id

        # Проверяем, есть ли топик в хранилище
        topic_id = self.storage.get_topic_id(user_id)
        if topic_id is not None:
            logger.debug(
                "Найден существующий топик для user_id=%s: topic_id=%s",
                user_id,
                topic_id,
            )
            return topic_id

        # Создаем новый топик
        topic_name = self._generate_topic_name(user)
        logger.info(
            "Создание нового топика для user_id=%s: %s",
            user_id,
            topic_name,
        )

        try:
            # Проверяем, является ли группа форумом
            try:
                chat = await self.bot.get_chat(self.admin_group_id)
                if not hasattr(chat, 'is_forum') or not chat.is_forum:
                    error_msg = (
                        f"Группа с ID {self.admin_group_id} не является форумом. "
                        "Для работы админ-панели необходимо:\n"
                        "1. Преобразовать группу в супергруппу\n"
                        "2. Включить режим форума в настройках группы\n"
                        "3. Убедиться, что бот является администратором группы"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            except Exception as e:
                logger.warning("Не удалось проверить тип группы: %s", str(e))
            
            # Создаем топик в админской группе
            forum_topic = await self.bot.create_forum_topic(
                chat_id=self.admin_group_id,
                name=topic_name,
            )

            topic_id = forum_topic.message_thread_id

            # Сохраняем связь в хранилище
            self.storage.save_topic(
                user_id=user_id,
                topic_id=topic_id,
                topic_name=topic_name,
            )

            logger.info(
                "Создан новый топик для user_id=%s: topic_id=%s, name=%s",
                user_id,
                topic_id,
                topic_name,
            )

            return topic_id

        except RuntimeError:
            # Пробрасываем RuntimeError дальше (это наша проверка форума)
            raise
        except TelegramError as e:
            error_code = getattr(e, 'message', str(e))
            if "not a forum" in str(e).lower() or "не форум" in str(e).lower():
                error_msg = (
                    f"Группа с ID {self.admin_group_id} не является форумом. "
                    "Для работы админ-панели необходимо:\n"
                    "1. Преобразовать группу в супергруппу\n"
                    "2. Включить режим форума в настройках группы (Settings → Topics)\n"
                    "3. Убедиться, что бот является администратором группы"
                )
            else:
                error_msg = (
                    f"Ошибка при создании топика для user_id={user_id}: {str(e)}. "
                    "Убедитесь, что бот является администратором группы и имеет права на создание топиков."
                )
            logger.error(error_msg, exc_info=True)
            # Не роняем бота, но логируем ошибку
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Неожиданная ошибка при создании топика для user_id={user_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    async def forward_message_to_admin(
        self,
        user: User,
        message: Message,
        source: str = "User",
    ) -> None:
        """
        Пересылает сообщение в админскую группу в соответствующий топик.

        Args:
            user: Объект пользователя Telegram
            message: Сообщение для пересылки
            source: Источник сообщения ("User" для сообщений от пользователя, "AI" для AI-сообщений)
        """
        try:
            # Получаем или создаем топик
            try:
                topic_id = await self.get_or_create_topic(user)
            except RuntimeError as e:
                # Если группа не является форумом, просто логируем и выходим
                logger.warning("Админ-панель недоступна: %s", str(e))
                return

            # Определяем, как отправлять сообщение
            if source == "User":
                # Для сообщений от пользователя используем forward_message
                # (сохраняется авторство)
                await self._forward_user_message(message, topic_id, user)
            else:
                # Для AI-сообщений или других источников используем send_message
                await self._send_ai_message(message, topic_id, user, source)

            logger.debug(
                "Сообщение от user_id=%s отправлено в админ-панель (topic_id=%s, source=%s)",
                user.id,
                topic_id,
                source,
            )

        except Exception as e:
            logger.error(
                "Ошибка при отправке сообщения в админ-панель для user_id=%s: %s",
                user.id,
                str(e),
                exc_info=True,
            )
            # Не роняем бота, только логируем ошибку

    async def send_ai_response_to_topic(
        self,
        user_id: int,
        ai_text: str,
    ) -> None:
        """
        Отправляет ответ AI в топик пользователя.

        Args:
            user_id: ID пользователя Telegram
            ai_text: Текст ответа от AI
        """
        try:
            # Получаем topic_id из хранилища
            topic_id = self.storage.get_topic_id(user_id)
            if topic_id is None:
                logger.warning(
                    "Не найден топик для user_id=%s. Ответ AI не будет отправлен в админ-панель.",
                    user_id,
                )
                return

            # Отправляем ответ AI в топик с пометкой "ИИ Администратор" (жирным шрифтом)
            await self.bot.send_message(
                chat_id=self.admin_group_id,
                text=f"<b>ИИ Администратор</b>\n{ai_text}",
                message_thread_id=topic_id,
                parse_mode="HTML",
            )

            logger.debug(
                "Ответ AI отправлен в админ-панель для user_id=%s (topic_id=%s)",
                user_id,
                topic_id,
            )

        except Exception as e:
            logger.error(
                "Ошибка при отправке ответа AI в админ-панель для user_id=%s: %s",
                user_id,
                str(e),
                exc_info=True,
            )
            # Не роняем бота, только логируем ошибку

    async def _forward_user_message(
        self,
        message: Message,
        topic_id: int,
        user: User,
    ) -> None:
        """
        Пересылает сообщение от пользователя в топик.

        Args:
            message: Сообщение для пересылки
            topic_id: ID топика
            user: Пользователь
        """
        try:
            # Пытаемся переслать сообщение (сохраняется авторство)
            await self.bot.forward_message(
                chat_id=self.admin_group_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=topic_id,
            )
        except TelegramError as e:
            # Если пересылка не удалась (например, приватный чат),
            # отправляем копию сообщения с информацией о пользователе
            logger.warning(
                "Не удалось переслать сообщение от user_id=%s, отправляем копию: %s",
                user.id,
                str(e),
            )
            await self._send_message_copy(message, topic_id, user)

    async def _send_ai_message(
        self,
        message: Message,
        topic_id: int,
        user: User,
        source: str,
    ) -> None:
        """
        Отправляет AI-сообщение в топик.

        Args:
            message: Сообщение для отправки
            topic_id: ID топика
            user: Пользователь
            source: Источник сообщения
        """
        # Формируем текст сообщения
        text = self._extract_message_text(message)

        # Добавляем пометку об источнике, если это не User
        if source != "User":
            prefix = f"[{source}] "
            text = f"{prefix}{text}" if text else f"{prefix}(сообщение без текста)"

        await self.bot.send_message(
            chat_id=self.admin_group_id,
            text=text,
            message_thread_id=topic_id,
        )

    async def _send_message_copy(
        self,
        message: Message,
        topic_id: int,
        user: User,
    ) -> None:
        """
        Отправляет копию сообщения с информацией о пользователе.

        Args:
            message: Сообщение для отправки
            topic_id: ID топика
            user: Пользователь
        """
        text = self._extract_message_text(message)

        # Формируем сообщение с информацией о пользователе
        user_info = self._format_user_info(user)
        message_text = f"{user_info}\n\n{text}" if text else user_info

        await self.bot.send_message(
            chat_id=self.admin_group_id,
            text=message_text,
            message_thread_id=topic_id,
        )

    def _generate_topic_name(self, user: User) -> str:
        """
        Генерирует название топика для пользователя.

        Args:
            user: Объект пользователя Telegram

        Returns:
            Название топика
        """
        # Используем полное имя, если есть, иначе username, иначе ID
        if user.full_name:
            return user.full_name
        elif user.username:
            return f"@{user.username}"
        else:
            return f"User {user.id}"

    def _format_user_info(self, user: User) -> str:
        """
        Форматирует информацию о пользователе для отправки в админ-панель.

        Args:
            user: Объект пользователя Telegram

        Returns:
            Отформатированная строка с информацией о пользователе
        """
        parts = ["👤 Пользователь:"]

        if user.full_name:
            parts.append(f"Имя: {user.full_name}")

        if user.username:
            parts.append(f"Username: @{user.username}")

        parts.append(f"ID: {user.id}")

        return "\n".join(parts)

    def _extract_message_text(self, message: Message) -> str:
        """
        Извлекает текст из сообщения.

        Args:
            message: Сообщение Telegram

        Returns:
            Текст сообщения или пустая строка
        """
        if message.text:
            return message.text
        elif message.caption:
            return message.caption
        else:
            # Для сообщений без текста (фото, видео и т.д.)
            return "(сообщение без текста)"

    async def enable_manual_mode(self, topic_id: int) -> None:
        """
        Включает ручной режим (менеджер отвечает, ИИ отключен).

        Args:
            topic_id: ID топика в админской группе
        """
        try:
            # Находим user_id по topic_id
            user_id = self.storage.get_user_id(topic_id)
            if user_id is None:
                logger.warning(
                    "Не найден user_id для topic_id=%s. Режим не будет изменен.",
                    topic_id,
                )
                return

            # Устанавливаем режим "manual"
            self.storage.set_mode(user_id, "manual")

            # Отправляем сообщение в топик
            await self.bot.send_message(
                chat_id=self.admin_group_id,
                text="👨‍💻 Режим менеджера включен. ИИ отключен.",
                message_thread_id=topic_id,
            )

            logger.info(
                "Включен ручной режим для user_id=%s (topic_id=%s)",
                user_id,
                topic_id,
            )

        except Exception as e:
            logger.error(
                "Ошибка при включении ручного режима для topic_id=%s: %s",
                topic_id,
                str(e),
                exc_info=True,
            )
            raise

    async def enable_auto_mode(self, topic_id: int) -> None:
        """
        Включает автоматический режим (ИИ снова отвечает).

        Args:
            topic_id: ID топика в админской группе
        """
        try:
            # Находим user_id по topic_id
            user_id = self.storage.get_user_id(topic_id)
            if user_id is None:
                logger.warning(
                    "Не найден user_id для topic_id=%s. Режим не будет изменен.",
                    topic_id,
                )
                return

            # Устанавливаем режим "auto"
            self.storage.set_mode(user_id, "auto")

            # Отправляем сообщение в топик
            await self.bot.send_message(
                chat_id=self.admin_group_id,
                text="🤖 Режим бота включен. ИИ снова отвечает.",
                message_thread_id=topic_id,
            )

            logger.info(
                "Включен автоматический режим для user_id=%s (topic_id=%s)",
                user_id,
                topic_id,
            )

        except Exception as e:
            logger.error(
                "Ошибка при включении автоматического режима для topic_id=%s: %s",
                topic_id,
                str(e),
                exc_info=True,
            )
            raise

    def is_user_in_manual_mode(self, user_id: int) -> bool:
        """
        Проверяет, находится ли пользователь в ручном режиме.

        Args:
            user_id: ID пользователя Telegram

        Returns:
            True, если режим "manual", False в противном случае
        """
        mode = self.storage.get_mode(user_id)
        return mode == "manual"

    async def send_call_manager_notification(
        self,
        user: User,
        reason: str,
        recent_messages: list,
    ) -> None:
        """
        Отправляет уведомление о вызове менеджера в админскую группу.

        Args:
            user: Объект пользователя Telegram
            reason: Причина вызова менеджера
            recent_messages: Последние сообщения из переписки (5-6 сообщений)
        """
        try:
            # Получаем или создаем топик для пользователя
            try:
                topic_id = await self.get_or_create_topic(user)
            except RuntimeError as e:
                # Если группа не является форумом, просто логируем и выходим
                logger.warning("Админ-панель недоступна для уведомления CallManager: %s", str(e))
                return

            # Формируем сообщение
            message_lines = [
                "🔔 Вызов менеджера",
                "",
                f"👤 Клиент: {self._generate_topic_name(user)}",
                f"   ID: {user.id}",
                "",
                f"📋 Причина: {reason}",
                "",
                "💬 Последние сообщения из переписки:",
                "",
            ]

            from langchain_core.messages import HumanMessage, AIMessage

            for msg in recent_messages[-6:]:
                if not isinstance(msg, (HumanMessage, AIMessage)):
                    continue

                content = msg.content
                if content is None:
                    continue
                if isinstance(content, list):
                    content = " ".join(str(item) for item in content)
                else:
                    content = str(content)

                if not content.strip():
                    continue

                if len(content) > 200:
                    content = content[:200] + "..."

                sender = "👤 Клиент" if isinstance(msg, HumanMessage) else "🤖 Агент"
                message_lines.append(f"{sender}: {content}")
                message_lines.append("")

            message_text = "\n".join(message_lines)

            # Отправляем сообщение в топик
            await self.bot.send_message(
                chat_id=self.admin_group_id,
                text=message_text,
                message_thread_id=topic_id,
            )

            logger.info(
                "Уведомление CallManager отправлено в админ-панель для user_id=%s (topic_id=%s)",
                user.id,
                topic_id,
            )

        except Exception as e:
            logger.error(
                "Ошибка при отправке уведомления CallManager в админ-панель для user_id=%s: %s",
                user.id,
                str(e),
                exc_info=True,
            )
            raise

