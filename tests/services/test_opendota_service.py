"""
Тесты для OpenDota сервиса.
"""
import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

# NOTE: Если тесты не запускаются из-за ошибки в src/config.py,
# нужно исправить конфликт __slots__ с default values в dataclass.
# Для Python 3.10+ используйте slots=True в декораторе @dataclass.
from src.services.opendota_service import OpenDotaService, PlayerProfile, LiveGame, retry_with_backoff


class TestSteamId64ToAccountId:
    """Тесты конвертации Steam ID 64 в Account ID."""
    
    def test_steam_id64_to_account_id_valid(self):
        """Тест конвертации валидного Steam ID 64."""
        # Steam ID 64 = Account ID + 76561197960265728
        steam_id64 = 76561198012345678
        expected_account_id = 52079950  # 76561198012345678 - 76561197960265728
        
        result = OpenDotaService.steam_id64_to_account_id(steam_id64)
        
        assert result == expected_account_id
    
    def test_steam_id64_to_account_id_minimum(self):
        """Тест конвертации минимального Steam ID 64."""
        steam_id64 = 76561197960265728  # Минимальный Steam ID 64
        expected_account_id = 0
        
        result = OpenDotaService.steam_id64_to_account_id(steam_id64)
        
        assert result == expected_account_id
    
    def test_steam_id64_to_account_id_large(self):
        """Тест конвертации большого Steam ID 64."""
        steam_id64 = 76561199000000000
        expected_account_id = 1039734272
        
        result = OpenDotaService.steam_id64_to_account_id(steam_id64)
        
        assert result == expected_account_id


