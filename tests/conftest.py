"""
Общие фикстуры для тестов.
"""
import pytest
import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import Database
from src.database.repositories import (
    SpamRepository,
    ViolationRepository,
    WhitelistRepository,
    ChatSettingsRepository,
    BanStatsRepository,
)
from src.database.steam_repository import SteamLinkRepository
from src.services.spam_detector import SpamDetector


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT LOOP FIXTURE
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def event_loop():
    """Создаёт event loop для всех async тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def db() -> AsyncGenerator[Database, None]:
    """In-memory SQLite database для тестов."""
    database = Database(":memory:")
    await database.init_schema()
    yield database


@pytest.fixture
async def db_with_steam(db: Database) -> Database:
    """Database с инициализированной таблицей steam_links."""
    steam_repo = SteamLinkRepository(db)
    await steam_repo.init_table()
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# REPOSITORY FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def spam_repo(db: Database) -> SpamRepository:
    """SpamRepository с тестовой БД."""
    return SpamRepository(db)


@pytest.fixture
async def violation_repo(db: Database) -> ViolationRepository:
    """ViolationRepository с тестовой БД."""
    return ViolationRepository(db)


@pytest.fixture
async def whitelist_repo(db: Database) -> WhitelistRepository:
    """WhitelistRepository с тестовой БД."""
    return WhitelistRepository(db)


@pytest.fixture
async def settings_repo(db: Database) -> ChatSettingsRepository:
    """ChatSettingsRepository с тестовой БД."""
    return ChatSettingsRepository(db)


@pytest.fixture
async def ban_stats_repo(db: Database) -> BanStatsRepository:
    """BanStatsRepository с тестовой БД."""
    return BanStatsRepository(db)


@pytest.fixture
async def steam_repo(db_with_steam: Database) -> SteamLinkRepository:
    """SteamLinkRepository с тестовой БД."""
    return SteamLinkRepository(db_with_steam)


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def spam_detector(
    spam_repo: SpamRepository,
    whitelist_repo: WhitelistRepository,
    settings_repo: ChatSettingsRepository,
) -> SpamDetector:
    """SpamDetector с тестовыми репозиториями."""
    return SpamDetector(spam_repo, whitelist_repo, settings_repo)


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def default_settings() -> Dict[str, Any]:
    """Дефолтные настройки чата."""
    return {
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


@pytest.fixture
def test_settings() -> Dict[str, Any]:
    """Тестовые настройки с низкими лимитами для быстрых тестов."""
    return {
        "sticker_limit": 2,
        "sticker_window": 60,
        "text_limit": 2,
        "text_window": 60,
        "image_limit": 2,
        "image_window": 60,
        "video_limit": 2,
        "video_window": 60,
        "warning_enabled": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DATA FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def test_user_id() -> int:
    """Тестовый user_id."""
    return 123456789


@pytest.fixture
def test_chat_id() -> int:
    """Тестовый chat_id."""
    return -1001234567890


@pytest.fixture
def test_account_id() -> int:
    """Тестовый Dota 2 account_id."""
    return 87654321


@pytest.fixture
def test_steam_id64() -> int:
    """Тестовый Steam ID 64."""
    return 76561198047921049  # = account_id 87655321


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_opendota_profile() -> Dict[str, Any]:
    """Мок ответа OpenDota API для профиля."""
    return {
        "profile": {
            "account_id": 87654321,
            "personaname": "TestPlayer",
            "avatarfull": "https://example.com/avatar.jpg",
        },
        "rank_tier": 52,  # Legend 2
        "mmr_estimate": {"estimate": 3500},
    }


@pytest.fixture
def mock_opendota_recent_matches() -> list:
    """Мок ответа OpenDota API для последних матчей."""
    return [
        {
            "match_id": 7654321000,
            "hero_id": 1,  # Anti-Mage
            "kills": 10,
            "deaths": 3,
            "assists": 5,
            "player_slot": 0,  # Radiant
            "radiant_win": True,
            "duration": 2400,  # 40 минут
            "game_mode": 22,  # Ranked All Pick
        },
        {
            "match_id": 7654321001,
            "hero_id": 2,  # Axe
            "kills": 5,
            "deaths": 8,
            "assists": 15,
            "player_slot": 128,  # Dire
            "radiant_win": True,  # Проигрыш
            "duration": 1800,
            "game_mode": 23,  # Turbo
        },
    ]


@pytest.fixture
def mock_opendota_heroes() -> list:
    """Мок ответа OpenDota API для списка героев."""
    return [
        {"id": 1, "localized_name": "Anti-Mage"},
        {"id": 2, "localized_name": "Axe"},
        {"id": 3, "localized_name": "Bane"},
        {"id": 4, "localized_name": "Bloodseeker"},
        {"id": 5, "localized_name": "Crystal Maiden"},
    ]
