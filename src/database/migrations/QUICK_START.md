# Быстрый старт: Создание миграции

## 📝 Шаг 1: Создайте файл миграции

```bash
# Формат имени: migration_XXX_description.py
# XXX - номер версии (002, 003, 004...)
src/database/migrations/migration_002_add_logs.py
```

## 💻 Шаг 2: Напишите код

```python
"""
Миграция 002: Добавление таблицы логов.
"""
import aiosqlite


async def upgrade(conn: aiosqlite.Connection) -> None:
    """Применение миграции."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)


async def downgrade(conn: aiosqlite.Connection) -> None:
    """Откат миграции."""
    await conn.execute("DROP TABLE IF EXISTS action_logs")
```

## 📋 Шаг 3: Зарегистрируйте в `__init__.py`

```python
# Добавьте импорт
from .migration_002_add_logs import upgrade as m002_upgrade, downgrade as m002_downgrade

# Добавьте в список MIGRATIONS
MIGRATIONS = [
    (1, m001_upgrade, m001_downgrade, "Initial database schema"),
    (2, m002_upgrade, m002_downgrade, "Add action logs table"),  # ← Новая строка
]
```

## 🚀 Шаг 4: Запустите приложение

Миграция применится автоматически при старте!

```bash
python -m src.bot
```

## ✅ Готово!

Ваша миграция применена. Проверьте логи:

```
INFO - 📦 Applying migration 002: Add action logs table
INFO - ✅ Migration 002 applied successfully
```

---

## 🔍 Полезные команды

### Проверить текущую версию схемы

```python
from src.database import Database
from src.database.migrations_manager import MigrationManager

async def check():
    db = Database("data/bot.db")
    await db.init()
    async with db.connection() as conn:
        manager = MigrationManager(conn)
        version = await manager.get_current_version()
        print(f"Version: {version}")
    await db.close()
```

### Посмотреть историю миграций

```sql
SELECT * FROM schema_version ORDER BY version;
```

---

## 📚 Дополнительно

- 📖 Полная документация: `README.md`
- 🎯 Шаблон миграции: `migration_002_example.py.template`
- 💡 Примеры: см. `migration_001_initial_schema.py`
