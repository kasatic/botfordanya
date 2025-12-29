"""
Тесты для BanService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# NOTE: Если тесты не запускаются из-за ошибки в src/config.py,
# нужно исправить конфликт __slots__ с default values в dataclass.
from src.services.ban_service import BanService


@pytest.fixture
def mock_violation_repo():
    """Мок ViolationRepository."""
    repo = MagicMock()
    repo.get_info = AsyncMock(return_value=(0, None))
    repo.add_violation = AsyncMock(return_value=1)
    repo.is_banned = AsyncMock(return_value=False)
    repo.remove_ban = AsyncMock(return_value=True)
    repo.clear_user = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_spam_repo():
    """Мок SpamRepository."""
    repo = MagicMock()
    repo.clear_user = AsyncMock()
    return repo


@pytest.fixture
def mock_stats_repo():
    """Мок BanStatsRepository."""
    repo = MagicMock()
    repo.record_ban = AsyncMock()
    return repo


@pytest.fixture
def mock_context():
    """Мок telegram context."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.restrict_chat_member = AsyncMock()
    return context


@pytest.fixture
def ban_service(mock_violation_repo, mock_spam_repo, mock_stats_repo):
    """Создаёт BanService с моками."""
    return BanService(mock_violation_repo, mock_spam_repo, mock_stats_repo)


class TestBanServiceIsBanned:
    """Тесты метода is_banned()."""
    
    @pytest.mark.asyncio
    async def test_is_banned_returns_true(self, ban_service, mock_violation_repo):
        """Тест: пользователь забанен."""
        mock_violation_repo.is_banned.return_value = True
        
        result = await ban_service.is_banned(user_id=123, chat_id=456)
        
        assert result is True
        mock_violation_repo.is_banned.assert_called_once_with(123, 456)
    
    @pytest.mark.asyncio
    async def test_is_banned_returns_false(self, ban_service, mock_violation_repo):
        """Тест: пользователь не забанен."""
        mock_violation_repo.is_banned.return_value = False
        
        result = await ban_service.is_banned(user_id=123, chat_id=456)
        
        assert result is False


class TestBanServiceGetViolationInfo:
    """Тесты метода get_violation_info()."""
    
    @pytest.mark.asyncio
    async def test_get_violation_info_no_violations(
        self, ban_service, mock_violation_repo
    ):
        """Тест: нет нарушений."""
        mock_violation_repo.get_info.return_value = (0, None)
        
        count, banned_until = await ban_service.get_violation_info(
            user_id=123, chat_id=456
        )
        
        assert count == 0
        assert banned_until is None
    
    @pytest.mark.asyncio
    async def test_get_violation_info_with_violations(
        self, ban_service, mock_violation_repo
    ):
        """Тест: есть нарушения."""
        ban_time = datetime.now().isoformat()
        mock_violation_repo.get_info.return_value = (3, ban_time)
        
        count, banned_until = await ban_service.get_violation_info(
            user_id=123, chat_id=456
        )
        
        assert count == 3
        assert banned_until == ban_time


