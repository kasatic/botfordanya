"""
Асинхронное подключение к SQLite через aiosqlite.
"""

import logging
import asyncio
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class Database:
    """Асинхронный менеджер подключения к БД."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Создаёт директорию для БД если нужно."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        """Инициализация долгоживущего соединения."""
        async with self._lock:
            if self._conn is None:
                self._conn = await aiosqlite.connect(self.db_path)
                self._conn.row_factory = aiosqlite.Row
                logger.info("✅ Database connection established")

                # Автоматически применяем миграции после подключения
                await self.migrate()

    async def close(self) -> None:
        """Закрытие соединения."""
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None
                logger.info("✅ Database connection closed")

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Async context manager для подключения."""
        async with self._lock:
            if self._conn is None:
                raise RuntimeError("Database not initialized. Call init() first.")

            try:
                yield self._conn
                await self._conn.commit()
            except Exception as e:
                await self._conn.rollback()
                logger.error(f"Database error: {e}")
                raise

    async def migrate(self) -> None:
        """Применяет все необходимые миграции к базе данных."""
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call init() first.")

        # Импортируем здесь, чтобы избежать циклических импортов
        from .migrations_manager import MigrationManager
        from .migrations import get_migrations

        logger.info("🔄 Starting database migration...")
        migration_manager = MigrationManager(self._conn)
        migrations = get_migrations()
        await migration_manager.migrate_to_latest(migrations)
        logger.info("✅ Database migration completed")

    async def init_schema(self) -> None:
        """
        DEPRECATED: Используйте migrate() вместо этого метода.

        Этот метод оставлен для обратной совместимости и теперь просто вызывает migrate().
        Миграции применяются автоматически при вызове init().
        """
        logger.warning("⚠️ init_schema() is deprecated. Migrations are now applied automatically during init().")
        await self.migrate()
