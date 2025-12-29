"""
Тесты для SpamDetector сервиса.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

# NOTE: Если тесты не запускаются из-за ошибки в src/config.py,
# нужно исправить конфликт __slots__ с default values в dataclass.
from src.services.spam_detector import SpamDetector, SpamType, SpamCheckResult


@pytest.fixture
def mock_spam_repo():
    """Мок SpamRepository."""
    repo = MagicMock()
    repo.add_record = AsyncMock()
    repo.count_recent = AsyncMock(return_value=0)
    repo.clear_user = AsyncMock()
    return repo


@pytest.fixture
def mock_whitelist_repo():
    """Мок WhitelistRepository."""
    repo = MagicMock()
    repo.is_whitelisted = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_settings_repo():
    """Мок ChatSettingsRepository."""
    repo = MagicMock()
    repo.get = AsyncMock(return_value={
        "sticker_limit": 3,
        "sticker_window": 30,
        "text_limit": 3,
        "text_window": 20,
        "image_limit": 3,
        "image_window": 30,
        "video_limit": 3,
        "video_window": 30,
        "warning_enabled": True,
    })
    return repo


@pytest.fixture
def spam_detector(mock_spam_repo, mock_whitelist_repo, mock_settings_repo):
    """Создаёт SpamDetector с моками."""
    return SpamDetector(mock_spam_repo, mock_whitelist_repo, mock_settings_repo)


class TestSpamDetectorCheck:
    """Тесты метода check()."""
    
    @pytest.mark.asyncio
    async def test_check_whitelisted_user_not_spam(
        self, spam_detector, mock_whitelist_repo, mock_spam_repo
    ):
        """Тест: пользователь в whitelist не считается спамером."""
        mock_whitelist_repo.is_whitelisted.return_value = True
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER
        )
        
        assert result.is_spam is False
        assert result.is_warning is False
        assert result.count == 0
        # Не должен записывать активность для whitelisted
        mock_spam_repo.add_record.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_check_normal_user_no_spam(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: обычный пользователь без превышения лимита."""
        mock_spam_repo.count_recent.return_value = 1
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER
        )
        
        assert result.is_spam is False
        assert result.is_warning is False
        assert result.count == 1
        assert result.limit == 3
        mock_spam_repo.add_record.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_spam_limit_exceeded(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: превышение лимита — спам."""
        mock_spam_repo.count_recent.return_value = 3  # limit = 3
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER
        )
        
        assert result.is_spam is True
        assert result.is_warning is False
        assert result.count == 3
        assert result.spam_type == SpamType.STICKER
    
    @pytest.mark.asyncio
    async def test_check_warning_one_before_limit(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: предупреждение за 1 до лимита."""
        mock_spam_repo.count_recent.return_value = 2  # limit - 1 = 2
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER
        )
        
        assert result.is_spam is False
        assert result.is_warning is True
        assert result.count == 2
    
    @pytest.mark.asyncio
    async def test_check_warning_disabled(
        self, spam_detector, mock_spam_repo, mock_settings_repo
    ):
        """Тест: предупреждение отключено в настройках."""
        mock_settings_repo.get.return_value = {
            "sticker_limit": 3,
            "sticker_window": 30,
            "text_limit": 3,
            "text_window": 20,
            "image_limit": 3,
            "image_window": 30,
            "video_limit": 3,
            "video_window": 30,
            "warning_enabled": False,  # Отключено
        }
        mock_spam_repo.count_recent.return_value = 2  # limit - 1
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER
        )
        
        assert result.is_spam is False
        assert result.is_warning is False  # Не должно быть предупреждения
    
    @pytest.mark.asyncio
    async def test_check_text_spam_with_hash(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: текстовый спам с content_hash."""
        mock_spam_repo.count_recent.return_value = 3
        content_hash = "abc123hash"
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.TEXT,
            content_hash=content_hash
        )
        
        assert result.is_spam is True
        assert result.spam_type == SpamType.TEXT
        # Проверяем, что hash передаётся в count_recent
        mock_spam_repo.count_recent.assert_called_once()
        call_args = mock_spam_repo.count_recent.call_args
        assert call_args[0][4] == content_hash  # content_hash в позиционных аргументах
    
    @pytest.mark.asyncio
    async def test_check_photo_spam(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: спам фотографиями."""
        mock_spam_repo.count_recent.return_value = 3
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.PHOTO,
            content_hash="photo_hash"
        )
        
        assert result.is_spam is True
        assert result.spam_type == SpamType.PHOTO
        assert result.reason == "одинаковых картинок"
    
    @pytest.mark.asyncio
    async def test_check_video_spam(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: спам видео."""
        mock_spam_repo.count_recent.return_value = 3
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.VIDEO,
            content_hash="video_hash"
        )
        
        assert result.is_spam is True
        assert result.spam_type == SpamType.VIDEO
        assert result.reason == "одинаковых видео"
    
    @pytest.mark.asyncio
    async def test_check_animation_spam(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: спам гифками."""
        mock_spam_repo.count_recent.return_value = 3
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.ANIMATION
        )
        
        assert result.is_spam is True
        assert result.spam_type == SpamType.ANIMATION
        assert result.reason == "гифок"
    
    @pytest.mark.asyncio
    async def test_check_sticker_no_hash_used(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: для стикеров hash не используется."""
        mock_spam_repo.count_recent.return_value = 1
        
        await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER,
            content_hash="some_hash"  # Передаём hash
        )
        
        # Для стикеров hash не должен передаваться в count_recent
        call_args = mock_spam_repo.count_recent.call_args
        assert call_args[0][4] is None  # content_hash должен быть None
    
    @pytest.mark.asyncio
    async def test_check_custom_limits(
        self, spam_detector, mock_spam_repo, mock_settings_repo
    ):
        """Тест: кастомные лимиты чата."""
        mock_settings_repo.get.return_value = {
            "sticker_limit": 10,  # Увеличенный лимит
            "sticker_window": 60,
            "text_limit": 5,
            "text_window": 30,
            "image_limit": 5,
            "image_window": 30,
            "video_limit": 5,
            "video_window": 30,
            "warning_enabled": True,
        }
        mock_spam_repo.count_recent.return_value = 5  # Меньше нового лимита
        
        result = await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER
        )
        
        assert result.is_spam is False
        assert result.limit == 10
    
    @pytest.mark.asyncio
    async def test_check_records_activity(
        self, spam_detector, mock_spam_repo
    ):
        """Тест: активность записывается в репозиторий."""
        await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER,
            content_hash="test_hash"
        )
        
        mock_spam_repo.add_record.assert_called_once_with(
            123, 456, "sticker", "test_hash"
        )
    
    @pytest.mark.asyncio
    async def test_check_gets_chat_settings(
        self, spam_detector, mock_settings_repo
    ):
        """Тест: настройки чата запрашиваются."""
        await spam_detector.check(
            user_id=123,
            chat_id=456,
            spam_type=SpamType.STICKER
        )
        
        mock_settings_repo.get.assert_called_once_with(456)


class TestSpamCheckResult:
    """Тесты для SpamCheckResult dataclass."""
    
    def test_spam_check_result_creation(self):
        """Тест создания SpamCheckResult."""
        result = SpamCheckResult(
            is_spam=True,
            is_warning=False,
            count=5,
            limit=3,
            spam_type=SpamType.STICKER,
            reason="стикеров"
        )
        
        assert result.is_spam is True
        assert result.is_warning is False
        assert result.count == 5
        assert result.limit == 3
        assert result.spam_type == SpamType.STICKER
        assert result.reason == "стикеров"
    
    def test_spam_check_result_default_reason(self):
        """Тест SpamCheckResult с дефолтным reason."""
        result = SpamCheckResult(
            is_spam=False,
            is_warning=False,
            count=1,
            limit=3,
            spam_type=SpamType.TEXT
        )
        
        assert result.reason == ""


class TestSpamType:
    """Тесты для SpamType enum."""
    
    def test_spam_type_values(self):
        """Тест значений SpamType."""
        assert SpamType.STICKER.value == "sticker"
        assert SpamType.ANIMATION.value == "animation"
        assert SpamType.TEXT.value == "text"
        assert SpamType.PHOTO.value == "photo"
        assert SpamType.VIDEO.value == "video"
