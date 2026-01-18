"""
Репозиторий для привязки Steam аккаунтов.
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple

from .connection import Database

logger = logging.getLogger(__name__)


class SteamLinkRepository:
    """Репозиторий для связи Telegram <-> Steam."""

    def __init__(self, db: Database):
        self.db = db

    async def init_table(self) -> None:
        """Создаёт таблицы если нет."""
        async with self.db.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS steam_links (
                    user_id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    persona_name TEXT,
                    linked_at TEXT NOT NULL
                )
            """)

            # Таблица подписок на shame
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shame_subscriptions (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    last_match_id INTEGER,
                    subscribed_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, chat_id)
                )
            """)

            logger.info("✅ Steam links table ready")

    async def link(self, user_id: int, account_id: int, persona_name: str = None) -> bool:
        """Привязывает Steam аккаунт к Telegram."""
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO steam_links (user_id, account_id, persona_name, linked_at)
                VALUES (?, ?, ?, ?)
            """,
                (user_id, account_id, persona_name, datetime.now().isoformat()),
            )
            return True

    async def unlink(self, user_id: int) -> bool:
        """Отвязывает Steam аккаунт."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("DELETE FROM steam_links WHERE user_id = ?", (user_id,))
            return cursor.rowcount > 0

    async def get_account_id(self, user_id: int) -> Optional[int]:
        """Возвращает Account ID по Telegram user_id."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT account_id FROM steam_links WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else None

    async def get_all_linked(self) -> List[Tuple[int, int, str]]:
        """Возвращает всех привязанных: (user_id, account_id, persona_name)."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT user_id, account_id, persona_name FROM steam_links")
            results = await cursor.fetchall()
            return [(r[0], r[1], r[2]) for r in results]

    # ═══════════════════════════════════════════════════════════
    # 🔔 SHAME SUBSCRIPTIONS
    # ═══════════════════════════════════════════════════════════

    async def subscribe_shame(self, user_id: int, chat_id: int) -> bool:
        """Подписывает на shame уведомления."""
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO shame_subscriptions (user_id, chat_id, subscribed_at)
                VALUES (?, ?, ?)
            """,
                (user_id, chat_id, datetime.now().isoformat()),
            )
            return True

    async def unsubscribe_shame(self, user_id: int, chat_id: int) -> bool:
        """Отписывает от shame."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM shame_subscriptions WHERE user_id = ? AND chat_id = ?", (user_id, chat_id)
            )
            return cursor.rowcount > 0

    async def is_shame_subscribed(self, user_id: int, chat_id: int) -> bool:
        """Проверяет подписку."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM shame_subscriptions WHERE user_id = ? AND chat_id = ?", (user_id, chat_id)
            )
            return await cursor.fetchone() is not None

    async def get_shame_subscribers(self, chat_id: int) -> List[Tuple[int, int, Optional[int]]]:
        """Возвращает подписчиков чата: (user_id, account_id, last_match_id)."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT s.user_id, l.account_id, s.last_match_id
                FROM shame_subscriptions s
                JOIN steam_links l ON s.user_id = l.user_id
                WHERE s.chat_id = ?
            """,
                (chat_id,),
            )
            results = await cursor.fetchall()
            return [(r[0], r[1], r[2]) for r in results]

    async def get_all_shame_chats(self) -> List[int]:
        """Возвращает все чаты с подписчиками."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT DISTINCT chat_id FROM shame_subscriptions")
            results = await cursor.fetchall()
            return [r[0] for r in results]

    async def update_last_match(self, user_id: int, chat_id: int, match_id: int) -> None:
        """Обновляет последний обработанный матч."""
        async with self.db.connection() as conn:
            await conn.execute(
                "UPDATE shame_subscriptions SET last_match_id = ? WHERE user_id = ? AND chat_id = ?",
                (match_id, user_id, chat_id),
            )
