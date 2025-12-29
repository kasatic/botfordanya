"""
Integration tests for SteamLinkRepository.
Тесты для Steam привязок и shame подписок.
"""
import pytest
from datetime import datetime

from src.database import Database
from src.database.steam_repository import SteamLinkRepository


class TestSteamLinkRepository:
    """Тесты для SteamLinkRepository - привязка Steam аккаунтов."""

    @pytest.fixture
    async def repo(self, db: Database) -> SteamLinkRepository:
        """Создаёт SteamLinkRepository с инициализированными таблицами."""
        repo = SteamLinkRepository(db)
        await repo.init_table()
        return repo

    # ═══════════════════════════════════════════════════════════════════════════
    # LINK / UNLINK TESTS
    # ═══════════════════════════════════════════════════════════════════════════

    async def test_link_creates_entry(self, repo: SteamLinkRepository):
        """link() должен создавать привязку Steam аккаунта."""
        user_id, account_id = 123, 87654321

        result = await repo.link(user_id, account_id)

        assert result is True
        stored_account_id = await repo.get_account_id(user_id)
        assert stored_account_id == account_id

    async def test_link_with_persona_name(self, repo: SteamLinkRepository):
        """link() должен сохранять persona_name."""
        user_id, account_id = 123, 87654321
        persona_name = "TestPlayer"

        await repo.link(user_id, account_id, persona_name=persona_name)

        all_linked = await repo.get_all_linked()
        assert len(all_linked) == 1
        assert all_linked[0] == (user_id, account_id, persona_name)

    async def test_link_updates_existing(self, repo: SteamLinkRepository):
        """link() должен обновлять существующую привязку."""
        user_id = 123

        await repo.link(user_id, 111111)
        await repo.link(user_id, 222222)

        account_id = await repo.get_account_id(user_id)
        assert account_id == 222222

    async def test_unlink_removes_entry(self, repo: SteamLinkRepository):
        """unlink() должен удалять привязку."""
        user_id, account_id = 123, 87654321

        await repo.link(user_id, account_id)
        result = await repo.unlink(user_id)

        assert result is True
        stored_account_id = await repo.get_account_id(user_id)
        assert stored_account_id is None

    async def test_unlink_returns_false_for_nonexistent(self, repo: SteamLinkRepository):
        """unlink() должен возвращать False для несуществующей привязки."""
        result = await repo.unlink(999)

        assert result is False

    async def test_get_account_id_returns_account_id(self, repo: SteamLinkRepository):
        """get_account_id() должен возвращать account_id."""
        user_id, account_id = 123, 87654321

        await repo.link(user_id, account_id)

        result = await repo.get_account_id(user_id)
        assert result == account_id

    async def test_get_account_id_returns_none_for_nonexistent(self, repo: SteamLinkRepository):
        """get_account_id() должен возвращать None для несуществующей привязки."""
        result = await repo.get_account_id(999)

        assert result is None

    async def test_get_all_linked_returns_all_entries(self, repo: SteamLinkRepository):
        """get_all_linked() должен возвращать все привязки."""
        await repo.link(111, 11111111, "Player1")
        await repo.link(222, 22222222, "Player2")
        await repo.link(333, 33333333, "Player3")

        all_linked = await repo.get_all_linked()

        assert len(all_linked) == 3
        user_ids = [entry[0] for entry in all_linked]
        assert 111 in user_ids
        assert 222 in user_ids
        assert 333 in user_ids

    async def test_get_all_linked_returns_empty_when_no_links(self, repo: SteamLinkRepository):
        """get_all_linked() должен возвращать пустой список когда нет привязок."""
        all_linked = await repo.get_all_linked()

        assert all_linked == []


