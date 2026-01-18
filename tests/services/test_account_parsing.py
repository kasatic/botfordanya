"""
Тесты для парсинга Steam аккаунтов в OpenDota сервисе.
Проверяет все поддерживаемые форматы и edge cases.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.opendota_service import OpenDotaService


class TestAccountIdParsing:
    """Тесты для parse_account_id() - основной метод парсинга."""
    
    @pytest.mark.asyncio
    async def test_parse_account_id_direct(self):
        """Тест парсинга прямого Account ID."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("123456789")
        
        assert result == 123456789
    
    @pytest.mark.asyncio
    async def test_parse_account_id_with_spaces(self):
        """Тест парсинга Account ID с пробелами."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("  123456789  ")
        
        assert result == 123456789
    
    @pytest.mark.asyncio
    async def test_parse_steam_id64(self):
        """Тест парсинга Steam ID 64."""
        service = OpenDotaService()
        steam_id64 = "76561198012345678"
        expected = OpenDotaService.steam_id64_to_account_id(76561198012345678)
        
        result = await service.parse_account_id(steam_id64)
        
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_parse_dotabuff_url(self):
        """Тест парсинга Dotabuff URL."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("https://www.dotabuff.com/players/123456789")
        
        assert result == 123456789
    
    @pytest.mark.asyncio
    async def test_parse_opendota_url(self):
        """Тест парсинга OpenDota URL."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("https://www.opendota.com/players/123456789")
        
        assert result == 123456789
    
    @pytest.mark.asyncio
    async def test_parse_steam_profiles_url(self):
        """Тест парсинга Steam profiles URL."""
        service = OpenDotaService()
        steam_id64 = 76561198012345678
        expected = OpenDotaService.steam_id64_to_account_id(steam_id64)
        
        result = await service.parse_account_id(f"https://steamcommunity.com/profiles/{steam_id64}")
        
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_parse_steam_vanity_url_success(self):
        """Тест парсинга Steam vanity URL с успешным резолвом."""
        service = OpenDotaService()
        
        # Мокаем _resolve_vanity_url
        with patch.object(service, '_resolve_vanity_url', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = 123456789
            
            result = await service.parse_account_id("https://steamcommunity.com/id/customname")
            
            assert result == 123456789
            mock_resolve.assert_called_once_with("customname")
    
    @pytest.mark.asyncio
    async def test_parse_steam_vanity_url_failure(self):
        """Тест парсинга Steam vanity URL с неудачным резолвом."""
        service = OpenDotaService()
        
        # Мокаем _resolve_vanity_url
        with patch.object(service, '_resolve_vanity_url', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = None
            
            result = await service.parse_account_id("https://steamcommunity.com/id/nonexistent")
            
            assert result is None
            mock_resolve.assert_called_once_with("nonexistent")
    
    @pytest.mark.asyncio
    async def test_parse_empty_string(self):
        """Тест парсинга пустой строки."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_none(self):
        """Тест парсинга None."""
        service = OpenDotaService()
        
        result = await service.parse_account_id(None)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_invalid_url(self):
        """Тест парсинга невалидного URL."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("https://example.com/invalid")
        
        # Должен вернуть None или попытаться извлечь число
        assert result is None or isinstance(result, int)


class TestVanityUrlResolution:
    """Тесты для _resolve_vanity_url() - резолв кастомных Steam URL."""
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_exact_match(self):
        """Тест резолва с точным совпадением имени."""
        service = OpenDotaService()
        
        # Мокаем _fetch
        mock_data = [
            {"account_id": 123456789, "personaname": "CustomName"},
            {"account_id": 987654321, "personaname": "OtherName"}
        ]
        
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_data
            
            result = await service._resolve_vanity_url("CustomName")
            
            assert result == 123456789
            mock_fetch.assert_called_once_with("/search?q=CustomName")
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_case_insensitive(self):
        """Тест резолва без учёта регистра."""
        service = OpenDotaService()
        
        # Мокаем _fetch
        mock_data = [
            {"account_id": 123456789, "personaname": "CustomName"},
        ]
        
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_data
            
            result = await service._resolve_vanity_url("customname")
            
            assert result == 123456789
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_first_result(self):
        """Тест резолва берёт первый результат если нет точного совпадения."""
        service = OpenDotaService()
        
        # Мокаем _fetch
        mock_data = [
            {"account_id": 111111111, "personaname": "SimilarName1"},
            {"account_id": 222222222, "personaname": "SimilarName2"}
        ]
        
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_data
            
            result = await service._resolve_vanity_url("Similar")
            
            # Должен вернуть первый результат
            assert result == 111111111
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_empty_results(self):
        """Тест резолва с пустыми результатами."""
        service = OpenDotaService()
        
        # Мокаем _fetch
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            
            result = await service._resolve_vanity_url("nonexistent")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_api_failure(self):
        """Тест резолва при ошибке API."""
        service = OpenDotaService()
        
        # Мокаем _fetch
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            
            result = await service._resolve_vanity_url("anyname")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_empty_name(self):
        """Тест резолва с пустым именем."""
        service = OpenDotaService()
        
        result = await service._resolve_vanity_url("")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_none_name(self):
        """Тест резолва с None."""
        service = OpenDotaService()
        
        result = await service._resolve_vanity_url(None)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_resolve_vanity_url_exception_handling(self):
        """Тест обработки исключений при резолве."""
        service = OpenDotaService()
        
        # Мокаем _fetch чтобы выбросить исключение
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")
            
            result = await service._resolve_vanity_url("anyname")
            
            # Должен вернуть None и залогировать ошибку
            assert result is None


class TestRegexPatterns:
    """Тесты для регулярных выражений в parse_account_id_sync()."""
    
    def test_dotabuff_regex_variations(self):
        """Тест regex для различных вариаций Dotabuff URL."""
        test_cases = [
            ("https://dotabuff.com/players/123456789", 123456789),
            ("http://dotabuff.com/players/123456789", 123456789),
            ("https://www.dotabuff.com/players/123456789", 123456789),
            ("https://dotabuff.com/players/123456789/", 123456789),
            ("https://dotabuff.com/players/123456789/matches", 123456789),
            ("https://DOTABUFF.COM/PLAYERS/123456789", 123456789),
        ]
        
        for url, expected in test_cases:
            result = OpenDotaService.parse_account_id_sync(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_opendota_regex_variations(self):
        """Тест regex для различных вариаций OpenDota URL."""
        test_cases = [
            ("https://opendota.com/players/123456789", 123456789),
            ("http://opendota.com/players/123456789", 123456789),
            ("https://www.opendota.com/players/123456789", 123456789),
            ("https://opendota.com/players/123456789/", 123456789),
            ("https://opendota.com/players/123456789/overview", 123456789),
            ("https://OPENDOTA.COM/PLAYERS/123456789", 123456789),
        ]
        
        for url, expected in test_cases:
            result = OpenDotaService.parse_account_id_sync(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_steam_profiles_regex_variations(self):
        """Тест regex для различных вариаций Steam profiles URL."""
        steam_id64 = 76561198012345678
        expected = OpenDotaService.steam_id64_to_account_id(steam_id64)
        
        test_cases = [
            f"https://steamcommunity.com/profiles/{steam_id64}",
            f"http://steamcommunity.com/profiles/{steam_id64}",
            f"https://www.steamcommunity.com/profiles/{steam_id64}",
            f"https://steamcommunity.com/profiles/{steam_id64}/",
            f"https://steamcommunity.com/profiles/{steam_id64}/home",
            f"https://STEAMCOMMUNITY.COM/PROFILES/{steam_id64}",
        ]
        
        for url in test_cases:
            result = OpenDotaService.parse_account_id_sync(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_steam_vanity_regex_detection(self):
        """Тест regex для обнаружения Steam vanity URL."""
        test_cases = [
            "https://steamcommunity.com/id/customname",
            "http://steamcommunity.com/id/customname",
            "https://www.steamcommunity.com/id/customname",
            "https://steamcommunity.com/id/custom-name",
            "https://steamcommunity.com/id/custom_name",
            "https://steamcommunity.com/id/player123",
            "https://STEAMCOMMUNITY.COM/ID/CustomName",
        ]
        
        for url in test_cases:
            result = OpenDotaService.parse_account_id_sync(url)
            # Должен вернуть None, так как требуется async резолв
            assert result is None, f"Should return None for vanity URL: {url}"


class TestEdgeCases:
    """Тесты для граничных случаев и потенциальных багов."""
    
    @pytest.mark.asyncio
    async def test_very_long_account_id(self):
        """Тест парсинга очень длинного числа."""
        service = OpenDotaService()
        
        # Число длиннее 17 цифр
        result = await service.parse_account_id("123456789012345678901")
        
        # Должен обработать корректно или вернуть None
        assert result is None or isinstance(result, int)
    
    @pytest.mark.asyncio
    async def test_account_id_with_leading_zeros(self):
        """Тест парсинга Account ID с ведущими нулями."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("00123456789")
        
        # Должен убрать ведущие нули
        assert result == 123456789
    
    @pytest.mark.asyncio
    async def test_mixed_url_formats(self):
        """Тест парсинга URL со смешанными форматами."""
        service = OpenDotaService()
        
        # URL с query параметрами
        result = await service.parse_account_id("https://dotabuff.com/players/123456789?tab=matches")
        
        assert result == 123456789
    
    @pytest.mark.asyncio
    async def test_url_with_fragment(self):
        """Тест парсинга URL с фрагментом."""
        service = OpenDotaService()
        
        result = await service.parse_account_id("https://opendota.com/players/123456789#overview")
        
        assert result == 123456789
    
    def test_steam_id64_boundary_values(self):
        """Тест конвертации граничных значений Steam ID 64."""
        # Минимальный Steam ID 64
        min_steam_id = 76561197960265728
        assert OpenDotaService.steam_id64_to_account_id(min_steam_id) == 0
        
        # Максимальный реалистичный Steam ID 64
        max_steam_id = 76561199999999999
        result = OpenDotaService.steam_id64_to_account_id(max_steam_id)
        assert result > 0
    
    @pytest.mark.asyncio
    async def test_unicode_in_vanity_url(self):
        """Тест парсинга vanity URL с unicode символами."""
        service = OpenDotaService()
        
        with patch.object(service, '_resolve_vanity_url', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = None
            
            result = await service.parse_account_id("https://steamcommunity.com/id/имя")
            
            # Должен попытаться резолвить
            assert result is None
    
    @pytest.mark.asyncio
    async def test_special_characters_in_vanity(self):
        """Тест парсинга vanity URL со специальными символами."""
        service = OpenDotaService()
        
        with patch.object(service, '_resolve_vanity_url', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = 123456789
            
            result = await service.parse_account_id("https://steamcommunity.com/id/player-name_123")
            
            assert result == 123456789
            mock_resolve.assert_called_once_with("player-name_123")


class TestSteamId64Conversion:
    """Тесты для конвертации Steam ID 64 в Account ID."""
    
    def test_conversion_formula(self):
        """Тест формулы конвертации."""
        # Steam ID 64 = Account ID + 76561197960265728
        account_id = 123456789
        steam_id64 = account_id + 76561197960265728
        
        result = OpenDotaService.steam_id64_to_account_id(steam_id64)
        
        assert result == account_id
    
    def test_conversion_known_values(self):
        """Тест конвертации известных значений."""
        test_cases = [
            (76561197960265728, 0),
            (76561198012345678, 52079950),
            (76561199000000000, 1039734272),
        ]
        
        for steam_id64, expected_account_id in test_cases:
            result = OpenDotaService.steam_id64_to_account_id(steam_id64)
            assert result == expected_account_id


class TestIntegration:
    """Интеграционные тесты для полного flow парсинга."""
    
    @pytest.mark.asyncio
    async def test_full_flow_with_vanity_url(self):
        """Тест полного flow с vanity URL."""
        service = OpenDotaService()
        
        # Мокаем _fetch для резолва
        mock_search_data = [
            {"account_id": 123456789, "personaname": "TestPlayer"}
        ]
        
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_search_data
            
            result = await service.parse_account_id("https://steamcommunity.com/id/TestPlayer")
            
            assert result == 123456789
            mock_fetch.assert_called_once_with("/search?q=TestPlayer")
    
    @pytest.mark.asyncio
    async def test_fallback_to_sync_parsing(self):
        """Тест fallback на синхронный парсинг."""
        service = OpenDotaService()
        
        # Не должен вызывать API для прямых ID
        with patch.object(service, '_fetch', new_callable=AsyncMock) as mock_fetch:
            result = await service.parse_account_id("123456789")
            
            assert result == 123456789
            # API не должен вызываться
            mock_fetch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_multiple_formats_same_account(self):
        """Тест что разные форматы дают один Account ID."""
        service = OpenDotaService()
        account_id = 123456789
        steam_id64 = account_id + 76561197960265728
        
        formats = [
            str(account_id),
            str(steam_id64),
            f"https://dotabuff.com/players/{account_id}",
            f"https://opendota.com/players/{account_id}",
            f"https://steamcommunity.com/profiles/{steam_id64}",
        ]
        
        results = []
        for fmt in formats:
            result = await service.parse_account_id(fmt)
            results.append(result)
        
        # Все должны дать один и тот же Account ID
        assert all(r == account_id for r in results), f"Results differ: {results}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
