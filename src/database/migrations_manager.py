"""
Система управления миграциями для SQLite БД.
"""

import logging
from typing import Awaitable, Callable, List, Tuple

import aiosqlite

logger = logging.getLogger(__name__)


class MigrationManager:
    """Менеджер миграций базы данных."""

    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def init_schema_version_table(self) -> None:
        """Создаёт таблицу для хранения версии схемы."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
        """)
        await self.conn.commit()
        logger.debug("✅ Schema version table initialized")

    async def get_current_version(self) -> int:
        """Получает текущую версию схемы БД."""
        await self.init_schema_version_table()

        cursor = await self.conn.execute("SELECT MAX(version) as version FROM schema_version")
        row = await cursor.fetchone()
        version = row[0] if row and row[0] is not None else 0
        logger.debug(f"Current schema version: {version}")
        return version

    async def apply_migration(
        self, version: int, upgrade_func: Callable[[aiosqlite.Connection], Awaitable[None]], description: str = ""
    ) -> None:
        """Применяет одну миграцию."""
        logger.info(f"📦 Applying migration {version:03d}: {description}")

        try:
            # Применяем миграцию
            await upgrade_func(self.conn)

            # Записываем версию
            await self.conn.execute(
                """
                INSERT INTO schema_version (version, applied_at, description)
                VALUES (?, datetime('now'), ?)
                """,
                (version, description),
            )
            await self.conn.commit()

            logger.info(f"✅ Migration {version:03d} applied successfully")
        except Exception as e:
            await self.conn.rollback()
            logger.error(f"❌ Failed to apply migration {version:03d}: {e}")
            raise

    async def migrate_to_latest(self, migrations: List[Tuple[int, Callable, Callable, str]]) -> None:
        """
        Применяет все необходимые миграции до последней версии.

        Args:
            migrations: Список кортежей (version, upgrade_func, downgrade_func, description)
        """
        current_version = await self.get_current_version()

        # Сортируем миграции по версии
        sorted_migrations = sorted(migrations, key=lambda x: x[0])

        # Применяем только те миграции, которые новее текущей версии
        pending_migrations = [m for m in sorted_migrations if m[0] > current_version]

        if not pending_migrations:
            logger.info("✅ Database schema is up to date")
            return

        logger.info(f"📦 Found {len(pending_migrations)} pending migration(s)")

        for version, upgrade_func, _, description in pending_migrations:
            await self.apply_migration(version, upgrade_func, description)

        logger.info("✅ All migrations applied successfully")

    async def rollback_migration(
        self, version: int, downgrade_func: Callable[[aiosqlite.Connection], Awaitable[None]], description: str = ""
    ) -> None:
        """Откатывает миграцию."""
        logger.info(f"⏪ Rolling back migration {version:03d}: {description}")

        try:
            # Откатываем миграцию
            await downgrade_func(self.conn)

            # Удаляем запись о версии
            await self.conn.execute("DELETE FROM schema_version WHERE version = ?", (version,))
            await self.conn.commit()

            logger.info(f"✅ Migration {version:03d} rolled back successfully")
        except Exception as e:
            await self.conn.rollback()
            logger.error(f"❌ Failed to rollback migration {version:03d}: {e}")
            raise