class TestParseAccountIdSync:
    """Тесты синхронного парсера Account ID."""
    
    # --- Тесты для Account ID ---
    
    def test_parse_account_id_direct_number(self):
        """Тест парсинга прямого Account ID."""
        result = OpenDotaService.parse_account_id_sync("123456789")
        
        assert result == 123456789
    
    def test_parse_account_id_with_spaces(self):
        """Тест парсинга Account ID с пробелами."""
        result = OpenDotaService.parse_account_id_sync("  123456789  ")
        
        assert result == 123456789
    
    def test_parse_account_id_short(self):
        """Тест парсинга короткого Account ID."""
        result = OpenDotaService.parse_account_id_sync("12345")
        
        assert result == 12345
    
    # --- Тесты для Steam ID 64 ---
    
    def test_parse_steam_id64(self):
        """Тест парсинга Steam ID 64."""
        steam_id64 = "76561198012345678"
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = OpenDotaService.parse_account_id_sync(steam_id64)
        
        assert result == expected
    
    def test_parse_steam_id64_with_spaces(self):
        """Тест парсинга Steam ID 64 с пробелами."""
        steam_id64 = "  76561198012345678  "
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = OpenDotaService.parse_account_id_sync(steam_id64)
        
        assert result == expected
    
    # --- Тесты для Dotabuff URL ---
    
    def test_parse_dotabuff_url_https(self):
        """Тест парсинга HTTPS Dotabuff URL."""
        url = "https://dotabuff.com/players/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_dotabuff_url_http(self):
        """Тест парсинга HTTP Dotabuff URL."""
        url = "http://dotabuff.com/players/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_dotabuff_url_www(self):
        """Тест парсинга Dotabuff URL с www."""
        url = "https://www.dotabuff.com/players/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_dotabuff_url_with_trailing_slash(self):
        """Тест парсинга Dotabuff URL с trailing slash."""
        url = "https://dotabuff.com/players/123456789/"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_dotabuff_url_with_subpath(self):
        """Тест парсинга Dotabuff URL с дополнительным путём."""
        url = "https://dotabuff.com/players/123456789/matches"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_dotabuff_url_case_insensitive(self):
        """Тест парсинга Dotabuff URL без учёта регистра."""
        url = "https://DOTABUFF.COM/PLAYERS/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    # --- Тесты для OpenDota URL ---
    
    def test_parse_opendota_url_https(self):
        """Тест парсинга HTTPS OpenDota URL."""
        url = "https://opendota.com/players/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_opendota_url_http(self):
        """Тест парсинга HTTP OpenDota URL."""
        url = "http://opendota.com/players/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_opendota_url_www(self):
        """Тест парсинга OpenDota URL с www."""
        url = "https://www.opendota.com/players/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_opendota_url_with_trailing_slash(self):
        """Тест парсинга OpenDota URL с trailing slash."""
        url = "https://opendota.com/players/123456789/"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_opendota_url_with_subpath(self):
        """Тест парсинга OpenDota URL с дополнительным путём."""
        url = "https://opendota.com/players/123456789/overview"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    def test_parse_opendota_url_case_insensitive(self):
        """Тест парсинга OpenDota URL без учёта регистра."""
        url = "https://OPENDOTA.COM/PLAYERS/123456789"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == 123456789
    
    # --- Тесты для Steam Community URL ---
    
    def test_parse_steam_profiles_url_https(self):
        """Тест парсинга HTTPS Steam profiles URL."""
        url = "https://steamcommunity.com/profiles/76561198012345678"
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == expected
    
    def test_parse_steam_profiles_url_http(self):
        """Тест парсинга HTTP Steam profiles URL."""
        url = "http://steamcommunity.com/profiles/76561198012345678"
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == expected
    
    def test_parse_steam_profiles_url_www(self):
        """Тест парсинга Steam profiles URL с www."""
        url = "https://www.steamcommunity.com/profiles/76561198012345678"
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == expected
    
    def test_parse_steam_profiles_url_with_trailing_slash(self):
        """Тест парсинга Steam profiles URL с trailing slash."""
        url = "https://steamcommunity.com/profiles/76561198012345678/"
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == expected
    
    def test_parse_steam_profiles_url_case_insensitive(self):
        """Тест парсинга Steam profiles URL без учёта регистра."""
        url = "https://STEAMCOMMUNITY.COM/PROFILES/76561198012345678"
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result == expected
    
    # --- Тесты для Steam vanity URL (возвращает None) ---
    
    def test_parse_steam_vanity_url_returns_none(self):
        """Тест парсинга Steam vanity URL возвращает None (требуется async)."""
        url = "https://steamcommunity.com/id/customname"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result is None
    
    def test_parse_steam_vanity_url_with_numbers(self):
        """Тест парсинга Steam vanity URL с числами в имени."""
        url = "https://steamcommunity.com/id/player123"
        
        result = OpenDotaService.parse_account_id_sync(url)
        
        assert result is None
    
    # --- Тесты для невалидных входов ---
    
    def test_parse_empty_string(self):
        """Тест парсинга пустой строки."""
        result = OpenDotaService.parse_account_id_sync("")
        
        assert result is None
    
    def test_parse_none_input(self):
        """Тест парсинга None."""
        result = OpenDotaService.parse_account_id_sync(None)
        
        assert result is None
    
    def test_parse_whitespace_only(self):
        """Тест парсинга строки только из пробелов."""
        result = OpenDotaService.parse_account_id_sync("   ")
        
        assert result is None
    
    def test_parse_garbage_text(self):
        """Тест парсинга мусорного текста."""
        result = OpenDotaService.parse_account_id_sync("hello world")
        
        assert result is None
    
    def test_parse_invalid_url(self):
        """Тест парсинга невалидного URL."""
        result = OpenDotaService.parse_account_id_sync("https://example.com/players/123")
        
        # Должен вернуть 123 как число (парсер извлекает числа)
        assert result == 123
    
    def test_parse_negative_number(self):
        """Тест парсинга отрицательного числа."""
        result = OpenDotaService.parse_account_id_sync("-123456789")
        
        # Парсер убирает нечисловые символы, получается 123456789
        assert result == 123456789
    
    def test_parse_zero(self):
        """Тест парсинга нуля."""
        result = OpenDotaService.parse_account_id_sync("0")
        
        # Парсер возвращает 0 как валидное число (хотя это не реальный Account ID)
        # Валидация Account ID должна происходить на уровне API
        assert result == 0
    
    def test_parse_letters_only(self):
        """Тест парсинга строки только из букв."""
        result = OpenDotaService.parse_account_id_sync("abcdefgh")
        
        assert result is None
    
    def test_parse_special_characters(self):
        """Тест парсинга специальных символов."""
        result = OpenDotaService.parse_account_id_sync("!@#$%^&*()")
        
        assert result is None
    
    def test_parse_mixed_garbage(self):
        """Тест парсинга смешанного мусора."""
        result = OpenDotaService.parse_account_id_sync("abc123def456")
        
        # Парсер извлекает числа: 123456
        assert result == 123456