class TestBanServiceApplyBan:
    """Тесты метода apply_ban()."""
    
    @pytest.mark.asyncio
    async def test_apply_ban_first_violation_10_minutes(
        self, ban_service, mock_violation_repo, mock_context, mock_stats_repo
    ):
        """Тест: первое нарушение — бан на 10 минут."""
        mock_violation_repo.get_info.return_value = (0, None)  # Нет предыдущих
        mock_violation_repo.add_violation.return_value = 1
        
        success, violation_count, ban_minutes = await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123,
            ban_type="spam",
            reason="стикеры"
        )
        
        assert success is True
        assert violation_count == 1
        assert ban_minutes == 10  # Первый бан = 10 минут
        mock_context.bot.restrict_chat_member.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_ban_second_violation_60_minutes(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест: второе нарушение — бан на 60 минут."""
        mock_violation_repo.get_info.return_value = (1, None)  # 1 предыдущее
        mock_violation_repo.add_violation.return_value = 2
        
        success, violation_count, ban_minutes = await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        assert success is True
        assert violation_count == 2
        assert ban_minutes == 60  # Второй бан = 60 минут
    
    @pytest.mark.asyncio
    async def test_apply_ban_third_violation_300_minutes(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест: третье нарушение — бан на 300 минут (5 часов)."""
        mock_violation_repo.get_info.return_value = (2, None)  # 2 предыдущих
        mock_violation_repo.add_violation.return_value = 3
        
        success, violation_count, ban_minutes = await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        assert success is True
        assert violation_count == 3
        assert ban_minutes == 300  # Третий бан = 300 минут
    
    @pytest.mark.asyncio
    async def test_apply_ban_fourth_violation_1440_minutes(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест: четвёртое нарушение — бан на 1440 минут (24 часа)."""
        mock_violation_repo.get_info.return_value = (3, None)  # 3 предыдущих
        mock_violation_repo.add_violation.return_value = 4
        
        success, violation_count, ban_minutes = await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        assert success is True
        assert violation_count == 4
        assert ban_minutes == 1440  # Четвёртый бан = 1440 минут
    
    @pytest.mark.asyncio
    async def test_apply_ban_fifth_violation_default_duration(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест: пятое+ нарушение — дефолтный бан (2880 минут = 48 часов)."""
        mock_violation_repo.get_info.return_value = (4, None)  # 4 предыдущих
        mock_violation_repo.add_violation.return_value = 5
        
        success, violation_count, ban_minutes = await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        assert success is True
        assert violation_count == 5
        assert ban_minutes == 2880  # Дефолт = 2880 минут
    
    @pytest.mark.asyncio
    async def test_apply_ban_records_stats(
        self, ban_service, mock_violation_repo, mock_context, mock_stats_repo
    ):
        """Тест: бан записывается в статистику."""
        mock_violation_repo.get_info.return_value = (0, None)
        mock_violation_repo.add_violation.return_value = 1
        
        await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123,
            ban_type="spam",
            reason="стикеры"
        )
        
        mock_stats_repo.record_ban.assert_called_once_with(
            123, 456, "spam", 10, "стикеры"
        )
    
    @pytest.mark.asyncio
    async def test_apply_ban_telegram_error(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест: ошибка Telegram при бане."""
        from telegram.error import BadRequest
        
        mock_violation_repo.get_info.return_value = (0, None)
        mock_violation_repo.add_violation.return_value = 1
        mock_context.bot.restrict_chat_member.side_effect = BadRequest("Not enough rights")
        
        success, violation_count, ban_minutes = await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        assert success is False
        assert violation_count == 1
        assert ban_minutes == 10
    
    @pytest.mark.asyncio
    async def test_apply_ban_uses_restricted_permissions(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест: применяются ограниченные права."""
        mock_violation_repo.get_info.return_value = (0, None)
        mock_violation_repo.add_violation.return_value = 1
        
        await ban_service.apply_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        call_kwargs = mock_context.bot.restrict_chat_member.call_args.kwargs
        assert call_kwargs["chat_id"] == 456
        assert call_kwargs["user_id"] == 123
        assert call_kwargs["permissions"] == BanService.RESTRICTED_PERMISSIONS


class TestBanServiceRemoveBan:
    """Тесты метода remove_ban()."""
    
    @pytest.mark.asyncio
    async def test_remove_ban_success(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест: успешное снятие бана."""
        result = await ban_service.remove_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        assert result is True
        mock_violation_repo.remove_ban.assert_called_once_with(123, 456)
        mock_context.bot.restrict_chat_member.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_ban_uses_full_permissions(
        self, ban_service, mock_context
    ):
        """Тест: восстанавливаются полные права."""
        await ban_service.remove_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        call_kwargs = mock_context.bot.restrict_chat_member.call_args.kwargs
        assert call_kwargs["permissions"] == BanService.FULL_PERMISSIONS
    
    @pytest.mark.asyncio
    async def test_remove_ban_telegram_error(
        self, ban_service, mock_context
    ):
        """Тест: ошибка Telegram при снятии бана."""
        from telegram.error import BadRequest
        
        mock_context.bot.restrict_chat_member.side_effect = BadRequest("User not found")
        
        result = await ban_service.remove_ban(
            context=mock_context,
            chat_id=456,
            user_id=123
        )
        
        assert result is False


class TestBanServicePardonUser:
    """Тесты метода pardon_user()."""
    
    @pytest.mark.asyncio
    async def test_pardon_user_clears_violations(
        self, ban_service, mock_violation_repo, mock_spam_repo
    ):
        """Тест: pardon очищает нарушения."""
        result = await ban_service.pardon_user(user_id=123, chat_id=456)
        
        assert result is True
        mock_violation_repo.clear_user.assert_called_once_with(123, 456)
    
    @pytest.mark.asyncio
    async def test_pardon_user_clears_spam_records(
        self, ban_service, mock_spam_repo
    ):
        """Тест: pardon очищает записи спама."""
        await ban_service.pardon_user(user_id=123, chat_id=456)
        
        mock_spam_repo.clear_user.assert_called_once_with(123, 456)


class TestBanServiceGetRemainingTime:
    """Тесты метода get_remaining_time()."""
    
    @pytest.mark.asyncio
    async def test_get_remaining_time_not_banned(
        self, ban_service, mock_violation_repo
    ):
        """Тест: пользователь не забанен."""
        mock_violation_repo.get_info.return_value = (0, None)
        
        result = await ban_service.get_remaining_time(user_id=123, chat_id=456)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_remaining_time_ban_expired(
        self, ban_service, mock_violation_repo
    ):
        """Тест: бан истёк."""
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_violation_repo.get_info.return_value = (1, past_time)
        
        result = await ban_service.get_remaining_time(user_id=123, chat_id=456)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_remaining_time_active_ban(
        self, ban_service, mock_violation_repo
    ):
        """Тест: активный бан."""
        future_time = (datetime.now() + timedelta(minutes=30)).isoformat()
        mock_violation_repo.get_info.return_value = (1, future_time)
        
        result = await ban_service.get_remaining_time(user_id=123, chat_id=456)
        
        # Должно быть около 30 минут (с погрешностью)
        assert result is not None
        assert 28 <= result <= 31


class TestBanServicePermissions:
    """Тесты констант разрешений."""
    
    def test_restricted_permissions(self):
        """Тест ограниченных разрешений."""
        perms = BanService.RESTRICTED_PERMISSIONS
        
        assert perms.can_send_messages is True
        assert perms.can_send_photos is False
        assert perms.can_send_videos is False
        assert perms.can_send_audios is False
        assert perms.can_send_documents is False
        assert perms.can_send_other_messages is False
        assert perms.can_send_voice_notes is False
        assert perms.can_send_video_notes is False
        assert perms.can_send_polls is False
    
    def test_full_permissions(self):
        """Тест полных разрешений."""
        perms = BanService.FULL_PERMISSIONS
        
        assert perms.can_send_messages is True
        assert perms.can_send_photos is True
        assert perms.can_send_videos is True
        assert perms.can_send_audios is True
        assert perms.can_send_documents is True
        assert perms.can_send_other_messages is True
        assert perms.can_send_voice_notes is True
        assert perms.can_send_video_notes is True
        assert perms.can_send_polls is True


class TestProgressiveBanDurations:
    """Тесты прогрессивной системы банов."""
    
    @pytest.mark.asyncio
    async def test_progressive_ban_sequence(
        self, ban_service, mock_violation_repo, mock_context
    ):
        """Тест последовательности прогрессивных банов."""
        expected_durations = [10, 60, 300, 1440, 2880, 2880]
        
        for i, expected_duration in enumerate(expected_durations):
            mock_violation_repo.get_info.return_value = (i, None)
            mock_violation_repo.add_violation.return_value = i + 1
            
            _, _, ban_minutes = await ban_service.apply_ban(
                context=mock_context,
                chat_id=456,
                user_id=123
            )
            
            assert ban_minutes == expected_duration, \
                f"Violation #{i+1}: expected {expected_duration}, got {ban_minutes}"
