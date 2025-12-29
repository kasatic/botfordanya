"""
Integration tests for database repositories.
Тесты для SpamRepository, ViolationRepository, WhitelistRepository, ChatSettingsRepository.
"""
import pytest
from datetime import datetime, timedelta

from src.database import (
    Database,
    SpamRepository,
    ViolationRepository,
    WhitelistRepository,
    ChatSettingsRepository,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SPAM REPOSITORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpamRepository:
    """Тесты для SpamRepository."""

    @pytest.fixture
    async def repo(self, db: Database) -> SpamRepository:
        """Создаёт SpamRepository с тестовой БД."""
        return SpamRepository(db)

    async def test_add_record_creates_entry(self, repo: SpamRepository):
        """add_record() должен создавать запись в БД."""
        user_id, chat_id = 123, -100123

        await repo.add_record(user_id, chat_id, "sticker")

        count = await repo.count_recent(user_id, chat_id, "sticker", window_seconds=60)
        assert count == 1

    async def test_add_record_with_content_hash(self, repo: SpamRepository):
        """add_record() должен сохранять content_hash."""
        user_id, chat_id = 123, -100123
        content_hash = "abc123hash"

        await repo.add_record(user_id, chat_id, "text", content_hash=content_hash)

        count = await repo.count_recent(
            user_id, chat_id, "text", window_seconds=60, content_hash=content_hash
        )
        assert count == 1

    async def test_add_multiple_records(self, repo: SpamRepository):
        """add_record() должен добавлять несколько записей."""
        user_id, chat_id = 123, -100123

        await repo.add_record(user_id, chat_id, "sticker")
        await repo.add_record(user_id, chat_id, "sticker")
        await repo.add_record(user_id, chat_id, "sticker")

        count = await repo.count_recent(user_id, chat_id, "sticker", window_seconds=60)
        assert count == 3

    async def test_count_recent_filters_by_type(self, repo: SpamRepository):
        """count_recent() должен фильтровать по типу спама."""
        user_id, chat_id = 123, -100123

        await repo.add_record(user_id, chat_id, "sticker")
        await repo.add_record(user_id, chat_id, "sticker")
        await repo.add_record(user_id, chat_id, "text")

        sticker_count = await repo.count_recent(user_id, chat_id, "sticker", window_seconds=60)
        text_count = await repo.count_recent(user_id, chat_id, "text", window_seconds=60)

        assert sticker_count == 2
        assert text_count == 1

    async def test_count_recent_filters_by_user(self, repo: SpamRepository):
        """count_recent() должен фильтровать по пользователю."""
        chat_id = -100123

        await repo.add_record(111, chat_id, "sticker")
        await repo.add_record(111, chat_id, "sticker")
        await repo.add_record(222, chat_id, "sticker")

        count_user1 = await repo.count_recent(111, chat_id, "sticker", window_seconds=60)
        count_user2 = await repo.count_recent(222, chat_id, "sticker", window_seconds=60)

        assert count_user1 == 2
        assert count_user2 == 1

    async def test_count_recent_filters_by_chat(self, repo: SpamRepository):
        """count_recent() должен фильтровать по чату."""
        user_id = 123

        await repo.add_record(user_id, -100111, "sticker")
        await repo.add_record(user_id, -100111, "sticker")
        await repo.add_record(user_id, -100222, "sticker")

        count_chat1 = await repo.count_recent(user_id, -100111, "sticker", window_seconds=60)
        count_chat2 = await repo.count_recent(user_id, -100222, "sticker", window_seconds=60)

        assert count_chat1 == 2
        assert count_chat2 == 1

    async def test_count_recent_filters_by_content_hash(self, repo: SpamRepository):
        """count_recent() с content_hash должен считать только совпадающие."""
        user_id, chat_id = 123, -100123

        await repo.add_record(user_id, chat_id, "text", content_hash="hash1")
        await repo.add_record(user_id, chat_id, "text", content_hash="hash1")
        await repo.add_record(user_id, chat_id, "text", content_hash="hash2")

        count_hash1 = await repo.count_recent(
            user_id, chat_id, "text", window_seconds=60, content_hash="hash1"
        )
        count_hash2 = await repo.count_recent(
            user_id, chat_id, "text", window_seconds=60, content_hash="hash2"
        )

        assert count_hash1 == 2
        assert count_hash2 == 1

    async def test_count_recent_returns_zero_for_empty(self, repo: SpamRepository):
        """count_recent() должен возвращать 0 для пустых результатов."""
        count = await repo.count_recent(999, -100999, "sticker", window_seconds=60)
        assert count == 0

    async def test_clear_user_removes_all_records(self, repo: SpamRepository):
        """clear_user() должен удалять все записи пользователя в чате."""
        user_id, chat_id = 123, -100123

        await repo.add_record(user_id, chat_id, "sticker")
        await repo.add_record(user_id, chat_id, "text")
        await repo.add_record(user_id, chat_id, "image")

        await repo.clear_user(user_id, chat_id)

        sticker_count = await repo.count_recent(user_id, chat_id, "sticker", window_seconds=60)
        text_count = await repo.count_recent(user_id, chat_id, "text", window_seconds=60)
        image_count = await repo.count_recent(user_id, chat_id, "image", window_seconds=60)

        assert sticker_count == 0
        assert text_count == 0
        assert image_count == 0

    async def test_clear_user_does_not_affect_other_users(self, repo: SpamRepository):
        """clear_user() не должен затрагивать записи других пользователей."""
        chat_id = -100123

        await repo.add_record(111, chat_id, "sticker")
        await repo.add_record(222, chat_id, "sticker")

        await repo.clear_user(111, chat_id)

        count_user1 = await repo.count_recent(111, chat_id, "sticker", window_seconds=60)
        count_user2 = await repo.count_recent(222, chat_id, "sticker", window_seconds=60)

        assert count_user1 == 0
        assert count_user2 == 1

    async def test_clear_user_does_not_affect_other_chats(self, repo: SpamRepository):
        """clear_user() не должен затрагивать записи в других чатах."""
        user_id = 123

        await repo.add_record(user_id, -100111, "sticker")
        await repo.add_record(user_id, -100222, "sticker")

        await repo.clear_user(user_id, -100111)

        count_chat1 = await repo.count_recent(user_id, -100111, "sticker", window_seconds=60)
        count_chat2 = await repo.count_recent(user_id, -100222, "sticker", window_seconds=60)

        assert count_chat1 == 0
        assert count_chat2 == 1


# ═══════════════════════════════════════════════════════════════════════════════
# VIOLATION REPOSITORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestViolationRepository:
    """Тесты для ViolationRepository."""

    @pytest.fixture
    async def repo(self, db: Database) -> ViolationRepository:
        """Создаёт ViolationRepository с тестовой БД."""
        return ViolationRepository(db)

    async def test_add_violation_creates_entry(self, repo: ViolationRepository):
        """add_violation() должен создавать запись и возвращать счётчик 1."""
        user_id, chat_id = 123, -100123

        count = await repo.add_violation(user_id, chat_id, ban_minutes=5)

        assert count == 1

    async def test_add_violation_increments_counter(self, repo: ViolationRepository):
        """add_violation() должен инкрементировать счётчик."""
        user_id, chat_id = 123, -100123

        count1 = await repo.add_violation(user_id, chat_id, ban_minutes=5)
        count2 = await repo.add_violation(user_id, chat_id, ban_minutes=10)
        count3 = await repo.add_violation(user_id, chat_id, ban_minutes=15)

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

    async def test_get_info_returns_count_and_banned_until(self, repo: ViolationRepository):
        """get_info() должен возвращать (count, banned_until)."""
        user_id, chat_id = 123, -100123

        await repo.add_violation(user_id, chat_id, ban_minutes=5)
        await repo.add_violation(user_id, chat_id, ban_minutes=10)

        count, banned_until = await repo.get_info(user_id, chat_id)

        assert count == 2
        assert banned_until is not None

    async def test_get_info_returns_zero_for_new_user(self, repo: ViolationRepository):
        """get_info() должен возвращать (0, None) для нового пользователя."""
        count, banned_until = await repo.get_info(999, -100999)

        assert count == 0
        assert banned_until is None

    async def test_is_banned_returns_true_when_banned(self, repo: ViolationRepository):
        """is_banned() должен возвращать True если бан активен."""
        user_id, chat_id = 123, -100123

        await repo.add_violation(user_id, chat_id, ban_minutes=60)

        is_banned = await repo.is_banned(user_id, chat_id)

        assert is_banned is True

    async def test_is_banned_returns_false_for_new_user(self, repo: ViolationRepository):
        """is_banned() должен возвращать False для нового пользователя."""
        is_banned = await repo.is_banned(999, -100999)

        assert is_banned is False

    async def test_is_banned_returns_false_after_ban_expires(self, repo: ViolationRepository):
        """is_banned() должен возвращать False после истечения бана."""
        user_id, chat_id = 123, -100123

        # Добавляем нарушение с баном на 0 минут (сразу истекает)
        await repo.add_violation(user_id, chat_id, ban_minutes=0)

        is_banned = await repo.is_banned(user_id, chat_id)

        # Бан на 0 минут должен сразу истечь
        assert is_banned is False

    async def test_get_top_returns_sorted_violators(self, repo: ViolationRepository):
        """get_top() должен возвращать топ нарушителей отсортированный по убыванию."""
        chat_id = -100123

        # Добавляем нарушения разным пользователям
        await repo.add_violation(111, chat_id, ban_minutes=5)

        await repo.add_violation(222, chat_id, ban_minutes=5)
        await repo.add_violation(222, chat_id, ban_minutes=5)
        await repo.add_violation(222, chat_id, ban_minutes=5)

        await repo.add_violation(333, chat_id, ban_minutes=5)
        await repo.add_violation(333, chat_id, ban_minutes=5)

        top = await repo.get_top(chat_id, limit=10)

        assert len(top) == 3
        assert top[0] == (222, 3)  # Первый - 3 нарушения
        assert top[1] == (333, 2)  # Второй - 2 нарушения
        assert top[2] == (111, 1)  # Третий - 1 нарушение

    async def test_get_top_respects_limit(self, repo: ViolationRepository):
        """get_top() должен ограничивать количество результатов."""
        chat_id = -100123

        for i in range(10):
            await repo.add_violation(100 + i, chat_id, ban_minutes=5)

        top = await repo.get_top(chat_id, limit=3)

        assert len(top) == 3

    async def test_get_top_returns_empty_for_new_chat(self, repo: ViolationRepository):
        """get_top() должен возвращать пустой список для нового чата."""
        top = await repo.get_top(-100999, limit=10)

        assert top == []

    async def test_get_top_filters_by_chat(self, repo: ViolationRepository):
        """get_top() должен фильтровать по чату."""
        await repo.add_violation(111, -100111, ban_minutes=5)
        await repo.add_violation(222, -100222, ban_minutes=5)

        top_chat1 = await repo.get_top(-100111, limit=10)
        top_chat2 = await repo.get_top(-100222, limit=10)

        assert len(top_chat1) == 1
        assert top_chat1[0][0] == 111
        assert len(top_chat2) == 1
        assert top_chat2[0][0] == 222

    async def test_remove_ban_clears_banned_until(self, repo: ViolationRepository):
        """remove_ban() должен снимать бан."""
        user_id, chat_id = 123, -100123

        await repo.add_violation(user_id, chat_id, ban_minutes=60)
        assert await repo.is_banned(user_id, chat_id) is True

        result = await repo.remove_ban(user_id, chat_id)

        assert result is True
        assert await repo.is_banned(user_id, chat_id) is False

    async def test_remove_ban_returns_false_for_nonexistent(self, repo: ViolationRepository):
        """remove_ban() должен возвращать False для несуществующего пользователя."""
        result = await repo.remove_ban(999, -100999)

        assert result is False

    async def test_clear_user_removes_violation_record(self, repo: ViolationRepository):
        """clear_user() должен полностью удалять запись."""
        user_id, chat_id = 123, -100123

        await repo.add_violation(user_id, chat_id, ban_minutes=5)
        await repo.add_violation(user_id, chat_id, ban_minutes=5)

        result = await repo.clear_user(user_id, chat_id)

        assert result is True
        count, banned_until = await repo.get_info(user_id, chat_id)
        assert count == 0
        assert banned_until is None


# ═══════════════════════════════════════════════════════════════════════════════
# WHITELIST REPOSITORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhitelistRepository:
    """Тесты для WhitelistRepository."""

    @pytest.fixture
    async def repo(self, db: Database) -> WhitelistRepository:
        """Создаёт WhitelistRepository с тестовой БД."""
        return WhitelistRepository(db)

    async def test_add_creates_entry(self, repo: WhitelistRepository):
        """add() должен добавлять пользователя в белый список."""
        user_id, chat_id = 123, -100123

        result = await repo.add(user_id, chat_id)

        assert result is True
        assert await repo.is_whitelisted(user_id, chat_id) is True

    async def test_add_with_added_by(self, repo: WhitelistRepository):
        """add() должен сохранять информацию о том, кто добавил."""
        user_id, chat_id, admin_id = 123, -100123, 999

        await repo.add(user_id, chat_id, added_by=admin_id)

        whitelist = await repo.get_all(chat_id)
        assert len(whitelist) == 1
        assert whitelist[0][0] == user_id

    async def test_add_is_idempotent(self, repo: WhitelistRepository):
        """add() должен быть идемпотентным (повторное добавление не создаёт дубликат)."""
        user_id, chat_id = 123, -100123

        await repo.add(user_id, chat_id)
        await repo.add(user_id, chat_id)

        whitelist = await repo.get_all(chat_id)
        assert len(whitelist) == 1

    async def test_remove_deletes_entry(self, repo: WhitelistRepository):
        """remove() должен удалять пользователя из белого списка."""
        user_id, chat_id = 123, -100123

        await repo.add(user_id, chat_id)
        result = await repo.remove(user_id, chat_id)

        assert result is True
        assert await repo.is_whitelisted(user_id, chat_id) is False

    async def test_remove_returns_false_for_nonexistent(self, repo: WhitelistRepository):
        """remove() должен возвращать False для несуществующего пользователя."""
        result = await repo.remove(999, -100999)

        assert result is False

    async def test_is_whitelisted_returns_true_for_whitelisted(self, repo: WhitelistRepository):
        """is_whitelisted() должен возвращать True для пользователя в белом списке."""
        user_id, chat_id = 123, -100123

        await repo.add(user_id, chat_id)

        assert await repo.is_whitelisted(user_id, chat_id) is True

    async def test_is_whitelisted_returns_false_for_not_whitelisted(self, repo: WhitelistRepository):
        """is_whitelisted() должен возвращать False для пользователя не в белом списке."""
        assert await repo.is_whitelisted(999, -100999) is False

    async def test_is_whitelisted_is_chat_specific(self, repo: WhitelistRepository):
        """is_whitelisted() должен быть специфичным для чата."""
        user_id = 123

        await repo.add(user_id, -100111)

        assert await repo.is_whitelisted(user_id, -100111) is True
        assert await repo.is_whitelisted(user_id, -100222) is False

    async def test_get_all_returns_all_whitelisted(self, repo: WhitelistRepository):
        """get_all() должен возвращать всех пользователей в белом списке чата."""
        chat_id = -100123

        await repo.add(111, chat_id)
        await repo.add(222, chat_id)
        await repo.add(333, chat_id)

        whitelist = await repo.get_all(chat_id)

        assert len(whitelist) == 3
        user_ids = [entry[0] for entry in whitelist]
        assert 111 in user_ids
        assert 222 in user_ids
        assert 333 in user_ids

    async def test_get_all_returns_empty_for_new_chat(self, repo: WhitelistRepository):
        """get_all() должен возвращать пустой список для нового чата."""
        whitelist = await repo.get_all(-100999)

        assert whitelist == []

    async def test_get_all_filters_by_chat(self, repo: WhitelistRepository):
        """get_all() должен фильтровать по чату."""
        await repo.add(111, -100111)
        await repo.add(222, -100222)

        whitelist_chat1 = await repo.get_all(-100111)
        whitelist_chat2 = await repo.get_all(-100222)

        assert len(whitelist_chat1) == 1
        assert whitelist_chat1[0][0] == 111
        assert len(whitelist_chat2) == 1
        assert whitelist_chat2[0][0] == 222


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT SETTINGS REPOSITORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatSettingsRepository:
    """Тесты для ChatSettingsRepository."""

    @pytest.fixture
    async def repo(self, db: Database) -> ChatSettingsRepository:
        """Создаёт ChatSettingsRepository с тестовой БД."""
        return ChatSettingsRepository(db)

    async def test_get_returns_defaults_for_new_chat(self, repo: ChatSettingsRepository):
        """get() должен возвращать дефолтные настройки для нового чата."""
        settings = await repo.get(-100999)

        assert settings["sticker_limit"] == 3
        assert settings["sticker_window"] == 30
        assert settings["text_limit"] == 3
        assert settings["text_window"] == 20
        assert settings["image_limit"] == 3
        assert settings["image_window"] == 30
        assert settings["video_limit"] == 3
        assert settings["video_window"] == 30
        assert settings["warning_enabled"] == 1

    async def test_set_creates_entry_for_new_chat(self, repo: ChatSettingsRepository):
        """set() должен создавать запись для нового чата."""
        chat_id = -100123

        result = await repo.set(chat_id, "sticker_limit", 5)

        assert result is True
        settings = await repo.get(chat_id)
        assert settings["sticker_limit"] == 5

    async def test_set_updates_existing_setting(self, repo: ChatSettingsRepository):
        """set() должен обновлять существующую настройку."""
        chat_id = -100123

        await repo.set(chat_id, "sticker_limit", 5)
        await repo.set(chat_id, "sticker_limit", 10)

        settings = await repo.get(chat_id)
        assert settings["sticker_limit"] == 10

    async def test_set_preserves_other_settings(self, repo: ChatSettingsRepository):
        """set() должен сохранять другие настройки при обновлении одной."""
        chat_id = -100123

        await repo.set(chat_id, "sticker_limit", 5)
        await repo.set(chat_id, "text_limit", 10)

        settings = await repo.get(chat_id)
        assert settings["sticker_limit"] == 5
        assert settings["text_limit"] == 10

    async def test_set_returns_false_for_invalid_key(self, repo: ChatSettingsRepository):
        """set() должен возвращать False для невалидного ключа."""
        result = await repo.set(-100123, "invalid_key", 5)

        assert result is False

    async def test_set_all_valid_keys(self, repo: ChatSettingsRepository):
        """set() должен работать для всех валидных ключей."""
        chat_id = -100123
        valid_keys = [
            "sticker_limit", "sticker_window",
            "text_limit", "text_window",
            "image_limit", "image_window",
            "video_limit", "video_window",
            "warning_enabled",
        ]

        for key in valid_keys:
            result = await repo.set(chat_id, key, 99)
            assert result is True, f"set() failed for key: {key}"

        settings = await repo.get(chat_id)
        for key in valid_keys:
            if key == "warning_enabled":
                assert settings[key] is True  # 99 -> True (bool conversion)
            else:
                assert settings[key] == 99, f"Value mismatch for key: {key}"

    async def test_get_is_chat_specific(self, repo: ChatSettingsRepository):
        """get() должен возвращать настройки специфичные для чата."""
        await repo.set(-100111, "sticker_limit", 5)
        await repo.set(-100222, "sticker_limit", 10)

        settings_chat1 = await repo.get(-100111)
        settings_chat2 = await repo.get(-100222)

        assert settings_chat1["sticker_limit"] == 5
        assert settings_chat2["sticker_limit"] == 10

    async def test_get_returns_copy_of_defaults(self, repo: ChatSettingsRepository):
        """get() должен возвращать копию дефолтных настроек, а не ссылку."""
        settings1 = await repo.get(-100111)
        settings2 = await repo.get(-100222)

        settings1["sticker_limit"] = 999

        assert settings2["sticker_limit"] == 3  # Не изменилось

    async def test_warning_enabled_boolean_conversion(self, repo: ChatSettingsRepository):
        """warning_enabled должен корректно конвертироваться в bool."""
        chat_id = -100123

        await repo.set(chat_id, "warning_enabled", 1)
        settings = await repo.get(chat_id)
        assert settings["warning_enabled"] is True

        await repo.set(chat_id, "warning_enabled", 0)
        settings = await repo.get(chat_id)
        assert settings["warning_enabled"] is False