class TestPlayerProfile:
    """Тесты для PlayerProfile dataclass."""
    
    def test_rank_name_unranked(self):
        """Тест названия ранга для unranked."""
        profile = PlayerProfile(
            account_id=123,
            persona_name="Test",
            avatar="",
            rank_tier=None
        )
        
        assert profile.rank_name == "Unranked"
    
    def test_rank_name_herald(self):
        """Тест названия ранга Herald."""
        profile = PlayerProfile(
            account_id=123,
            persona_name="Test",
            avatar="",
            rank_tier=11  # Herald 1
        )
        
        assert profile.rank_name == "Herald 1"
    
    def test_rank_name_immortal(self):
        """Тест названия ранга Immortal."""
        profile = PlayerProfile(
            account_id=123,
            persona_name="Test",
            avatar="",
            rank_tier=80  # Immortal
        )
        
        assert profile.rank_name == "Immortal"
    
    def test_rank_name_ancient_5(self):
        """Тест названия ранга Ancient 5."""
        profile = PlayerProfile(
            account_id=123,
            persona_name="Test",
            avatar="",
            rank_tier=65  # Ancient 5
        )
        
        assert profile.rank_name == "Ancient 5"


class TestLiveGame:
    """Тесты для LiveGame dataclass."""
    
    def test_time_str_format(self):
        """Тест форматирования времени игры."""
        game = LiveGame(
            match_id=123,
            game_time=754,  # 12:34
            game_mode="All Pick",
            player_hero="Anti-Mage",
            player_team="Radiant"
        )
        
        assert game.minutes == 12
        assert game.seconds == 34
        assert game.time_str == "12:34"
    
    def test_time_str_zero_padded_seconds(self):
        """Тест форматирования времени с нулями."""
        game = LiveGame(
            match_id=123,
            game_time=65,  # 1:05
            game_mode="All Pick",
            player_hero="Anti-Mage",
            player_team="Radiant"
        )
        
        assert game.time_str == "1:05"



