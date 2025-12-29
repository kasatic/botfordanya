"""
Асинхронное подключение к SQLite через aiosqlite.
"""
import logging
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class Database:
    """Асинхронный менеджер подключения к БД."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """Создаёт директорию для БД если нужно."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Async context manager для подключения."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            await conn.close()
    
    async def init_schema(self) -> None:
        """Инициализация схемы БД."""
        async with self.connection() as conn:
            # Таблица спама
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS spam_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    spam_type TEXT NOT NULL,
                    content_hash TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_spam_user_type 
                ON spam_records(user_id, chat_id, spam_type, timestamp)
            """)
            
            # Таблица нарушений
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS violations (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    count INTEGER DEFAULT 0,
                    last_violation TEXT,
                    banned_until TEXT,
                    PRIMARY KEY (user_id, chat_id)
                )
            """)
            
            # Белый список
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    added_by INTEGER,
                    added_at TEXT,
                    PRIMARY KEY (user_id, chat_id)
                )
            """)
            
            # Настройки чатов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id INTEGER PRIMARY KEY,
                    sticker_limit INTEGER DEFAULT 3,
                    sticker_window INTEGER DEFAULT 30,
                    text_limit INTEGER DEFAULT 3,
                    text_window INTEGER DEFAULT 20,
                    image_limit INTEGER DEFAULT 3,
                    image_window INTEGER DEFAULT 30,
                    video_limit INTEGER DEFAULT 3,
                    video_window INTEGER DEFAULT 30,
                    warning_enabled INTEGER DEFAULT 1,
                    updated_at TEXT
                )
            """)
            
            # Статистика банов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ban_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    ban_type TEXT NOT NULL,
                    ban_minutes INTEGER NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ban_stats_chat_time 
                ON ban_stats(chat_id, timestamp)
            """)
            
            logger.info("✅ Database schema initialized")
