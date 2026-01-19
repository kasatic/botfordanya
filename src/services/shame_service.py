"""
Сервис для отслеживания матчей и shame уведомлений.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from telegram.ext import Application

from src.database.steam_repository import SteamLinkRepository
from src.services.opendota_service import OpenDotaService

logger = logging.getLogger(__name__)


@dataclass
class ShameResult:
    """Результат анализа матча."""

    match_id: int
    loser_account_id: int
    loser_hero: str
    loser_kda: str
    loser_damage: int
    loser_gpm: int
    duration: int
    win: bool
    all_players_stats: List[Dict]


class ShameService:
    """Сервис для shame уведомлений после матчей."""

    SHAME_TITLES = [
        "🤡 СЫН ШЛЮХИ МАТЧА",
        "💩 ПОЗОР КОМАНДЫ",
        "🦥 ЛЕНИВЕЦ ИГРЫ",
        "🗑 МУСОРКА МАТЧА",
        "🤢 ДНИЩЕ ДНЯ",
        "🐌 СЛОУПОК КАТКИ",
        "🧻 ТУАЛЕТНАЯ БУМАГА",
        "🪨 КАМЕНЬ В ОГОРОД",
    ]

    SHAME_PHRASES = [
        "тащил команду... на дно",
        "играл как будто первый раз мышку увидел",
        "вносил огромный вклад в победу врага",
        "был главным спонсором вражеской команды",
        "думал что это симулятор ходьбы",
        "косплеил крипа весь матч",
        "искал смысл жизни вместо врагов",
        "тренировал респавн",
    ]

    def __init__(self, opendota: OpenDotaService, steam_repo: SteamLinkRepository, application: Application):
        self.opendota = opendota
        self.steam_repo = steam_repo
        self.application = application
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Запускает фоновую проверку матчей."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info("🔔 Shame service started")

    async def stop(self) -> None:
        """Останавливает сервис."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Закрываем OpenDota сессию при остановке
        if self.opendota:
            await self.opendota.close()

        logger.info("🔕 Shame service stopped")

    async def _check_loop(self) -> None:
        """Основной цикл проверки матчей."""
        while self._running:
            try:
                await self._check_all_subscribers()
            except Exception as e:
                logger.error(f"Shame check error: {e}")

            # Проверяем каждые 2 минуты
            await asyncio.sleep(120)

    async def _check_all_subscribers(self) -> None:
        """Проверяет всех подписчиков на новые матчи."""
        chats = await self.steam_repo.get_all_shame_chats()

        for chat_id in chats:
            await self._check_chat_subscribers(chat_id)

    async def _check_chat_subscribers(self, chat_id: int) -> None:
        """Проверяет подписчиков конкретного чата."""
        subscribers = await self.steam_repo.get_shame_subscribers(chat_id)

        if not subscribers:
            return

        # Группируем по матчам — если несколько друзей в одном матче
        match_players: Dict[int, List[tuple]] = {}

        for user_id, account_id, last_match_id in subscribers:
            try:
                # Получаем ID последнего матча из OpenDota API
                current_match = await self.opendota.get_recent_match_id(account_id)

                if not current_match:
                    continue

                # Проверяем по БД, а не по кэшу - БД является единственным источником истины
                if current_match == last_match_id:
                    logger.debug(f"Match {current_match} already processed for user {user_id}")
                    continue

                # Группируем игроков по матчам
                if current_match not in match_players:
                    match_players[current_match] = []

                match_players[current_match].append((user_id, account_id))

            except Exception as e:
                logger.error(f"Error checking user {user_id}: {e}")

        # Обрабатываем каждый новый матч
        for match_id, players in match_players.items():
            await self._process_match(chat_id, match_id, players)

    async def _process_match(self, chat_id: int, match_id: int, players: List[tuple]) -> None:
        """Обрабатывает завершённый матч."""
        match_data = await self.opendota.get_match_players(match_id)

        if not match_data:
            return

        # Находим наших игроков в матче
        our_account_ids = {acc_id for _, acc_id in players}
        our_players = [p for p in match_data["players"] if p["account_id"] in our_account_ids]

        if not our_players:
            return

        # Находим самого бесполезного среди наших
        worst = min(our_players, key=lambda p: p["usefulness"])

        # Находим telegram user_id для худшего игрока
        worst_user_id = None
        for user_id, account_id in players:
            if account_id == worst["account_id"]:
                worst_user_id = user_id
                break

        if not worst_user_id:
            return

        # Обновляем last_match_id в БД для всех участников
        for user_id, _ in players:
            await self.steam_repo.update_last_match(user_id, chat_id, match_id)

        # Отправляем shame сообщение
        await self._send_shame(chat_id, worst_user_id, worst, match_data)

    async def _send_shame(self, chat_id: int, user_id: int, player: Dict, match_data: Dict) -> None:
        """Отправляет shame сообщение в чат."""
        title = random.choice(self.SHAME_TITLES)
        phrase = random.choice(self.SHAME_PHRASES)

        kda = f"{player['kills']}/{player['deaths']}/{player['assists']}"
        result = "победе" if player["win"] else "поражении"

        # Форматируем урон
        def fmt(n):
            if n >= 1000:
                return f"{n / 1000:.1f}k"
            return str(n)

        text = (
            f"{title}\n\n"
            f"[👤](tg://user?id={user_id}) {phrase}\n\n"
            f"🦸 {player['hero']}\n"
            f"⚔️ KDA: *{kda}*\n"
            f"🗡 Урон: *{fmt(player['hero_damage'])}*\n"
            f"💰 GPM: *{player['gpm']}*\n\n"
            f"⏱ {match_data['duration']} мин • При {result}\n\n"
            f"🔗 [Матч](https://www.opendota.com/matches/{match_data['match_id']})"
        )

        try:
            await self.application.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            logger.info(f"Shame sent to chat {chat_id} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send shame: {e}")
