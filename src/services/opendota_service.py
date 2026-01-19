"""
Сервис для работы с OpenDota API.
"""

import asyncio
import logging
import traceback
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

import aiohttp

logger = logging.getLogger(__name__)

T = TypeVar("T")

OPENDOTA_API = "https://api.opendota.com/api"


def retry_with_backoff(
    max_retries: int = 3, base_delay: float = 1.0, exceptions: tuple = (aiohttp.ClientError, asyncio.TimeoutError)
):
    """
    Декоратор для retry логики с exponential backoff.

    Args:
        max_retries: Максимальное количество попыток (по умолчанию 3)
        base_delay: Базовая задержка в секундах (по умолчанию 1.0)
        exceptions: Кортеж исключений для retry (по умолчанию NetworkError и TimeoutError)

    Exponential backoff: 1s, 2s, 4s, 8s...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        # Вычисляем задержку: base_delay * 2^attempt
                        delay = base_delay * (2**attempt)

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay}s..."
                        )

                        await asyncio.sleep(delay)
                    else:
                        # Последняя попытка провалилась
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}: {e}\n"
                            f"Traceback:\n{traceback.format_exc()}"
                        )

            # Если все попытки провалились, пробрасываем исключение
            raise last_exception

        return wrapper

    return decorator


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
        0: "Unknown",
        1: "All Pick",
        2: "Captain's Mode",
        3: "Random Draft",
        4: "Single Draft",
        5: "All Random",
        22: "Ranked All Pick",
        23: "Turbo",
    }

    HEROES: Dict[int, str] = {}  # Загрузится при первом запросе

    def __init__(self, steam_api_key: Optional[str] = None):
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._rate_limiter: deque = deque(maxlen=60)  # 60 запросов в минуту
        self._rate_lock = asyncio.Lock()
        self.failed_requests: int = 0  # Счетчик проваленных запросов
        self._steam_api_key = steam_api_key  # Для резолва vanity URL

    async def init(self) -> None:
        """Инициализирует HTTP сессию заранее."""
        async with self._session_lock:
            if self._session is None:
                timeout = aiohttp.ClientTimeout(total=30)
                self._session = aiohttp.ClientSession(timeout=timeout)
                logger.info("OpenDota HTTP session initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает HTTP сессию (создает если нужно)."""
        async with self._session_lock:
            if self._session is None:
                timeout = aiohttp.ClientTimeout(total=30)
                self._session = aiohttp.ClientSession(timeout=timeout)
                logger.info("OpenDota HTTP session created")
            return self._session

    async def _check_rate_limit(self) -> None:
        """Проверяет и ждет если достигнут rate limit."""
        async with self._rate_lock:
            now = datetime.now()

            # Удаляем запросы старше 1 минуты
            while self._rate_limiter and (now - self._rate_limiter[0]).total_seconds() > 60:
                self._rate_limiter.popleft()

            # Если достигнут лимит - ждем
            if len(self._rate_limiter) >= 60:
                oldest = self._rate_limiter[0]
                wait_time = 60 - (now - oldest).total_seconds()
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)

            # Записываем текущий запрос
            self._rate_limiter.append(now)

    async def close(self) -> None:
        """Закрывает HTTP сессию."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("OpenDota HTTP session closed")

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def _fetch_with_retry(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Внутренний метод для запроса с retry логикой.
        Пробрасывает исключения для обработки декоратором.
        """
        # Валидация endpoint
        if not endpoint.startswith("/"):
            logger.error("Invalid endpoint: must start with /")
            return None
        if ".." in endpoint or "//" in endpoint:
            logger.error("Invalid endpoint: contains suspicious patterns")
            return None

        # Проверяем rate limit ПЕРЕД запросом
        await self._check_rate_limit()

        session = await self._get_session()
        async with session.get(f"{OPENDOTA_API}{endpoint}") as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                return None
            else:
                logger.warning(f"OpenDota API error: {resp.status}")
                return None

    async def _fetch(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Делает запрос к API с retry логикой и graceful degradation.

        Retry стратегия:
        - До 3 попыток при NetworkError или TimeoutError
        - Exponential backoff: 1s, 2s, 4s
        - Graceful degradation: возвращает None при провале всех попыток
        """
        try:
            return await self._fetch_with_retry(endpoint)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # Все попытки провалились - graceful degradation
            logger.error(
                f"All retry attempts failed for endpoint {endpoint}: {e}\n" f"Traceback:\n{traceback.format_exc()}"
            )
            self.failed_requests += 1
            return None
        except Exception as e:
            # Неожиданные исключения логируем и возвращаем None
            logger.error(f"Unexpected error in OpenDota request: {e}\n{traceback.format_exc()}")
            self.failed_requests += 1
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
            mmr_estimate=data.get("mmr_estimate", {}).get("estimate"),
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
                        avg_mmr=match.get("average_mmr"),
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
            except Exception:
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

            players.append(
                {
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
                }
            )

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
        dotabuff_match = re.search(r"dotabuff\.com/players/(\d+)", input_str, re.IGNORECASE)
        if dotabuff_match:
            return int(dotabuff_match.group(1))

        # 2. Ссылки OpenDota: opendota.com/players/123456789
        opendota_match = re.search(r"opendota\.com/players/(\d+)", input_str, re.IGNORECASE)
        if opendota_match:
            return int(opendota_match.group(1))

        # 3. Steam Community с числовым ID: steamcommunity.com/profiles/76561198012345678
        steam_profiles_match = re.search(r"steamcommunity\.com/profiles/(\d+)", input_str, re.IGNORECASE)
        if steam_profiles_match:
            steam_id64 = int(steam_profiles_match.group(1))
            return OpenDotaService.steam_id64_to_account_id(steam_id64)

        # 4. Steam Community с кастомным URL: steamcommunity.com/id/customname
        # Возвращаем None — нужен асинхронный резолв
        steam_vanity_match = re.search(r"steamcommunity\.com/id/([a-zA-Z0-9_-]+)", input_str, re.IGNORECASE)
        if steam_vanity_match:
            return None  # Требуется async резолв

        # 5. Чистые числа
        try:
            # Убираем возможные пробелы и лишние символы
            clean = re.sub(r"[^\d]", "", input_str)

            if not clean:
                return None

            num = int(clean)

            # Steam ID 64 (17 цифр, начинается с 7656119...)
            if len(clean) == 17 and clean.startswith("7656119"):
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
        steam_vanity_match = re.search(r"steamcommunity\.com/id/([a-zA-Z0-9_-]+)", input_str, re.IGNORECASE)
        if steam_vanity_match:
            vanity_name = steam_vanity_match.group(1)
            return await self._resolve_vanity_url(vanity_name)

        return None

    async def _resolve_vanity_url(self, vanity_name: str) -> Optional[int]:
        """
        Резолвит кастомный Steam URL через Steam Web API или OpenDota.

        Приоритет:
        1. Steam Web API (точный резолв) - если есть ключ
        2. OpenDota поиск (приблизительный) - fallback
        """
        if not vanity_name:
            return None

        # Способ 1: Steam Web API (ТОЧНЫЙ резолв vanity URL)
        if self._steam_api_key:
            try:
                logger.info(f"Resolving vanity URL via Steam API: {vanity_name}")

                session = await self._get_session()
                url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
                params = {"key": self._steam_api_key, "vanityurl": vanity_name}

                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response = data.get("response", {})

                        if response.get("success") == 1:
                            steam_id64 = int(response.get("steamid"))
                            account_id = self.steam_id64_to_account_id(steam_id64)
                            logger.info(f"✅ Resolved via Steam API: {vanity_name} -> {account_id}")
                            return account_id
                        else:
                            logger.warning(f"Steam API: vanity URL not found: {vanity_name}")
                    else:
                        logger.warning(f"Steam API error: {resp.status}")
            except Exception as e:
                logger.warning(f"Failed to resolve via Steam API: {e}")
        else:
            logger.warning("Steam API key not configured, falling back to OpenDota search")

        # Способ 2: OpenDota поиск (ПРИБЛИЗИТЕЛЬНЫЙ - ищет по имени профиля)
        try:
            logger.info(f"Resolving via OpenDota search: {vanity_name}")

            data = await self._fetch(f"/search?q={vanity_name}")
            if data and len(data) > 0:
                # Ищем точное совпадение имени (case-insensitive)
                for player in data:
                    persona = player.get("personaname", "").lower()
                    if persona == vanity_name.lower():
                        account_id = player.get("account_id")
                        logger.info(f"✅ Exact match via OpenDota: {vanity_name} -> {account_id}")
                        return account_id

                # Если точного нет - берём первый результат
                first = data[0]
                account_id = first.get("account_id")
                persona = first.get("personaname")
                logger.warning(
                    f"⚠️ No exact match for '{vanity_name}', using first result: " f"{persona} -> {account_id}"
                )
                return account_id
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
