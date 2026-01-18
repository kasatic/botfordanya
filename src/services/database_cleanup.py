"""
Сервис для периодической очистки старых записей из базы данных.
"""

import asyncio
import logging
from typing import Optional

from src.database.repositories import SpamRepository

logger = logging.getLogger(__name__)


class DatabaseCleanupService:
    """Сервис для фоновой очистки базы данных."""

    def __init__(self, spam_repo: SpamRepository, interval_hours: int = 1, retention_hours: int = 24):
        """
        Args:
            spam_repo: Репозиторий для работы со спам-записями
            interval_hours: Интервал между очистками в часах (по умолчанию 1)
            retention_hours: Сколько часов хранить записи (по умолчанию 24)
        """
        self.spam_repo = spam_repo
        self.interval_hours = interval_hours
        self.retention_hours = retention_hours
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Запускает фоновую задачу очистки."""
        if self._running:
            logger.warning("⚠️ Cleanup service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"🧹 Database cleanup service started (interval: {self.interval_hours}h, retention: {self.retention_hours}h)"
        )

    async def stop(self) -> None:
        """Останавливает фоновую задачу очистки."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Database cleanup service stopped")

    async def _cleanup_loop(self) -> None:
        """Основной цикл очистки."""
        while self._running:
            try:
                # Выполняем очистку
                deleted_count = await self.spam_repo.cleanup_old_records(hours=self.retention_hours)

                if deleted_count > 0:
                    logger.info(f"✅ Cleanup completed: {deleted_count} records removed")

                # Ждём до следующей очистки
                await asyncio.sleep(self.interval_hours * 3600)

            except asyncio.CancelledError:
                logger.info("🛑 Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in cleanup loop: {e}", exc_info=True)
                # При ошибке ждём меньше времени перед повтором
                await asyncio.sleep(300)  # 5 минут

    async def cleanup_now(self) -> int:
        """Выполняет очистку немедленно (для ручного вызова).

        Returns:
            Количество удаленных записей
        """
        try:
            deleted_count = await self.spam_repo.cleanup_old_records(hours=self.retention_hours)
            logger.info(f"🧹 Manual cleanup: {deleted_count} records removed")
            return deleted_count
        except Exception as e:
            logger.error(f"❌ Error during manual cleanup: {e}", exc_info=True)
            return 0
