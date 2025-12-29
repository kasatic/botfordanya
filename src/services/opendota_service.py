"""
Сервис для работы с OpenDota API.
"""
import logging
import aiohttp
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OPENDOTA_API = "https://api.opendota.com/api"


@dataclass
class LiveGame:
    """Информация о текущей игре."""
    match_id: int
    game_time: int  # секунды
    game_mode: str
    player_hero: str
    player_team: str  # radiant/dire
    avg_mmr: Optional[int] = None
    
    @property
    def minutes(self) -> int:
        return self.game_time // 60
    
    @property
    def seconds(self) -> int:
        return self.game_time % 60
    
    @property
    def time_str(self) -> str:
        return f"{self.minutes}:{self.seconds:02d}"


@dataclass 
class PlayerProfile:
    """Профиль игрока."""
    account_id: int
    persona_name: str
    avatar: str
    rank_tier: Optional[int] = None
    mmr_estimate: Optional[int] = None
    
    @property
    def rank_name(self) -> str:
        """Конвертирует rank_tier в название."""
        if not self.rank_tier:
            return "Unranked"
        
        medals = ["", "Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal"]
        tier = self.rank_tier // 10
        stars = self.rank_tier % 10
        
        if tier < len(medals):
            return f"{medals[tier]} {stars}" if stars else medals[tier]
        return "Immortal"


