"""
Асинхронные репозитории для работы с данными.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from .connection import Database

logger = logging.getLogger(__name__)


class SpamRepository:
    """Репозиторий для записей спама."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def add_record(self, user_id: int, chat_id: int, spam_type: str, content_hash: str = None) -> None:
        """Добавляет запись о спаме."""
        async with self.db.connection() as conn:
            await conn.execute(
                "INSERT INTO spam_records (user_id, chat_id, spam_type, content_hash, timestamp) VALUES (?, ?, ?, ?, ?)",
                (user_id, chat_id, spam_type, content_hash, datetime.now().isoformat())
            )
    
    async def count_recent(
        self, 
        user_id: int,
        chat_id: int,
        spam_type: str, 
        window_seconds: int,
        content_hash: str = None
    ) -> int:
        """Считает записи за последние N секунд."""
        cutoff = (datetime.now() - timedelta(seconds=window_seconds)).isoformat()
        
        async with self.db.connection() as conn:
            # Удаляем старые записи
            await conn.execute(
                "DELETE FROM spam_records WHERE user_id = ? AND chat_id = ? AND spam_type = ? AND timestamp < ?",
                (user_id, chat_id, spam_type, cutoff)
            )
            
            # Считаем актуальные
            if content_hash:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM spam_records WHERE user_id = ? AND chat_id = ? AND spam_type = ? AND content_hash = ?",
                    (user_id, chat_id, spam_type, content_hash)
                )
            else:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM spam_records WHERE user_id = ? AND chat_id = ? AND spam_type = ?",
                    (user_id, chat_id, spam_type)
                )
            
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    async def clear_user(self, user_id: int, chat_id: int) -> None:
        """Очищает все записи пользователя в чате."""
        async with self.db.connection() as conn:
            await conn.execute(
                "DELETE FROM spam_records WHERE user_id = ? AND chat_id = ?", 
                (user_id, chat_id)
            )


class ViolationRepository:
    """Репозиторий для нарушений."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def get_info(self, user_id: int, chat_id: int) -> Tuple[int, Optional[str]]:
        """Возвращает (count, banned_until) для пользователя."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT count, banned_until FROM violations WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            result = await cursor.fetchone()
            
            if result:
                return result[0], result[1]
            return 0, None
    
    async def add_violation(self, user_id: int, chat_id: int, ban_minutes: int) -> int:
        """Добавляет нарушение, возвращает новый счётчик."""
        now = datetime.now().isoformat()
        until = (datetime.now() + timedelta(minutes=ban_minutes)).isoformat()
        
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT count FROM violations WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            result = await cursor.fetchone()
            
            new_count = (result[0] + 1) if result else 1
            
            await conn.execute("""
                INSERT OR REPLACE INTO violations (user_id, chat_id, count, last_violation, banned_until)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, chat_id, new_count, now, until))
            
            return new_count
    
    async def is_banned(self, user_id: int, chat_id: int) -> bool:
        """Проверяет, забанен ли пользователь сейчас."""
        _, banned_until = await self.get_info(user_id, chat_id)
        if banned_until:
            return banned_until > datetime.now().isoformat()
        return False
    
    async def remove_ban(self, user_id: int, chat_id: int) -> bool:
        """Снимает бан (обнуляет banned_until)."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "UPDATE violations SET banned_until = NULL WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            return cursor.rowcount > 0
    
    async def clear_user(self, user_id: int, chat_id: int) -> bool:
        """Полностью очищает историю пользователя."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM violations WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            return cursor.rowcount > 0
    
    async def get_top(self, chat_id: int, limit: int = 10) -> List[Tuple[int, int]]:
        """Возвращает топ нарушителей чата."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT user_id, count FROM violations WHERE chat_id = ? ORDER BY count DESC LIMIT ?",
                (chat_id, limit)
            )
            results = await cursor.fetchall()
            return [(r[0], r[1]) for r in results]


class WhitelistRepository:
    """Репозиторий для белого списка."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def is_whitelisted(self, user_id: int, chat_id: int) -> bool:
        """Проверяет, в белом списке ли пользователь."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM whitelist WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            result = await cursor.fetchone()
            return result is not None
    
    async def add(self, user_id: int, chat_id: int, added_by: int = None) -> bool:
        """Добавляет в белый список."""
        async with self.db.connection() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO whitelist (user_id, chat_id, added_by, added_at) VALUES (?, ?, ?, ?)",
                (user_id, chat_id, added_by, datetime.now().isoformat())
            )
            return True
    
    async def remove(self, user_id: int, chat_id: int) -> bool:
        """Удаляет из белого списка."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM whitelist WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            return cursor.rowcount > 0
    
    async def get_all(self, chat_id: int) -> List[Tuple[int, str]]:
        """Возвращает белый список чата."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT user_id, added_at FROM whitelist WHERE chat_id = ?",
                (chat_id,)
            )
            results = await cursor.fetchall()
            return [(r[0], r[1]) for r in results]


