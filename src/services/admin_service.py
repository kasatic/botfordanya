"""
Сервис управления админами.
"""
import logging
from pathlib import Path
from typing import List, Set

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class AdminService:
    """Сервис для работы с админами."""
    
    def __init__(self, admin_file: str):
        self.admin_file = admin_file
        self._admins: Set[str] = set()
        self.reload()
    
    def reload(self) -> int:
        """Перезагружает список админов из файла."""
        self._admins.clear()
        
        path = Path(self.admin_file)
        if not path.exists():
            logger.warning(f"Admin file not found: {self.admin_file}")
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
            
            logger.info(f"Loaded {len(self._admins)} admins from {self.admin_file}")
            return len(self._admins)
        except Exception as e:
            logger.error(f"Error reading admin file: {e}")
            return 0
    
    def is_admin(self, username: str) -> bool:
        """Проверяет, является ли username админом."""
        if not username:
            return False
        return username.lower() in self._admins
    
    async def is_chat_owner(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: int, 
        user_id: int
    ) -> bool:
        """Проверяет, является ли пользователь владельцем чата."""
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            return member.status == "creator"
        except Exception as e:
            logger.error(f"Error checking chat owner: {e}")
            return False
    
    async def is_chat_admin(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: int, 
        user_id: int
    ) -> bool:
        """Проверяет, является ли пользователь админом чата."""
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            return member.status in ("creator", "administrator")
        except Exception as e:
            logger.error(f"Error checking chat admin: {e}")
            return False
    
    async def can_unban(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: int, 
        user_id: int,
        username: str
    ) -> bool:
        """Проверяет, может ли пользователь разбанивать."""
        # Владелец чата всегда может
        if await self.is_chat_owner(context, chat_id, user_id):
            return True
        # Или если в списке админов
        return self.is_admin(username)
    
    @property
    def admin_list(self) -> List[str]:
        """Возвращает список админов."""
        return list(self._admins)
