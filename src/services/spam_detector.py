"""
Сервис детекции спама.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

from src.database import SpamRepository, WhitelistRepository, ChatSettingsRepository

logger = logging.getLogger(__name__)


class SpamType(Enum):
    """Типы спама."""

    STICKER = "sticker"
    ANIMATION = "animation"
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"


@dataclass
class SpamCheckResult:
    """Результат проверки на спам."""

    is_spam: bool
    is_warning: bool  # Предупреждение (1 до лимита)
    count: int
    limit: int
    spam_type: SpamType
    reason: str = ""


class SpamDetector:
    """Детектор спама с поддержкой настроек чата."""

    REASONS = {
        SpamType.STICKER: "стикеров",
        SpamType.ANIMATION: "гифок",
        SpamType.TEXT: "одинаковых сообщений",
        SpamType.PHOTO: "одинаковых картинок",
        SpamType.VIDEO: "одинаковых видео",
    }

    def __init__(
        self, spam_repo: SpamRepository, whitelist_repo: WhitelistRepository, settings_repo: ChatSettingsRepository
    ):
        self.spam_repo = spam_repo
        self.whitelist_repo = whitelist_repo
        self.settings_repo = settings_repo

    def _get_limits(self, settings: Dict[str, Any], spam_type: SpamType) -> tuple[int, int]:
        """Возвращает (limit, window) для типа спама."""
        type_map = {
            SpamType.STICKER: ("sticker_limit", "sticker_window"),
            SpamType.ANIMATION: ("sticker_limit", "sticker_window"),
            SpamType.TEXT: ("text_limit", "text_window"),
            SpamType.PHOTO: ("image_limit", "image_window"),
            SpamType.VIDEO: ("video_limit", "video_window"),
        }
        limit_key, window_key = type_map[spam_type]
        return settings[limit_key], settings[window_key]

    async def check(
        self, user_id: int, chat_id: int, spam_type: SpamType, content_hash: Optional[str] = None
    ) -> SpamCheckResult:
        """
        Проверяет на спам и записывает активность.
        """
        # Получаем настройки чата
        settings = await self.settings_repo.get(chat_id)
        limit, window = self._get_limits(settings, spam_type)

        # Белый список — не проверяем
        if await self.whitelist_repo.is_whitelisted(user_id, chat_id):
            return SpamCheckResult(is_spam=False, is_warning=False, count=0, limit=limit, spam_type=spam_type)

        # Атомарно записываем активность и считаем
        use_hash = spam_type in (SpamType.TEXT, SpamType.PHOTO, SpamType.VIDEO)
        count = await self.spam_repo.add_and_count_recent(
            user_id, chat_id, spam_type.value, window, content_hash if use_hash else None
        )

        is_spam = count >= limit
        is_warning = (count == limit - 1) and settings.get("warning_enabled", True)

        return SpamCheckResult(
            is_spam=is_spam,
            is_warning=is_warning,
            count=count,
            limit=limit,
            spam_type=spam_type,
            reason=self.REASONS[spam_type],
        )
