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

from .models import (
    User,
    Violation,
    BanInfo,
    SpamRecord,
    ChatSettings,
    SteamLink,
    ShameSubscription,
    BanStatistics,
)

from .enums import (
    SpamType,
    BanLevel,
    ChatType,
)

from .exceptions import (
    DomainException,
    UserNotFound,
    InvalidAccountId,
    InvalidChatId,
    BanNotFound,
    AlreadyBanned,
    NotBanned,
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
