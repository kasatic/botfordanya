"""
Тесты для OpenDota сервиса.
"""
import pytest

# NOTE: Если тесты не запускаются из-за ошибки в src/config.py,
# нужно исправить конфликт __slots__ с default values в dataclass.
# Для Python 3.10+ используйте slots=True в декораторе @dataclass.
from src.services.opendota_service import OpenDotaService, PlayerProfile, LiveGame


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
