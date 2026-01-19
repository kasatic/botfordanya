"""
Доменный слой - ядро бизнес-логики.

Содержит:
- Доменные модели (entities)
- Перечисления (enums)
- Доменные исключения (exceptions)
- Value Objects

Правила:
- НЕ зависит от других слоев
- Чистая бизнес-логика без инфраструктуры
- Immutable модели где возможно
"""

from .enums import (
    BanLevel,
    ChatType,
    SpamType,
)
from .exceptions import (
    AlreadyBanned,
    BanNotFound,
    DomainException,
    InvalidAccountId,
    InvalidChatId,
    NotBanned,
    UserNotFound,
)
from .models import (
    BanInfo,
    BanStatistics,
    ChatSettings,
    ShameSubscription,
    SpamRecord,
    SteamLink,
    User,
    Violation,
)

__all__ = [
    # Models
    "User",
    "Violation",
    "BanInfo",
    "SpamRecord",
    "ChatSettings",
    "SteamLink",
    "ShameSubscription",
    "BanStatistics",
    # Enums
    "SpamType",
    "BanLevel",
    "ChatType",
    # Exceptions
    "DomainException",
    "UserNotFound",
    "InvalidAccountId",
    "InvalidChatId",
    "BanNotFound",
    "AlreadyBanned",
    "NotBanned",
]
