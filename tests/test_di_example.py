"""
Пример тестов с использованием Dependency Injection.

Демонстрирует, как легко тестировать сервисы с DI.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.services.ban_service import BanService
from src.services.spam_detector import SpamDetector, SpamType
from src.database import ViolationRepository, SpamRepository, BanStatsRepository
from src.database import WhitelistRepository, ChatSettingsRepository


class TestBanServiceWithDI:
    """Тесты BanService с использованием моков."""
    
    @pytest.fixture
    def mock_repos(self):
        """Создает моки репозиториев."""
        return {
            'violation': Mock(spec=ViolationRepository),
            'spam': Mock(spec=SpamRepository),
            'stats': Mock(spec=BanStatsRepository),
        }
    
    @pytest.fixture
    def ban_service(self, mock_repos):
        """Создает BanService с моками."""
        return BanService(
            violation_repo=mock_repos['violation'],
            spam_repo=mock_repos['spam'],
            stats_repo=mock_repos['stats']
        )
    
    @pytest.mark.asyncio
    async def test_get_violation_info(self, ban_service, mock_repos):
        """Тест получения информации о нарушениях."""
        # Arrange
        user_id = 123
        chat_id = 456
        expected_count = 3
        expected_banned_until = "2024-01-01T12:00:00"
        
        mock_repos['violation'].get_info = AsyncMock(
            return_value=(expected_count, expected_banned_until)
        )
        
        # Act
        count, banned_until = await ban_service.get_violation_info(user_id, chat_id)
        
        # Assert
        assert count == expected_count
        assert banned_until == expected_banned_until
        mock_repos['violation'].get_info.assert_called_once_with(user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_is_banned_returns_true_when_user_is_banned(self, ban_service, mock_repos):
        """Тест проверки бана — пользователь забанен."""
        # Arrange
        user_id = 123
        chat_id = 456
        
        mock_repos['violation'].is_banned = AsyncMock(return_value=True)
        
        # Act
        result = await ban_service.is_banned(user_id, chat_id)
        
        # Assert
        assert result is True
        mock_repos['violation'].is_banned.assert_called_once_with(user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_pardon_user_clears_all_records(self, ban_service, mock_repos):
        """Тест прощения пользователя — очищает все записи."""
        # Arrange
        user_id = 123
        chat_id = 456
        
        mock_repos['violation'].clear_user = AsyncMock(return_value=True)
        mock_repos['spam'].clear_user = AsyncMock(return_value=None)
        
        # Act
        result = await ban_service.pardon_user(user_id, chat_id)
        
        # Assert
        assert result is True
        mock_repos['violation'].clear_user.assert_called_once_with(user_id, chat_id)
        mock_repos['spam'].clear_user.assert_called_once_with(user_id, chat_id)


class TestSpamDetectorWithDI:
    """Тесты SpamDetector с использованием моков."""
    
    @pytest.fixture
    def mock_repos(self):
        """Создает моки репозиториев."""
        return {
            'spam': Mock(spec=SpamRepository),
            'whitelist': Mock(spec=WhitelistRepository),
            'settings': Mock(spec=ChatSettingsRepository),
        }
    
    @pytest.fixture
    def spam_detector(self, mock_repos):
        """Создает SpamDetector с моками."""
        return SpamDetector(
            spam_repo=mock_repos['spam'],
            whitelist_repo=mock_repos['whitelist'],
            settings_repo=mock_repos['settings']
        )
    
    @pytest.mark.asyncio
    async def test_whitelisted_user_not_detected_as_spam(self, spam_detector, mock_repos):
        """Тест: пользователь из белого списка не детектится как спамер."""
        # Arrange
        user_id = 123
        chat_id = 456
        
        mock_repos['whitelist'].is_whitelisted = AsyncMock(return_value=True)
        mock_repos['settings'].get = AsyncMock(return_value={
            'sticker_limit': 3,
            'sticker_window': 30,
        })
        
        # Act
        result = await spam_detector.check(
            user_id=user_id,
            chat_id=chat_id,
            spam_type=SpamType.STICKER
        )
        
        # Assert
        assert result.is_spam is False
        assert result.is_warning is False
        assert result.count == 0
        mock_repos['whitelist'].is_whitelisted.assert_called_once_with(user_id, chat_id)
        # Не должны проверять спам для whitelisted
        mock_repos['spam'].add_and_count_recent.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_spam_detected_when_limit_exceeded(self, spam_detector, mock_repos):
        """Тест: спам детектится при превышении лимита."""
        # Arrange
        user_id = 123
        chat_id = 456
        limit = 3
        
        mock_repos['whitelist'].is_whitelisted = AsyncMock(return_value=False)
        mock_repos['settings'].get = AsyncMock(return_value={
            'sticker_limit': limit,
            'sticker_window': 30,
            'warning_enabled': True,
        })
        mock_repos['spam'].add_and_count_recent = AsyncMock(return_value=limit)
        
        # Act
        result = await spam_detector.check(
            user_id=user_id,
            chat_id=chat_id,
            spam_type=SpamType.STICKER
        )
        
        # Assert
        assert result.is_spam is True
        assert result.count == limit
        assert result.limit == limit
        assert result.spam_type == SpamType.STICKER
    
    @pytest.mark.asyncio
    async def test_warning_triggered_one_before_limit(self, spam_detector, mock_repos):
        """Тест: предупреждение срабатывает за 1 до лимита."""
        # Arrange
        user_id = 123
        chat_id = 456
        limit = 3
        count = limit - 1  # 2
        
        mock_repos['whitelist'].is_whitelisted = AsyncMock(return_value=False)
        mock_repos['settings'].get = AsyncMock(return_value={
            'sticker_limit': limit,
            'sticker_window': 30,
            'warning_enabled': True,
        })
        mock_repos['spam'].add_and_count_recent = AsyncMock(return_value=count)
        
        # Act
        result = await spam_detector.check(
            user_id=user_id,
            chat_id=chat_id,
            spam_type=SpamType.STICKER
        )
        
        # Assert
        assert result.is_spam is False
        assert result.is_warning is True
        assert result.count == count


# Пример интеграционного теста с реальным контейнером
class TestDIContainer:
    """Тесты DI контейнера."""
    
    def test_container_registers_and_resolves_services(self):
        """Тест регистрации и получения сервисов."""
        from src.container import ServiceContainer, ServiceLifetime
        
        # Arrange
        container = ServiceContainer()
        
        class MockService:
            def __init__(self, value: str):
                self.value = value
        
        # Act
        container.register(
            MockService,
            lambda: MockService("test"),
            ServiceLifetime.SINGLETON
        )
        
        service1 = container.get(MockService)
        service2 = container.get(MockService)
        
        # Assert
        assert service1 is not None
        assert service1.value == "test"
        assert service1 is service2  # Singleton — тот же экземпляр
    
    def test_container_detects_circular_dependencies(self):
        """Тест обнаружения циклических зависимостей."""
        from src.container import ServiceContainer, ServiceLifetime
        
        # Arrange
        container = ServiceContainer()
        
        class ServiceA:
            pass
        
        class ServiceB:
            pass
        
        # Создаем циклическую зависимость
        container.register(
            ServiceA,
            lambda: ServiceA() if container.get(ServiceB) else None,
            ServiceLifetime.SINGLETON
        )
        
        container.register(
            ServiceB,
            lambda: ServiceB() if container.get(ServiceA) else None,
            ServiceLifetime.SINGLETON
        )
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Circular dependency"):
            container.get(ServiceA)
    
    def test_transient_creates_new_instances(self):
        """Тест Transient — создает новые экземпляры."""
        from src.container import ServiceContainer, ServiceLifetime
        
        # Arrange
        container = ServiceContainer()
        
        class TransientService:
            pass
        
        container.register(
            TransientService,
            lambda: TransientService(),
            ServiceLifetime.TRANSIENT
        )
        
        # Act
        service1 = container.get(TransientService)
        service2 = container.get(TransientService)
        
        # Assert
        assert service1 is not service2  # Разные экземпляры


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
