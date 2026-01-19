"""
Доменные модели (entities и value objects).

Правила:
- Используем dataclasses для immutability
- Модели не знают о БД (чистая бизнес-логика)
- Type hints везде
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import BanLevel, SpamType


@dataclass(frozen=True, slots=True)
class User:
    """Пользователь Telegram."""

    user_id: int
    name: str
    username: Optional[str] = None

    def __str__(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.name

    @property
    def mention(self) -> str:
        """Упоминание для Telegram."""
        if self.username:
            return f"@{self.username}"
        return f"[{self.name}](tg://user?id={self.user_id})"


@dataclass(frozen=True, slots=True)
class SpamRecord:
    """Запись о спаме."""

    user_id: int
    chat_id: int
    spam_type: SpamType
    timestamp: datetime
    content_hash: Optional[str] = None

    def is_recent(self, window_seconds: int) -> bool:
        """Проверяет, попадает ли запись в временное окно."""
        delta = datetime.now() - self.timestamp
        return delta.total_seconds() <= window_seconds


@dataclass(frozen=True, slots=True)
class BanInfo:
    """Информация о бане."""

    user_id: int
    chat_id: int
    violation_count: int
    banned_until: Optional[datetime]
    last_violation: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Активен ли бан сейчас."""
        if not self.banned_until:
            return False
        return self.banned_until > datetime.now()

    @property
    def remaining_minutes(self) -> int:
        """Оставшееся время бана в минутах."""
        if not self.is_active:
            return 0
        delta = self.banned_until - datetime.now()
        return max(0, int(delta.total_seconds() / 60))

    @property
    def ban_level(self) -> BanLevel:
        """Уровень бана."""
        return BanLevel.from_violation_count(self.violation_count)


@dataclass(frozen=True, slots=True)
class Violation:
    """Нарушение пользователя."""

    user_id: int
    chat_id: int
    count: int
    last_violation: datetime
    banned_until: Optional[datetime] = None

    def to_ban_info(self) -> BanInfo:
        """Конвертирует в BanInfo."""
        return BanInfo(
            user_id=self.user_id,
            chat_id=self.chat_id,
            violation_count=self.count,
            banned_until=self.banned_until,
            last_violation=self.last_violation,
        )


@dataclass(frozen=True, slots=True)
class ChatSettings:
    """Настройки чата."""

    chat_id: int
    sticker_limit: int = 3
    sticker_window: int = 30
    text_limit: int = 3
    text_window: int = 20
    image_limit: int = 3
    image_window: int = 30
    video_limit: int = 3
    video_window: int = 30
    warning_enabled: bool = True
    updated_at: Optional[datetime] = None

    def get_limits(self, spam_type: SpamType) -> tuple[int, int]:
        """Возвращает (limit, window) для типа спама."""
        limits_map = {
            SpamType.STICKER: (self.sticker_limit, self.sticker_window),
            SpamType.ANIMATION: (self.sticker_limit, self.sticker_window),
            SpamType.TEXT: (self.text_limit, self.text_window),
            SpamType.PHOTO: (self.image_limit, self.image_window),
            SpamType.VIDEO: (self.video_limit, self.video_window),
        }
        return limits_map[spam_type]


@dataclass(frozen=True, slots=True)
class SteamLink:
    """Привязка Steam аккаунта."""

    user_id: int
    account_id: int
    persona_name: Optional[str] = None
    linked_at: Optional[datetime] = None

    @property
    def steam_id_32(self) -> int:
        """32-битный Steam ID (Account ID)."""
        return self.account_id

    @property
    def steam_id_64(self) -> int:
        """64-битный Steam ID."""
        return self.account_id + 76561197960265728


@dataclass(frozen=True, slots=True)
class ShameSubscription:
    """Подписка на shame уведомления."""

    user_id: int
    chat_id: int
    last_match_id: Optional[int] = None
    subscribed_at: Optional[datetime] = None


@dataclass(frozen=False, slots=True)
class BanStatistics:
    """Статистика банов."""

    chat_id: int
    period_days: int
    total_bans: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    top_violators: list[tuple[int, int]] = field(default_factory=list)
    total_ban_minutes: int = 0

    @property
    def average_ban_duration(self) -> float:
        """Средняя длительность бана."""
        if self.total_bans == 0:
            return 0.0
        return self.total_ban_minutes / self.total_bans

    @property
    def most_common_type(self) -> Optional[str]:
        """Самый частый тип нарушения."""
        if not self.by_type:
            return None
        return max(self.by_type.items(), key=lambda x: x[1])[0]
