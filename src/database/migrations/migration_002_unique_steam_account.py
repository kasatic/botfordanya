"""
Миграция 002: Добавление UNIQUE constraint на account_id в steam_links.

Проблема:
Два пользователя могли привязать один и тот же Steam аккаунт,
что позволяло одному пользователю подставить другого.

Решение:
1. Находим и удаляем дубликаты account_id (оставляем самую раннюю привязку)
2. Пересоздаём таблицу с UNIQUE constraint на account_id
3. Копируем очищенные данные в новую таблицу

После миграции каждый Steam аккаунт может быть привязан только к одному Telegram пользователю.
"""
import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def upgrade(conn: aiosqlite.Connection) -> None:
    """Применение миграции: добавление UNIQUE constraint на account_id."""
    
    # Проверяем существует ли таблица steam_links
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='steam_links'"
    )
    table_exists = await cursor.fetchone()
    
    if not table_exists:
        logger.info("⚠️ Table steam_links doesn't exist yet, creating with UNIQUE constraint")
        # Создаём таблицу сразу с правильной схемой
        await conn.execute("""
            CREATE TABLE steam_links (
                user_id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL UNIQUE,
                persona_name TEXT,
                linked_at TEXT NOT NULL
            )
        """)
        return
    
    # 1. Находим дубликаты account_id
    cursor = await conn.execute("""
        SELECT account_id, COUNT(*) as cnt
        FROM steam_links
        GROUP BY account_id
        HAVING cnt > 1
    """)
    duplicates = await cursor.fetchall()
    
    if duplicates:
        logger.warning(f"⚠️ Found {len(duplicates)} duplicate account_id entries")
        for account_id, count in duplicates:
            logger.warning(f"  - account_id {account_id}: {count} users")
    
    # 2. Удаляем дубликаты, оставляя только самую раннюю привязку (MIN(rowid))
    await conn.execute("""
        DELETE FROM steam_links 
        WHERE rowid NOT IN (
            SELECT MIN(rowid) 
            FROM steam_links 
            GROUP BY account_id
        )
    """)
    
    deleted_count = conn.total_changes
    if deleted_count > 0:
        logger.info(f"🗑️ Removed {deleted_count} duplicate entries")
    
    # 3. Создаём новую таблицу с UNIQUE constraint
    await conn.execute("""
        CREATE TABLE steam_links_new (
            user_id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL UNIQUE,
            persona_name TEXT,
            linked_at TEXT NOT NULL
        )
    """)
    
    # 4. Копируем данные из старой таблицы в новую
    await conn.execute("""
        INSERT INTO steam_links_new (user_id, account_id, persona_name, linked_at)
        SELECT user_id, account_id, persona_name, linked_at
        FROM steam_links
    """)
    
    # 5. Удаляем старую таблицу
    await conn.execute("DROP TABLE steam_links")
    
    # 6. Переименовываем новую таблицу
    await conn.execute("ALTER TABLE steam_links_new RENAME TO steam_links")
    
    logger.info("✅ Added UNIQUE constraint on account_id in steam_links table")


async def downgrade(conn: aiosqlite.Connection) -> None:
    """Откат миграции: удаление UNIQUE constraint с account_id."""
    
    # Проверяем существует ли таблица
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='steam_links'"
    )
    table_exists = await cursor.fetchone()
    
    if not table_exists:
        logger.warning("⚠️ Table steam_links doesn't exist, nothing to rollback")
        return
    
    # 1. Создаём таблицу без UNIQUE constraint
    await conn.execute("""
        CREATE TABLE steam_links_old (
            user_id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL,
            persona_name TEXT,
            linked_at TEXT NOT NULL
        )
    """)
    
    # 2. Копируем данные
    await conn.execute("""
        INSERT INTO steam_links_old (user_id, account_id, persona_name, linked_at)
        SELECT user_id, account_id, persona_name, linked_at
        FROM steam_links
    """)
    
    # 3. Удаляем новую таблицу
    await conn.execute("DROP TABLE steam_links")
    
    # 4. Переименовываем старую таблицу
    await conn.execute("ALTER TABLE steam_links_old RENAME TO steam_links")
    
    logger.info("✅ Removed UNIQUE constraint from account_id in steam_links table")
