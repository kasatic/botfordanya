# Система миграций базы данных

Эта система управляет версионированием схемы SQLite базы данных.

## Структура

```
src/database/migrations/
├── __init__.py                          # Список всех миграций
├── migration_001_initial_schema.py      # Миграция 001
├── migration_002_example.py             # Миграция 002 (пример)
└── README.md                            # Эта документация
```

## Как работает

1. **Автоматическое применение**: Миграции применяются автоматически при вызове `Database.init()`
2. **Версионирование**: Таблица `schema_version` хранит информацию о применённых миграциях
3. **Последовательность**: Миграции применяются в порядке возрастания номера версии
4. **Идемпотентность**: Повторный запуск не применяет уже применённые миграции

## Создание новой миграции

### Шаг 1: Создайте файл миграции

Создайте файл `migration_XXX_description.py` где:
- `XXX` - номер версии (например, 002, 003)
- `description` - краткое описание изменений

```python
"""
Миграция 002: Добавление таблицы для логов.

Описание изменений:
- Создаёт таблицу action_logs
- Добавляет индекс по timestamp
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
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
        ON action_logs(timestamp)
    """)


async def downgrade(conn: aiosqlite.Connection) -> None:
    """Откат миграции."""
    await conn.execute("DROP INDEX IF EXISTS idx_logs_timestamp")
    await conn.execute("DROP TABLE IF EXISTS action_logs")
```

### Шаг 2: Зарегистрируйте миграцию

Добавьте импорт и запись в `__init__.py`:

```python
# Импортируем все миграции
from .migration_001_initial_schema import upgrade as m001_upgrade, downgrade as m001_downgrade
from .migration_002_example import upgrade as m002_upgrade, downgrade as m002_downgrade

# Список всех миграций в порядке применения
MIGRATIONS = [
    (1, m001_upgrade, m001_downgrade, "Initial database schema"),
    (2, m002_upgrade, m002_downgrade, "Add action logs table"),
]
```

### Шаг 3: Запустите приложение

Миграция применится автоматически при следующем запуске.

## Формат миграции

Каждая миграция должна содержать две функции:

### `upgrade(conn)`
Применяет изменения к базе данных:
- Создание таблиц
- Добавление колонок
- Создание индексов
- Изменение данных

### `downgrade(conn)`
Откатывает изменения:
- Удаление таблиц
- Удаление колонок
- Удаление индексов
- Восстановление данных

## Лучшие практики

### ✅ DO (Делайте)

1. **Используйте IF NOT EXISTS** для создания таблиц:
   ```python
   CREATE TABLE IF NOT EXISTS my_table (...)
   ```

2. **Используйте IF EXISTS** для удаления:
   ```python
   DROP TABLE IF EXISTS my_table
   ```

3. **Добавляйте описание** в docstring миграции

4. **Тестируйте миграции** на копии продакшн базы

5. **Делайте миграции атомарными** - одна миграция = одно логическое изменение

### ❌ DON'T (Не делайте)

1. **Не изменяйте применённые миграции** - создайте новую миграцию для исправлений

2. **Не удаляйте данные без бэкапа** в продакшене

3. **Не делайте сложные миграции данных** без тестирования

4. **Не пропускайте downgrade** - всегда реализуйте откат

## Примеры миграций

### Добавление колонки

```python
async def upgrade(conn: aiosqlite.Connection) -> None:
    """Добавляет колонку email в таблицу users."""
    await conn.execute("""
        ALTER TABLE users 
        ADD COLUMN email TEXT
    """)

async def downgrade(conn: aiosqlite.Connection) -> None:
    """
    SQLite не поддерживает DROP COLUMN напрямую.
    Нужно пересоздать таблицу без колонки.
    """
    # Создаём временную таблицу
    await conn.execute("""
        CREATE TABLE users_backup AS 
        SELECT id, name FROM users
    """)
    
    # Удаляем старую таблицу
    await conn.execute("DROP TABLE users")
    
    # Переименовываем временную
    await conn.execute("ALTER TABLE users_backup RENAME TO users")
```

### Изменение данных

```python
async def upgrade(conn: aiosqlite.Connection) -> None:
    """Нормализует значения spam_type."""
    await conn.execute("""
        UPDATE spam_records 
        SET spam_type = 'sticker' 
        WHERE spam_type IN ('STICKER', 'Sticker')
    """)

async def downgrade(conn: aiosqlite.Connection) -> None:
    """Откат не требуется - данные уже изменены."""
    pass
```

### Создание индекса

```python
async def upgrade(conn: aiosqlite.Connection) -> None:
    """Добавляет индекс для ускорения поиска."""
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_email 
        ON users(email)
    """)

async def downgrade(conn: aiosqlite.Connection) -> None:
    """Удаляет индекс."""
    await conn.execute("DROP INDEX IF EXISTS idx_users_email")
```

## Проверка текущей версии

Вы можете проверить текущую версию схемы в базе данных:

```python
from src.database import Database
from src.database.migrations import MigrationManager

async def check_version():
    db = Database("path/to/db.sqlite")
    await db.init()
    
    async with db.connection() as conn:
        manager = MigrationManager(conn)
        version = await manager.get_current_version()
        print(f"Current schema version: {version}")
    
    await db.close()
```

## Откат миграции (вручную)

Если нужно откатить миграцию вручную:

```python
from src.database import Database
from src.database.migrations import MigrationManager
from src.database.migrations.migration_002_example import downgrade

async def rollback():
    db = Database("path/to/db.sqlite")
    await db.init()
    
    async with db.connection() as conn:
        manager = MigrationManager(conn)
        await manager.rollback_migration(2, downgrade, "Example migration")
    
    await db.close()
```

## Преимущества системы

✅ **Версионирование** - всегда знаете текущую версию схемы  
✅ **История изменений** - все изменения задокументированы  
✅ **Автоматизация** - миграции применяются автоматически  
✅ **Откат** - можно вернуться к предыдущей версии  
✅ **Тестируемость** - легко тестировать на разных версиях схемы  
✅ **Командная работа** - избегаем конфликтов схемы между разработчиками  

## Troubleshooting

### Миграция не применяется

1. Проверьте, что миграция зарегистрирована в `__init__.py`
2. Проверьте номер версии - он должен быть больше текущей версии
3. Проверьте логи - там будет информация об ошибках

### Ошибка при применении миграции

1. Проверьте SQL синтаксис
2. Убедитесь, что таблицы/колонки существуют
3. Проверьте права доступа к файлу базы данных

### Нужно изменить применённую миграцию

**Не изменяйте применённую миграцию!** Вместо этого:
1. Создайте новую миграцию с исправлениями
2. Примените её

## Дополнительная информация

- Миграции используют транзакции - если миграция падает, изменения откатываются
- Таблица `schema_version` создаётся автоматически при первом запуске
- Миграции применяются последовательно, одна за другой
- Логи миграций можно найти в логах приложения