class ChatSettingsRepository:
    """Репозиторий для настроек чатов."""
    
    DEFAULT_SETTINGS = {
        "sticker_limit": 3,
        "sticker_window": 30,
        "text_limit": 3,
        "text_window": 20,
        "image_limit": 3,
        "image_window": 30,
        "video_limit": 3,
        "video_window": 30,
        "warning_enabled": 1,
    }
    
    def __init__(self, db: Database):
        self.db = db
    
    async def get(self, chat_id: int) -> Dict[str, Any]:
        """Возвращает настройки чата."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM chat_settings WHERE chat_id = ?",
                (chat_id,)
            )
            result = await cursor.fetchone()
            
            if result:
                return {
                    "sticker_limit": result[1],
                    "sticker_window": result[2],
                    "text_limit": result[3],
                    "text_window": result[4],
                    "image_limit": result[5],
                    "image_window": result[6],
                    "video_limit": result[7],
                    "video_window": result[8],
                    "warning_enabled": bool(result[9]),
                }
            return self.DEFAULT_SETTINGS.copy()
    
    async def set(self, chat_id: int, key: str, value: int) -> bool:
        """Устанавливает настройку."""
        if key not in self.DEFAULT_SETTINGS:
            return False
        
        async with self.db.connection() as conn:
            # Проверяем существование записи
            cursor = await conn.execute(
                "SELECT 1 FROM chat_settings WHERE chat_id = ?",
                (chat_id,)
            )
            exists = await cursor.fetchone()
            
            if exists:
                await conn.execute(
                    f"UPDATE chat_settings SET {key} = ?, updated_at = ? WHERE chat_id = ?",
                    (value, datetime.now().isoformat(), chat_id)
                )
            else:
                # Создаём с дефолтами
                settings = self.DEFAULT_SETTINGS.copy()
                settings[key] = value
                await conn.execute("""
                    INSERT INTO chat_settings 
                    (chat_id, sticker_limit, sticker_window, text_limit, text_window, 
                     image_limit, image_window, video_limit, video_window, warning_enabled, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (chat_id, settings["sticker_limit"], settings["sticker_window"],
                      settings["text_limit"], settings["text_window"],
                      settings["image_limit"], settings["image_window"],
                      settings["video_limit"], settings["video_window"],
                      settings["warning_enabled"], datetime.now().isoformat()))
            
            return True


class BanStatsRepository:
    """Репозиторий для статистики банов."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def record_ban(
        self, 
        user_id: int, 
        chat_id: int, 
        ban_type: str, 
        ban_minutes: int, 
        reason: str = None
    ) -> None:
        """Записывает бан в статистику."""
        async with self.db.connection() as conn:
            await conn.execute("""
                INSERT INTO ban_stats (user_id, chat_id, ban_type, ban_minutes, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, chat_id, ban_type, ban_minutes, reason, datetime.now().isoformat()))
    
    async def get_stats(self, chat_id: int, days: int = 7) -> Dict[str, Any]:
        """Возвращает статистику за N дней."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with self.db.connection() as conn:
            # Общее количество банов
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM ban_stats WHERE chat_id = ? AND timestamp > ?",
                (chat_id, cutoff)
            )
            total = (await cursor.fetchone())[0]
            
            # По типам
            cursor = await conn.execute("""
                SELECT ban_type, COUNT(*) as cnt 
                FROM ban_stats 
                WHERE chat_id = ? AND timestamp > ?
                GROUP BY ban_type
                ORDER BY cnt DESC
            """, (chat_id, cutoff))
            by_type = {r[0]: r[1] for r in await cursor.fetchall()}
            
            # Топ нарушителей за период
            cursor = await conn.execute("""
                SELECT user_id, COUNT(*) as cnt 
                FROM ban_stats 
                WHERE chat_id = ? AND timestamp > ?
                GROUP BY user_id
                ORDER BY cnt DESC
                LIMIT 5
            """, (chat_id, cutoff))
            top_violators = [(r[0], r[1]) for r in await cursor.fetchall()]
            
            # Суммарное время банов
            cursor = await conn.execute(
                "SELECT SUM(ban_minutes) FROM ban_stats WHERE chat_id = ? AND timestamp > ?",
                (chat_id, cutoff)
            )
            total_minutes = (await cursor.fetchone())[0] or 0
            
            return {
                "total_bans": total,
                "by_type": by_type,
                "top_violators": top_violators,
                "total_ban_minutes": total_minutes,
                "period_days": days,
            }
