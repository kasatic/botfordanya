"""
Сервис управления админами.
"""

import logging
from pathlib import Path
from typing import List, Set

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, NetworkError

logger = logging.getLogger(__name__)


class AdminService:
    """Сервис для работы с админами."""

    def __init__(self, admin_file: str):
        self.admin_file = admin_file
        self._admins: Set[str] = set()
        self.reload()

    def _sanitize_username(self, username: str) -> str:
        """
        Безопасно маскирует username для логов.

        Args:
            username: Оригинальный username

        Returns:
            Замаскированный username (первые 3 символа + ***)
        """
        if not username:
            return "empty"
        if len(username) <= 3:
            return "***"
        return f"{username[:3]}***"

    def reload(self) -> int:
        """Перезагружает список админов из файла."""
        self._admins.clear()

        path = Path(self.admin_file)
        if not path.exists():
            logger.warning(f"Admin file not found at configured path")
            return 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    # Убираем комментарии и пробелы
                    clean = line.split("#")[0].strip()
                    if clean:
                        # Убираем @ и приводим к нижнему регистру
                        username = clean.lstrip("@").lower()
                        self._admins.add(username)

            # Логируем только количество админов, не имена
            logger.info(f"Successfully loaded {len(self._admins)} admin(s) from configuration file")
            return len(self._admins)
        except IOError as e:
            logger.error(f"IO error reading admin file: {type(e).__name__}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error loading admins: {type(e).__name__}")
            return 0

    def is_admin(self, username: str) -> bool:
        """Проверяет, является ли username админом."""
        if not username:
            logger.debug("Admin check: False (empty username)")
            return False

        result = username.lower() in self._admins
        # Логируем только результат проверки, не username
        logger.debug(f"Admin check result: {result}")
        return result

    async def is_chat_owner(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
        """Проверяет, является ли пользователь владельцем чата."""
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            result = member.status == "creator"
            logger.debug(f"Chat owner check for user_id={user_id}: {result}")
            return result
        except (NetworkError, TimeoutError) as e:
            logger.warning(f"Network error checking chat owner: {type(e).__name__}")
            raise  # Пробрасываем для retry на верхнем уровне
        except TelegramError as e:
            logger.error(f"Telegram API error checking chat owner: {type(e).__name__}")
            return False  # Только при реальной ошибке API

    async def is_chat_admin(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
        """Проверяет, является ли пользователь админом чата."""
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            result = member.status in ("creator", "administrator")
            logger.debug(f"Chat admin check for user_id={user_id}: {result}")
            return result
        except (NetworkError, TimeoutError) as e:
            logger.warning(f"Network error checking admin: {type(e).__name__}")
            raise  # Пробрасываем для retry на верхнем уровне
        except TelegramError as e:
            logger.error(f"Telegram API error checking admin: {type(e).__name__}")
            return False  # Только при реальной ошибке API

    async def can_unban(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, username: str) -> bool:
        """Проверяет, может ли пользователь разбанивать."""
        # Владелец чата всегда может
        if await self.is_chat_owner(context, chat_id, user_id):
            logger.debug(f"Unban permission granted: chat owner (user_id={user_id})")
            return True
        # Админ чата может
        if await self.is_chat_admin(context, chat_id, user_id):
            logger.debug(f"Unban permission granted: chat admin (user_id={user_id})")
            return True
        # Или если в списке глобальных админов
        is_global_admin = self.is_admin(username)
        if is_global_admin:
            logger.debug(f"Unban permission granted: global admin (user_id={user_id})")
        else:
            logger.debug(f"Unban permission denied (user_id={user_id})")
        return is_global_admin

    @property
    def admin_list(self) -> List[str]:
        """Возвращает список админов."""
        return list(self._admins)
