"""
Ядро приложения - конфигурация и общие типы.

Содержит:
- Конфигурацию приложения
- Константы
- Type aliases
- Общие утилиты
"""

from .config import BanConfig, Config, Files, SpamLimits, config, get_config
from .constants import (
    DATABASE_CLEANUP_HOURS,
    DEFAULT_BAN_DURATION,
    DEFAULT_BAN_DURATIONS,
    DOTA_TRIGGERS,
)
from .types import AccountId, ChatId, MessageId, Timestamp, UserId

__all__ = [
    # Config
    "Config",
    "SpamLimits",
    "BanConfig",
    "Files",
    "get_config",
    "config",
    # Constants
    "DEFAULT_BAN_DURATIONS",
    "DEFAULT_BAN_DURATION",
    "DOTA_TRIGGERS",
    "DATABASE_CLEANUP_HOURS",
    # Types
    "UserId",
    "ChatId",
    "AccountId",
    "MessageId",
    "Timestamp",
]
