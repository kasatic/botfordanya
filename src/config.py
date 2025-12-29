"""
Конфигурация бота.
Все настройки в одном месте для удобного управления.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class SpamLimits:
    """Лимиты для разных типов контента."""
    sticker_limit: int = 3
    sticker_window: int = 30
    
    text_limit: int = 3
    text_window: int = 20
    
    image_limit: int = 3
    image_window: int = 30
    
    video_limit: int = 3
    video_window: int = 30


@dataclass(frozen=True, slots=True)
class BanConfig:
    """Конфигурация банов."""
    durations: tuple = (10, 60, 300, 1440)
    default_duration: int = 2880
    
    def get_duration(self, violation_number: int) -> int:
        """Возвращает длительность бана в минутах."""
        if violation_number <= 0:
            return self.durations[0]
        if violation_number <= len(self.durations):
            return self.durations[violation_number - 1]
        return self.default_duration


@dataclass(frozen=True, slots=True)
class Files:
    """Пути к файлам."""
    database: str = "data/bot.db"
    dota_users: str = "data/godota.txt"
    admins: str = "data/admins.txt"


class Config:
    """Главный конфиг бота."""
    __slots__ = ('token', 'spam', 'ban', 'files', 'dota_triggers')
    
    def __init__(self):
        self.token = os.getenv("BOT_TOKEN")
        if not self.token:
            raise ValueError("BOT_TOKEN не найден в .env файле")
        
        self.spam = SpamLimits()
        self.ban = BanConfig()
        self.files = Files()
        self.dota_triggers = ("го дота", "годота", "go dota", "godota")


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Singleton конфиг с кэшированием."""
    return Config()


# Для обратной совместимости
config = get_config()
