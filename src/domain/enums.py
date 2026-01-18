"""
Доменные перечисления.
"""

from enum import Enum


class SpamType(Enum):
    """Типы спама."""

    STICKER = "sticker"
    ANIMATION = "animation"
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"

    def __str__(self) -> str:
        return self.value

    @property
    def display_name(self) -> str:
        """Человекочитаемое название."""
        names = {
            self.STICKER: "стикеров",
            self.ANIMATION: "гифок",
            self.TEXT: "одинаковых сообщений",
            self.PHOTO: "одинаковых картинок",
            self.VIDEO: "одинаковых видео",
        }
        return names[self]


class BanLevel(Enum):
    """Уровни банов (прогрессия)."""

    FIRST = 1  # 10 минут
    SECOND = 2  # 60 минут
    THIRD = 3  # 300 минут (5 часов)
    FOURTH = 4  # 1440 минут (24 часа)
    PERMANENT = 5  # 2880 минут (48 часов) и выше

    @property
    def duration_minutes(self) -> int:
        """Длительность бана в минутах."""
        durations = {
            self.FIRST: 10,
            self.SECOND: 60,
            self.THIRD: 300,
            self.FOURTH: 1440,
            self.PERMANENT: 2880,
        }
        return durations[self]

    @classmethod
    def from_violation_count(cls, count: int) -> "BanLevel":
        """Определяет уровень бана по количеству нарушений."""
        if count <= 0:
            return cls.FIRST
        elif count == 1:
            return cls.FIRST
        elif count == 2:
            return cls.SECOND
        elif count == 3:
            return cls.THIRD
        elif count == 4:
            return cls.FOURTH
        else:
            return cls.PERMANENT


class ChatType(Enum):
    """Типы чатов."""

    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"

    def __str__(self) -> str:
        return self.value

    @property
    def is_group_chat(self) -> bool:
        """Является ли групповым чатом."""
        return self in (self.GROUP, self.SUPERGROUP)