# ═══════════════════════════════════════════════════════════════════════════════
# SHAME SUBSCRIPTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestShameSubscriptions:
    """Тесты для shame подписок."""

    @pytest.fixture
    async def repo(self, db: Database) -> SteamLinkRepository:
        """Создаёт SteamLinkRepository с инициализированными таблицами."""
        repo = SteamLinkRepository(db)
        await repo.init_table()
        return repo

    async def test_subscribe_shame_creates_subscription(self, repo: SteamLinkRepository):
        """subscribe_shame() должен создавать подписку."""
        user_id, chat_id = 123, -100123

        result = await repo.subscribe_shame(user_id, chat_id)

        assert result is True
        is_subscribed = await repo.is_shame_subscribed(user_id, chat_id)
        assert is_subscribed is True

    async def test_subscribe_shame_is_idempotent(self, repo: SteamLinkRepository):
        """subscribe_shame() должен быть идемпотентным."""
        user_id, chat_id = 123, -100123

        await repo.subscribe_shame(user_id, chat_id)
        await repo.subscribe_shame(user_id, chat_id)

        # Проверяем что подписка одна
        all_chats = await repo.get_all_shame_chats()
        assert len(all_chats) == 1

    async def test_unsubscribe_shame_removes_subscription(self, repo: SteamLinkRepository):
        """unsubscribe_shame() должен удалять подписку."""
        user_id, chat_id = 123, -100123

        await repo.subscribe_shame(user_id, chat_id)
        result = await repo.unsubscribe_shame(user_id, chat_id)

        assert result is True
        is_subscribed = await repo.is_shame_subscribed(user_id, chat_id)
        assert is_subscribed is False

    async def test_unsubscribe_shame_returns_false_for_nonexistent(self, repo: SteamLinkRepository):
        """unsubscribe_shame() должен возвращать False для несуществующей подписки."""
        result = await repo.unsubscribe_shame(999, -100999)

        assert result is False

    async def test_is_shame_subscribed_returns_true_when_subscribed(self, repo: SteamLinkRepository):
        """is_shame_subscribed() должен возвращать True для подписанного."""
        user_id, chat_id = 123, -100123

        await repo.subscribe_shame(user_id, chat_id)

        assert await repo.is_shame_subscribed(user_id, chat_id) is True

    async def test_is_shame_subscribed_returns_false_when_not_subscribed(self, repo: SteamLinkRepository):
        """is_shame_subscribed() должен возвращать False для неподписанного."""
        assert await repo.is_shame_subscribed(999, -100999) is False

    async def test_is_shame_subscribed_is_chat_specific(self, repo: SteamLinkRepository):
        """is_shame_subscribed() должен быть специфичным для чата."""
        user_id = 123

        await repo.subscribe_shame(user_id, -100111)

        assert await repo.is_shame_subscribed(user_id, -100111) is True
        assert await repo.is_shame_subscribed(user_id, -100222) is False

    async def test_get_shame_subscribers_returns_subscribers_with_steam_link(
        self, repo: SteamLinkRepository
    ):
        """get_shame_subscribers() должен возвращать подписчиков с привязанным Steam."""
        chat_id = -100123

        # Привязываем Steam и подписываем
        await repo.link(111, 11111111)
        await repo.subscribe_shame(111, chat_id)

        await repo.link(222, 22222222)
        await repo.subscribe_shame(222, chat_id)

        subscribers = await repo.get_shame_subscribers(chat_id)

        assert len(subscribers) == 2
        user_ids = [s[0] for s in subscribers]
        assert 111 in user_ids
        assert 222 in user_ids

    async def test_get_shame_subscribers_excludes_without_steam_link(
        self, repo: SteamLinkRepository
    ):
        """get_shame_subscribers() должен исключать подписчиков без привязки Steam."""
        chat_id = -100123

        # Подписываем без привязки Steam
        await repo.subscribe_shame(111, chat_id)

        # Привязываем Steam и подписываем
        await repo.link(222, 22222222)
        await repo.subscribe_shame(222, chat_id)

        subscribers = await repo.get_shame_subscribers(chat_id)

        assert len(subscribers) == 1
        assert subscribers[0][0] == 222
        assert subscribers[0][1] == 22222222

    async def test_get_shame_subscribers_returns_empty_for_new_chat(
        self, repo: SteamLinkRepository
    ):
        """get_shame_subscribers() должен возвращать пустой список для нового чата."""
        subscribers = await repo.get_shame_subscribers(-100999)

        assert subscribers == []

    async def test_get_shame_subscribers_filters_by_chat(self, repo: SteamLinkRepository):
        """get_shame_subscribers() должен фильтровать по чату."""
        await repo.link(111, 11111111)
        await repo.subscribe_shame(111, -100111)

        await repo.link(222, 22222222)
        await repo.subscribe_shame(222, -100222)

        subscribers_chat1 = await repo.get_shame_subscribers(-100111)
        subscribers_chat2 = await repo.get_shame_subscribers(-100222)

        assert len(subscribers_chat1) == 1
        assert subscribers_chat1[0][0] == 111
        assert len(subscribers_chat2) == 1
        assert subscribers_chat2[0][0] == 222

    async def test_get_all_shame_chats_returns_unique_chats(self, repo: SteamLinkRepository):
        """get_all_shame_chats() должен возвращать уникальные чаты."""
        await repo.subscribe_shame(111, -100111)
        await repo.subscribe_shame(222, -100111)  # Тот же чат
        await repo.subscribe_shame(333, -100222)

        chats = await repo.get_all_shame_chats()

        assert len(chats) == 2
        assert -100111 in chats
        assert -100222 in chats

    async def test_get_all_shame_chats_returns_empty_when_no_subscriptions(
        self, repo: SteamLinkRepository
    ):
        """get_all_shame_chats() должен возвращать пустой список без подписок."""
        chats = await repo.get_all_shame_chats()

        assert chats == []

    async def test_update_last_match_updates_match_id(self, repo: SteamLinkRepository):
        """update_last_match() должен обновлять last_match_id."""
        user_id, chat_id = 123, -100123
        match_id = 7654321000

        await repo.link(user_id, 87654321)
        await repo.subscribe_shame(user_id, chat_id)

        await repo.update_last_match(user_id, chat_id, match_id)

        subscribers = await repo.get_shame_subscribers(chat_id)
        assert len(subscribers) == 1
        assert subscribers[0][2] == match_id  # last_match_id

    async def test_update_last_match_is_chat_specific(self, repo: SteamLinkRepository):
        """update_last_match() должен обновлять только для конкретного чата."""
        user_id = 123

        await repo.link(user_id, 87654321)
        await repo.subscribe_shame(user_id, -100111)
        await repo.subscribe_shame(user_id, -100222)

        await repo.update_last_match(user_id, -100111, 1111111)

        subscribers_chat1 = await repo.get_shame_subscribers(-100111)
        subscribers_chat2 = await repo.get_shame_subscribers(-100222)

        assert subscribers_chat1[0][2] == 1111111
        assert subscribers_chat2[0][2] is None

    async def test_get_shame_subscribers_returns_last_match_id(self, repo: SteamLinkRepository):
        """get_shame_subscribers() должен возвращать last_match_id."""
        user_id, chat_id = 123, -100123
        match_id = 7654321000

        await repo.link(user_id, 87654321)
        await repo.subscribe_shame(user_id, chat_id)
        await repo.update_last_match(user_id, chat_id, match_id)

        subscribers = await repo.get_shame_subscribers(chat_id)

        assert len(subscribers) == 1
        user_id_result, account_id, last_match_id = subscribers[0]
        assert user_id_result == user_id
        assert account_id == 87654321
        assert last_match_id == match_id

    async def test_get_shame_subscribers_returns_none_for_new_subscription(
        self, repo: SteamLinkRepository
    ):
        """get_shame_subscribers() должен возвращать None для last_match_id новой подписки."""
        user_id, chat_id = 123, -100123

        await repo.link(user_id, 87654321)
        await repo.subscribe_shame(user_id, chat_id)

        subscribers = await repo.get_shame_subscribers(chat_id)

        assert len(subscribers) == 1
        assert subscribers[0][2] is None  # last_match_id is None


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