class TestRetryWithBackoff:
    """Тесты для декоратора retry_with_backoff."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Тест успешного выполнения с первой попытки."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def mock_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await mock_func()
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self):
        """Тест успешного выполнения со второй попытки."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise aiohttp.ClientError("Network error")
            return "success"
        
        result = await mock_func()
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_success_on_third_attempt(self):
        """Тест успешного выполнения с третьей попытки."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError("Timeout")
            return "success"
        
        result = await mock_func()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self):
        """Тест провала всех попыток."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def mock_func():
            nonlocal call_count
            call_count += 1
            raise aiohttp.ClientError("Network error")
        
        with pytest.raises(aiohttp.ClientError):
            await mock_func()
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff_timing(self):
        """Тест exponential backoff задержек."""
        call_times = []
        
        @retry_with_backoff(max_retries=3, base_delay=0.1)
        async def mock_func():
            call_times.append(datetime.now())
            raise aiohttp.ClientError("Network error")
        
        try:
            await mock_func()
        except aiohttp.ClientError:
            pass
        
        assert len(call_times) == 3
        
        # Проверяем задержки между попытками
        # Первая задержка: ~0.1s (base_delay * 2^0)
        delay1 = (call_times[1] - call_times[0]).total_seconds()
        assert 0.08 < delay1 < 0.15  # Допускаем небольшую погрешность
        
        # Вторая задержка: ~0.2s (base_delay * 2^1)
        delay2 = (call_times[2] - call_times[1]).total_seconds()
        assert 0.18 < delay2 < 0.25
    
    @pytest.mark.asyncio
    async def test_retry_with_timeout_error(self):
        """Тест retry при TimeoutError."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise asyncio.TimeoutError()
            return "success"
        
        result = await mock_func()
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_does_not_catch_other_exceptions(self):
        """Тест что декоратор не ловит другие исключения."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def mock_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Some other error")
        
        with pytest.raises(ValueError):
            await mock_func()
        
        # Должна быть только одна попытка, т.к. ValueError не в списке retry exceptions
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_custom_exceptions(self):
        """Тест retry с кастомными исключениями."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Custom error")
            return "success"
        
        result = await mock_func()
        
        assert result == "success"
        assert call_count == 2


class TestOpenDotaServiceRetry:
    """Тесты retry логики в OpenDotaService."""
    
    @pytest.mark.asyncio
    async def test_fetch_success_on_first_attempt(self):
        """Тест успешного запроса с первой попытки."""
        service = OpenDotaService()
        
        # Мокаем сессию
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        service._session = mock_session
        
        result = await service._fetch("/test")
        
        assert result == {"data": "test"}
        assert service.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_fetch_retry_on_network_error(self):
        """Тест retry при network error."""
        service = OpenDotaService()
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count < 2:
                raise aiohttp.ClientError("Network error")
            
            # Успех на второй попытке
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": "success"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            return mock_response
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        service._session = mock_session
        
        # Мокаем rate limiter
        service._check_rate_limit = AsyncMock()
        
        result = await service._fetch("/test")
        
        assert result == {"data": "success"}
        assert call_count == 2
        assert service.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_fetch_all_retries_fail_graceful_degradation(self):
        """Тест graceful degradation при провале всех попыток."""
        service = OpenDotaService()
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise aiohttp.ClientError("Network error")
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        service._session = mock_session
        
        # Мокаем rate limiter
        service._check_rate_limit = AsyncMock()
        
        result = await service._fetch("/test")
        
        # Должен вернуть None вместо падения
        assert result is None
        assert call_count == 3  # 3 попытки
        assert service.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_fetch_timeout_error_retry(self):
        """Тест retry при timeout error."""
        service = OpenDotaService()
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                raise asyncio.TimeoutError()
            
            # Успех на третьей попытке
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": "success"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            return mock_response
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        service._session = mock_session
        
        # Мокаем rate limiter
        service._check_rate_limit = AsyncMock()
        
        result = await service._fetch("/test")
        
        assert result == {"data": "success"}
        assert call_count == 3
        assert service.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_fetch_invalid_endpoint_no_retry(self):
        """Тест что невалидный endpoint не вызывает retry."""
        service = OpenDotaService()
        
        # Мокаем сессию (не должна быть вызвана)
        mock_session = AsyncMock()
        service._session = mock_session
        
        result = await service._fetch("invalid")  # Без начального /
        
        assert result is None
        assert service.failed_requests == 0
        # Сессия не должна быть вызвана
        mock_session.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_fetch_404_no_retry(self):
        """Тест что 404 не вызывает retry."""
        service = OpenDotaService()
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            return mock_response
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        service._session = mock_session
        
        # Мокаем rate limiter
        service._check_rate_limit = AsyncMock()
        
        result = await service._fetch("/test")
        
        assert result is None
        assert call_count == 1  # Только одна попытка
        assert service.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_fetch_unexpected_exception_graceful_degradation(self):
        """Тест graceful degradation при неожиданном исключении."""
        service = OpenDotaService()
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Unexpected error")
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        service._session = mock_session
        
        # Мокаем rate limiter
        service._check_rate_limit = AsyncMock()
        
        result = await service._fetch("/test")
        
        # Должен вернуть None вместо падения
        assert result is None
        assert call_count == 1  # Неожиданные исключения не retry
        assert service.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_failed_requests_counter_increments(self):
        """Тест что счетчик failed_requests увеличивается."""
        service = OpenDotaService()
        
        async def mock_get(*args, **kwargs):
            raise aiohttp.ClientError("Network error")
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        service._session = mock_session
        
        # Мокаем rate limiter
        service._check_rate_limit = AsyncMock()
        
        # Первый провал
        await service._fetch("/test1")
        assert service.failed_requests == 1
        
        # Второй провал
        await service._fetch("/test2")
        assert service.failed_requests == 2
        
        # Третий провал
        await service._fetch("/test3")
        assert service.failed_requests == 3
    
    @pytest.mark.asyncio
    async def test_fetch_respects_rate_limit(self):
        """Тест что retry логика учитывает rate limit."""
        service = OpenDotaService()
        
        rate_limit_calls = 0
        
        async def mock_rate_limit():
            nonlocal rate_limit_calls
            rate_limit_calls += 1
        
        service._check_rate_limit = mock_rate_limit
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count < 2:
                raise aiohttp.ClientError("Network error")
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": "success"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            return mock_response
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        service._session = mock_session
        
        await service._fetch("/test")
        
        # Rate limit должен быть проверен перед каждой попыткой
        assert rate_limit_calls == 2
        assert call_count == 2
