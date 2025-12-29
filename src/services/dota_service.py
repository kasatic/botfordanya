"""
Сервис для функции "го дота".
"""
import logging
from pathlib import Path
from typing import List, Optional

from src.config import config

logger = logging.getLogger(__name__)


class DotaService:
    """Сервис для призыва на доту."""
    
    def __init__(self, users_file: str):
        self.users_file = users_file
        self._users: List[str] = []
        self.reload()
    
    def reload(self) -> int:
        """Перезагружает список пользователей."""
        self._users.clear()
        
        path = Path(self.users_file)
        if not path.exists():
            logger.warning(f"Dota users file not found: {self.users_file}")
            return 0
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    username = line.strip()
                    if username:
                        # Добавляем @ если нет
                        if not username.startswith("@"):
                            username = f"@{username}"
                        self._users.append(username)
            
            logger.info(f"Loaded {len(self._users)} dota users")
            return len(self._users)
        except Exception as e:
            logger.error(f"Error reading dota users file: {e}")
            return 0
    
    def check_trigger(self, text: str) -> bool:
        """Проверяет, содержит ли текст триггер."""
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in config.dota_triggers)
    
    def get_mention_text(self) -> Optional[str]:
        """Возвращает текст с упоминаниями для доты."""
        if not self._users:
            return None
        mentions = " ".join(self._users)
        return f"{mentions} го дота, дяяяяяй"
    
    @property
    def users(self) -> List[str]:
        """Список пользователей."""
        return self._users.copy()