class TestSteamRepositoryEdgeCases:
    """Edge cases для SteamLinkRepository."""

    @pytest.fixture
    async def repo(self, db: Database) -> SteamLinkRepository:
        """Создаёт SteamLinkRepository с инициализированными таблицами."""
        repo = SteamLinkRepository(db)
        await repo.init_table()
        return repo

    async def test_unlink_removes_steam_but_keeps_subscription(self, repo: SteamLinkRepository):
        """unlink() удаляет Steam привязку, но подписка остаётся (без Steam)."""
        user_id, chat_id = 123, -100123

        await repo.link(user_id, 87654321)
        await repo.subscribe_shame(user_id, chat_id)

        await repo.unlink(user_id)

        # Подписка есть, но без Steam не попадает в get_shame_subscribers
        is_subscribed = await repo.is_shame_subscribed(user_id, chat_id)
        assert is_subscribed is True

        subscribers = await repo.get_shame_subscribers(chat_id)
        assert len(subscribers) == 0  # Нет Steam привязки

    async def test_multiple_users_same_chat(self, repo: SteamLinkRepository):
        """Несколько пользователей могут быть подписаны на один чат."""
        chat_id = -100123

        for i in range(5):
            user_id = 100 + i
            await repo.link(user_id, 10000000 + i)
            await repo.subscribe_shame(user_id, chat_id)

        subscribers = await repo.get_shame_subscribers(chat_id)
        assert len(subscribers) == 5

    async def test_one_user_multiple_chats(self, repo: SteamLinkRepository):
        """Один пользователь может быть подписан на несколько чатов."""
        user_id = 123
        await repo.link(user_id, 87654321)

        for i in range(5):
            chat_id = -100100 - i
            await repo.subscribe_shame(user_id, chat_id)

        chats = await repo.get_all_shame_chats()
        assert len(chats) == 5
