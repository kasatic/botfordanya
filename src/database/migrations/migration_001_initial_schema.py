"""
Миграция 001: Начальная схема базы данных.

Создаёт все основные таблицы для работы бота:
- spam_records: записи о спаме
- violations: нарушения пользователей
- whitelist: белый список
- chat_settings: настройки чатов
- ban_stats: статистика банов
"""
import aiosqlite


async def upgrade(conn: aiosqlite.Connection) -> None:
    """Применение миграции: создание начальной схемы."""
    
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


async def downgrade(conn: aiosqlite.Connection) -> None:
    """Откат миграции: удаление всех таблиц."""
    
    await conn.execute("DROP INDEX IF EXISTS idx_ban_stats_chat_time")
    await conn.execute("DROP TABLE IF EXISTS ban_stats")
    await conn.execute("DROP TABLE IF EXISTS chat_settings")
    await conn.execute("DROP TABLE IF EXISTS whitelist")
    await conn.execute("DROP TABLE IF EXISTS violations")
    await conn.execute("DROP INDEX IF EXISTS idx_spam_user_type")
    await conn.execute("DROP TABLE IF EXISTS spam_records")
