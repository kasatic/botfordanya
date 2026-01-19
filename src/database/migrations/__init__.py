"""
Список всех миграций базы данных.

Каждая миграция представлена кортежем:
(version, upgrade_func, downgrade_func, description)
"""
from typing import List, Tuple, Callable, Awaitable
import aiosqlite

# Импортируем все миграции
from .migration_001_initial_schema import upgrade as m001_upgrade, downgrade as m001_downgrade
from .migration_002_unique_steam_account import upgrade as m002_upgrade, downgrade as m002_downgrade


# Список всех миграций в порядке применения
MIGRATIONS: List[Tuple[int, Callable[[aiosqlite.Connection], Awaitable[None]], Callable[[aiosqlite.Connection], Awaitable[None]], str]] = [
    (1, m001_upgrade, m001_downgrade, "Initial database schema"),
    (2, m002_upgrade, m002_downgrade, "Add UNIQUE constraint on steam_links.account_id"),
]


def get_migrations() -> List[Tuple[int, Callable, Callable, str]]:
    """Возвращает список всех миграций."""
    return MIGRATIONS


__all__ = ['get_migrations', 'MIGRATIONS']
