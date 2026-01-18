"""
Ядро приложения - конфигурация и общие типы.

Содержит:
- Конфигурацию приложения
- Константы
- Type aliases
- Общие утилиты
"""

from .config import Config, SpamLimits, BanConfig, Files, get_config, config
from .constants import (
    DEFAULT_BAN_DURATIONS,
    DEFAULT_BAN_DURATION,
    DOTA_TRIGGERS,
    DATABASE_CLEANUP_HOURS,
)
from .types import UserId, ChatId, AccountId, MessageId, Timestamp

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