class OpenDotaService:
    """Сервис для OpenDota API."""
    
    GAME_MODES = {
        0: "Unknown", 1: "All Pick", 2: "Captain's Mode", 3: "Random Draft",
        4: "Single Draft", 5: "All Random", 22: "Ranked All Pick", 23: "Turbo"
    }
    
    HEROES: Dict[int, str] = {}  # Загрузится при первом запросе
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _fetch(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Делает запрос к API."""
        try:
            session = await self._get_session()
            async with session.get(f"{OPENDOTA_API}{endpoint}") as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return None
                else:
                    logger.warning(f"OpenDota API error: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"OpenDota request failed: {e}")
            return None
    
    async def _load_heroes(self) -> None:
        """Загружает список героев."""
        if self.HEROES:
            return
        
        data = await self._fetch("/heroes")
        if data:
            self.HEROES = {h["id"]: h["localized_name"] for h in data}
    
    def _get_hero_name(self, hero_id: int) -> str:
        return self.HEROES.get(hero_id, f"Hero {hero_id}")
    
    async def get_profile(self, account_id: int) -> Optional[PlayerProfile]:
        """Получает профиль игрока."""
        data = await self._fetch(f"/players/{account_id}")
        if not data or "profile" not in data:
            return None
        
        profile = data["profile"]
        return PlayerProfile(
            account_id=account_id,
            persona_name=profile.get("personaname", "Unknown"),
            avatar=profile.get("avatarfull", ""),
            rank_tier=data.get("rank_tier"),
            mmr_estimate=data.get("mmr_estimate", {}).get("estimate")
        )
    
    async def get_live_game(self, account_id: int) -> Optional[LiveGame]:
        """Проверяет, в игре ли игрок сейчас."""
        await self._load_heroes()
        
        # Сначала пробуем через /players/{id}/recentMatches — не даст live
        # Нужен другой подход — через real-time данные
        
        # OpenDota не даёт прямой live статус, но можно через:
        # 1. Steam API (нужен ключ)
        # 2. Stratz API 
        # 3. Парсинг через /live
        
        # Попробуем через /live — там все текущие матчи
        data = await self._fetch("/live")
        if not data:
            return None
        
        # Ищем игрока в live матчах
        for match in data:
            players = match.get("players", [])
            for player in players:
                if player.get("account_id") == account_id:
                    hero_id = player.get("hero_id", 0)
                    team = "Radiant" if player.get("team") == 0 else "Dire"
                    
                    return LiveGame(
                        match_id=match.get("match_id", 0),
                        game_time=match.get("game_time", 0),
                        game_mode=self.GAME_MODES.get(match.get("game_mode", 0), "Unknown"),
                        player_hero=self._get_hero_name(hero_id),
                        player_team=team,
                        avg_mmr=match.get("average_mmr")
                    )
        
        return None
    
    async def get_last_match(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Получает последний матч игрока (базовая инфа)."""
        await self._load_heroes()
        
        data = await self._fetch(f"/players/{account_id}/recentMatches")
        if not data or len(data) == 0:
            return None
        
        match = data[0]
        hero_id = match.get("hero_id", 0)
        
        return {
            "match_id": match.get("match_id"),
            "hero": self._get_hero_name(hero_id),
            "kills": match.get("kills", 0),
            "deaths": match.get("deaths", 0),
            "assists": match.get("assists", 0),
            "win": (match.get("player_slot", 0) < 128) == match.get("radiant_win", False),
            "duration": match.get("duration", 0) // 60,
            "game_mode": self.GAME_MODES.get(match.get("game_mode", 0), "Unknown"),
        }
    
    async def get_match_details(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Получает детальную стату последнего матча."""
        await self._load_heroes()
        
        # Сначала получаем ID последнего матча
        recent = await self._fetch(f"/players/{account_id}/recentMatches")
        if not recent or len(recent) == 0:
            return None
        
        match_id = recent[0].get("match_id")
        
        # Теперь полные данные матча
        match = await self._fetch(f"/matches/{match_id}")
        if not match:
            return None
        
        # Ищем нашего игрока
        player = None
        for p in match.get("players", []):
            if p.get("account_id") == account_id:
                player = p
                break
        
        if not player:
            return None
        
        hero_id = player.get("hero_id", 0)
        is_radiant = player.get("player_slot", 0) < 128
        win = is_radiant == match.get("radiant_win", False)
        
        # Собираем всех игроков для сравнения
        all_players = match.get("players", [])
        team_players = [p for p in all_players if (p.get("player_slot", 0) < 128) == is_radiant]
        
        # Считаем ранги в команде
        team_hero_dmg = sorted([p.get("hero_damage", 0) for p in team_players], reverse=True)
        team_tower_dmg = sorted([p.get("tower_damage", 0) for p in team_players], reverse=True)
        team_gpm = sorted([p.get("gold_per_min", 0) for p in team_players], reverse=True)
        
        player_hero_dmg = player.get("hero_damage", 0)
        player_tower_dmg = player.get("tower_damage", 0)
        player_gpm = player.get("gold_per_min", 0)
        
        def get_rank(value, sorted_list):
            try:
                return sorted_list.index(value) + 1
            except:
                return 5
        
        return {
            "match_id": match_id,
            "hero": self._get_hero_name(hero_id),
            "win": win,
            "duration": match.get("duration", 0) // 60,
            "kills": player.get("kills", 0),
            "deaths": player.get("deaths", 0),
            "assists": player.get("assists", 0),
            "gpm": player_gpm,
            "xpm": player.get("xp_per_min", 0),
            "hero_damage": player_hero_dmg,
            "tower_damage": player_tower_dmg,
            "last_hits": player.get("last_hits", 0),
            "denies": player.get("denies", 0),
            # Ранги в команде (1 = лучший)
            "hero_dmg_rank": get_rank(player_hero_dmg, team_hero_dmg),
            "tower_dmg_rank": get_rank(player_tower_dmg, team_tower_dmg),
            "gpm_rank": get_rank(player_gpm, team_gpm),
            # Доп инфа
            "net_worth": player.get("net_worth", 0),
            "camps_stacked": player.get("camps_stacked", 0),
            "obs_placed": player.get("obs_placed", 0),
            "roshans": player.get("roshans_killed", 0),
        }
    
    async def get_wordcloud(self, account_id: int) -> Optional[Dict[str, int]]:
        """Получает wordcloud игрока (что пишет в чат)."""
        data = await self._fetch(f"/players/{account_id}/wordcloud")
        if not data:
            return None
        
        # API возвращает {"my_word_counts": {...}, "all_word_counts": {...}}
        words = data.get("my_word_counts", {})
        return words if words else None
    
    async def get_recent_match_id(self, account_id: int) -> Optional[int]:
        """Получает ID последнего матча."""
        data = await self._fetch(f"/players/{account_id}/recentMatches")
        if not data or len(data) == 0:
            return None
        return data[0].get("match_id")
    
    async def get_match_players(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Получает данные всех игроков матча для анализа."""
        await self._load_heroes()
        
        match = await self._fetch(f"/matches/{match_id}")
        if not match:
            return None
        
        players = []
        for p in match.get("players", []):
            is_radiant = p.get("player_slot", 0) < 128
            win = is_radiant == match.get("radiant_win", False)
            
            # Считаем "полезность" — комбинация метрик
            kills = p.get("kills", 0)
            deaths = p.get("deaths", 0)
            assists = p.get("assists", 0)
            hero_damage = p.get("hero_damage", 0)
            tower_damage = p.get("tower_damage", 0)
            gpm = p.get("gold_per_min", 0)
            
            # Формула бесполезности: много смертей, мало урона, мало участия
            # Чем выше score — тем бесполезнее
            kda = (kills + assists) / max(deaths, 1)
            usefulness = (hero_damage / 1000) + (tower_damage / 500) + (kda * 10) + (gpm / 50)
            
            players.append({
                "account_id": p.get("account_id"),
                "hero": self._get_hero_name(p.get("hero_id", 0)),
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "hero_damage": hero_damage,
                "tower_damage": tower_damage,
                "gpm": gpm,
                "win": win,
                "team": "radiant" if is_radiant else "dire",
                "usefulness": usefulness,
            })
        
        return {
            "match_id": match_id,
            "duration": match.get("duration", 0) // 60,
            "radiant_win": match.get("radiant_win", False),
            "players": players,
        }
    
    @staticmethod
    def steam_id64_to_account_id(steam_id64: int) -> int:
        """Конвертирует Steam ID 64 в Account ID 32."""
        return steam_id64 - 76561197960265728
    
    @staticmethod
    def steam_id_to_account_id(steam_id: str) -> Optional[int]:
        """
        Конвертирует Steam ID в Account ID для Dota.
        Deprecated: используй parse_account_id() для поддержки ссылок.
        """
        return OpenDotaService.parse_account_id_sync(steam_id)
    
    @staticmethod
    def parse_account_id_sync(input_str: str) -> Optional[int]:
        """
        Синхронный парсер ID (без резолва кастомных URL).
        Поддерживает:
        - Account ID (9-10 цифр)
        - Steam ID 64 (17 цифр)
        - Ссылки Dotabuff/OpenDota
        - Ссылки Steam Community с числовым ID
        """
        import re
        
        if not input_str:
            return None
        
        input_str = input_str.strip()
        
        # 1. Ссылки Dotabuff: dotabuff.com/players/123456789
        dotabuff_match = re.search(r'dotabuff\.com/players/(\d+)', input_str, re.IGNORECASE)
        if dotabuff_match:
            return int(dotabuff_match.group(1))
        
        # 2. Ссылки OpenDota: opendota.com/players/123456789
        opendota_match = re.search(r'opendota\.com/players/(\d+)', input_str, re.IGNORECASE)
        if opendota_match:
            return int(opendota_match.group(1))
        
        # 3. Steam Community с числовым ID: steamcommunity.com/profiles/76561198012345678
        steam_profiles_match = re.search(r'steamcommunity\.com/profiles/(\d+)', input_str, re.IGNORECASE)
        if steam_profiles_match:
            steam_id64 = int(steam_profiles_match.group(1))
            return OpenDotaService.steam_id64_to_account_id(steam_id64)
        
        # 4. Steam Community с кастомным URL: steamcommunity.com/id/customname
        # Возвращаем None — нужен асинхронный резолв
        steam_vanity_match = re.search(r'steamcommunity\.com/id/([a-zA-Z0-9_-]+)', input_str, re.IGNORECASE)
        if steam_vanity_match:
            return None  # Требуется async резолв
        
        # 5. Чистые числа
        try:
            # Убираем возможные пробелы и лишние символы
            clean = re.sub(r'[^\d]', '', input_str)
            
            if not clean:
                return None
            
            num = int(clean)
            
            # Steam ID 64 (17 цифр, начинается с 7656119...)
            if len(clean) == 17 and clean.startswith('7656119'):
                return OpenDotaService.steam_id64_to_account_id(num)
            
            # Account ID (обычно 8-10 цифр, но может быть меньше)
            if len(clean) <= 10:
                return num
            
            # Если число слишком большое но не Steam ID 64 — пробуем как есть
            if num > 0:
                return num
            
            return None
        except (ValueError, TypeError):
            return None
    
    async def parse_account_id(self, input_str: str) -> Optional[int]:
        """
        Умный парсер Account ID из разных форматов.
        
        Поддерживает:
        - Account ID: 123456789 (9-10 цифр)
        - Steam ID 64: 76561198012345678 (17 цифр)
        - Dotabuff: https://www.dotabuff.com/players/123456789
        - OpenDota: https://www.opendota.com/players/123456789
        - Steam: https://steamcommunity.com/profiles/76561198012345678
        - Steam vanity: https://steamcommunity.com/id/customname (резолвится через API)
        
        Returns:
            Account ID или None если не удалось распарсить
        """
        import re
        
        if not input_str:
            return None
        
        input_str = input_str.strip()
        
        # Сначала пробуем синхронный парсинг
        result = self.parse_account_id_sync(input_str)
        if result is not None:
            return result
        
        # Проверяем кастомный Steam URL — нужен API резолв
        steam_vanity_match = re.search(r'steamcommunity\.com/id/([a-zA-Z0-9_-]+)', input_str, re.IGNORECASE)
        if steam_vanity_match:
            vanity_name = steam_vanity_match.group(1)
            return await self._resolve_vanity_url(vanity_name)
        
        return None
    
    async def _resolve_vanity_url(self, vanity_name: str) -> Optional[int]:
        """
        Резолвит кастомный Steam URL через OpenDota API.
        
        Пробует несколько способов:
        1. Поиск по имени через OpenDota
        2. Прямой запрос профиля (если vanity = account_id)
        """
        if not vanity_name:
            return None
        
        # Способ 1: Поиск через OpenDota API
        try:
            data = await self._fetch(f"/search?q={vanity_name}")
            if data and len(data) > 0:
                # Берём первый результат — обычно самый релевантный
                # Но лучше проверить точное совпадение имени
                for player in data:
                    # Проверяем точное совпадение (без учёта регистра)
                    persona = player.get("personaname", "").lower()
                    if persona == vanity_name.lower():
                        return player.get("account_id")
                
                # Если точного нет — берём первый
                return data[0].get("account_id")
        except Exception as e:
            logger.warning(f"Failed to resolve vanity URL '{vanity_name}': {e}")
        
        return None
    
    @staticmethod
    def get_supported_formats() -> str:
        """Возвращает описание поддерживаемых форматов для пользователя."""
        return (
            "📋 *Поддерживаемые форматы:*\n\n"
            "🔢 *Числовые ID:*\n"
            "• Account ID: `123456789`\n"
            "• Steam ID 64: `76561198012345678`\n\n"
            "🔗 *Ссылки:*\n"
            "• `dotabuff.com/players/123456789`\n"
            "• `opendota.com/players/123456789`\n"
            "• `steamcommunity.com/profiles/76561198...`\n"
            "• `steamcommunity.com/id/nickname`\n\n"
            "💡 Просто скопируй ссылку на профиль!"
        )
