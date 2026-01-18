"""
Фикстуры для тестов базы данных.
"""
import pytest
from src.database import Database


@pytest.fixture
async def db(tmp_path):
    """Создаёт временную БД для каждого теста."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.init()  # Миграции применяются автоматически
    yield database
    await database.close()
