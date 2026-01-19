"""
Сервис управления банами.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from telegram import ChatPermissions
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.config import config
from src.database import BanStatsRepository, SpamRepository, ViolationRepository

logger = logging.getLogger(__name__)


class BanService:
    """Сервис банов."""

    # Разрешения при бане (только текст)
    RESTRICTED_PERMISSIONS = ChatPermissions(
        can_send_messages=True,
        can_send_photos=False,
        can_send_videos=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_other_messages=False,
        can_send_voice_notes=False,
        can_send_video_notes=False,
        can_send_polls=False,
    )

    # Полные разрешения
    FULL_PERMISSIONS = ChatPermissions(
        can_send_messages=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_other_messages=True,
        can_send_voice_notes=True,
        can_send_video_notes=True,
        can_send_polls=True,
    )

    def __init__(self, violation_repo: ViolationRepository, spam_repo: SpamRepository, stats_repo: BanStatsRepository):
        self.violation_repo = violation_repo
        self.spam_repo = spam_repo
        self.stats_repo = stats_repo

    async def get_violation_info(self, user_id: int, chat_id: int) -> Tuple[int, Optional[str]]:
        """Возвращает информацию о нарушениях."""
        return await self.violation_repo.get_info(user_id, chat_id)

    async def is_banned(self, user_id: int, chat_id: int) -> bool:
        """Проверяет, забанен ли пользователь."""
        return await self.violation_repo.is_banned(user_id, chat_id)

    async def apply_ban(
        self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, ban_type: str = "spam", reason: str = None
    ) -> Tuple[bool, int, int]:
        """
        Применяет бан к пользователю.

        Returns:
            (success, violation_count, ban_minutes)
        """
        # Получаем текущее количество нарушений для расчета длительности
        current_count, _ = await self.violation_repo.get_info(user_id, chat_id)
        next_level = current_count + 1

        # Определяем длительность бана
        ban_minutes = config.ban.get_duration(next_level)

        # Атомарно записываем нарушение и получаем новый счетчик
        violation_count = await self.violation_repo.increment_and_get(user_id, chat_id, ban_minutes)

        # Записываем в статистику
        await self.stats_repo.record_ban(user_id, chat_id, ban_type, ban_minutes, reason)

        # Применяем ограничения
        until_date = int((datetime.now() + timedelta(minutes=ban_minutes)).timestamp())

        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id, user_id=user_id, permissions=self.RESTRICTED_PERMISSIONS, until_date=until_date
            )
            logger.info(f"🔒 Banned user {user_id} in {chat_id} for {ban_minutes} min (#{violation_count})")
            return True, violation_count, ban_minutes
        except BadRequest as e:
            logger.warning(f"Cannot ban user {user_id}: {e}")
            return False, violation_count, ban_minutes

    async def remove_ban(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
        """Снимает бан с пользователя."""
        await self.violation_repo.remove_ban(user_id, chat_id)

        try:
            await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=self.FULL_PERMISSIONS)
            logger.info(f"🔓 Unbanned user {user_id} in {chat_id}")
            return True
        except BadRequest as e:
            logger.warning(f"Cannot unban user {user_id}: {e}")
            return False

    async def pardon_user(self, user_id: int, chat_id: int) -> bool:
        """Полностью прощает пользователя."""
        await self.violation_repo.clear_user(user_id, chat_id)
        await self.spam_repo.clear_user(user_id, chat_id)
        return True

    async def get_remaining_time(self, user_id: int, chat_id: int) -> Optional[int]:
        """Возвращает оставшееся время бана в минутах."""
        _, banned_until = await self.violation_repo.get_info(user_id, chat_id)
        if banned_until:
            ban_end = datetime.fromisoformat(banned_until)
            remaining = ban_end - datetime.now()
            if remaining.total_seconds() > 0:
                return int(remaining.total_seconds() / 60)
        return None
