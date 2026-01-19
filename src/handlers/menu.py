"""
Обработчики меню и навигации.
"""

import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.database import BanStatsRepository, ChatSettingsRepository, ViolationRepository, WhitelistRepository
from src.database.steam_repository import SteamLinkRepository
from src.services import AdminService, BanService
from src.services.opendota_service import OpenDotaService
from src.ui import Keyboards, Messages
from src.ui.messages import UserInfo

logger = logging.getLogger(__name__)


class MenuHandlers:
    """Обработчики меню."""

    def __init__(
        self,
        ban_service: BanService,
        admin_service: AdminService,
        whitelist_repo: WhitelistRepository,
        violation_repo: ViolationRepository,
        settings_repo: ChatSettingsRepository,
        stats_repo: BanStatsRepository,
        steam_repo: SteamLinkRepository = None,
        opendota: OpenDotaService = None,
    ):
        self.ban_service = ban_service
        self.admin_service = admin_service
        self.whitelist_repo = whitelist_repo
        self.violation_repo = violation_repo
        self.settings_repo = settings_repo
        self.stats_repo = stats_repo
        self.steam_repo = steam_repo
        self.opendota = opendota

    def _extract_owner_id(self, callback_data: str) -> int | None:
        """Извлекает owner_id из callback_data.

        Args:
            callback_data: строка вида "action_param_ownerid"

        Returns:
            owner_id если найден, иначе None
        """
        try:
            parts = callback_data.split("_")
            # Последняя часть должна быть числом (owner_id)
            if parts and parts[-1].isdigit():
                return int(parts[-1])
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════════════════
    # 🏠 ГЛАВНОЕ МЕНЮ
    # ═══════════════════════════════════════════════════════════

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /menu — главное меню."""
        user_id = update.effective_user.id

        await update.message.reply_text(
            Messages.welcome(), parse_mode="Markdown", reply_markup=Keyboards.main_menu(user_id)
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /start."""
        await self.menu_command(update, context)

    async def handle_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка навигации по меню."""
        query = update.callback_query
        await query.answer()

        data = query.data
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        # Извлекаем owner_id из callback_data
        owner_id = self._extract_owner_id(data)

        # Проверка владельца меню
        if owner_id and owner_id != user_id:
            await query.answer("❌ Это не твоё меню!", show_alert=True)
            return

        try:
            if data.startswith("menu_main"):
                await query.edit_message_text(
                    Messages.welcome(), parse_mode="Markdown", reply_markup=Keyboards.main_menu(user_id)
                )

            elif data.startswith("menu_stats"):
                await self._show_user_stats(query, context, user_id, chat_id)

            elif data.startswith("menu_top"):
                await self._show_top(query, context, chat_id, user_id)

            elif data.startswith("menu_chatstats"):
                await query.edit_message_text(
                    "📈 *Статистика чата*\n\nВыбери период:",
                    parse_mode="Markdown",
                    reply_markup=Keyboards.stats_period(user_id),
                )

            elif data.startswith("chatstats_"):
                parts = data.split("_")
                days = int(parts[1])
                await self._show_chat_stats(query, context, chat_id, days, user_id)

            elif data.startswith("menu_settings"):
                await self._show_settings(query, context, chat_id, user_id)

            elif data.startswith("menu_whitelist"):
                await self._show_whitelist(query, context, chat_id, user_id)

            elif data.startswith("whitelist_page_"):
                parts = data.split("_")
                page = int(parts[2])
                await self._show_whitelist(query, context, chat_id, user_id, page=page)

            elif data.startswith("menu_dota"):
                await self._show_dota_menu(query, context, user_id)

            elif data.startswith("menu_help"):
                await query.edit_message_text(
                    Messages.help_text(),
                    parse_mode="Markdown",
                    reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
                )

            elif data == "ignore":
                await query.answer("ℹ️ Это информационная кнопка", show_alert=False)

        except BadRequest as e:
            error_msg = str(e).lower()
            if "message is not modified" in error_msg:
                pass  # Игнорируем - сообщение уже в нужном состоянии
            elif "message to edit not found" in error_msg or "message can't be edited" in error_msg:
                # Сообщение было удалено или недоступно - отправляем новое
                try:
                    await query.message.reply_text(
                        Messages.welcome(), parse_mode="Markdown", reply_markup=Keyboards.main_menu(user_id)
                    )
                except Exception as send_error:
                    logger.error(f"Failed to send new message: {send_error}")
            else:
                logger.error(f"Menu callback error: {e}")

    # ═══════════════════════════════════════════════════════════
    # 📊 СТАТИСТИКА
    # ═══════════════════════════════════════════════════════════

    async def _show_user_stats(self, query, context, user_id: int, chat_id: int) -> None:
        """Показывает статистику пользователя."""
        violations, banned_until = await self.violation_repo.get_info(user_id, chat_id)
        is_banned = await self.ban_service.is_banned(user_id, chat_id)
        remaining = await self.ban_service.get_remaining_time(user_id, chat_id)
        is_whitelisted = await self.whitelist_repo.is_whitelisted(user_id, chat_id)

        user = UserInfo(user_id=user_id, name=query.from_user.first_name, username=query.from_user.username)

        await query.edit_message_text(
            Messages.user_stats(user, violations, is_banned, remaining, is_whitelisted),
            parse_mode="Markdown",
            reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
        )

    async def _show_top(self, query, context, chat_id: int, user_id: int) -> None:
        """Показывает топ нарушителей."""
        top_list = await self.violation_repo.get_top(chat_id, 10)

        # Получаем имена
        names = {}
        for uid, _ in top_list:
            try:
                member = await context.bot.get_chat_member(chat_id, uid)
                names[uid] = member.user.first_name
            except Exception:
                names[uid] = f"ID {uid}"

        await query.edit_message_text(
            Messages.top_violators(top_list, names),
            parse_mode="Markdown",
            reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
        )

    async def _show_chat_stats(self, query, context, chat_id: int, days: int, user_id: int) -> None:
        """Показывает статистику чата."""
        stats = await self.stats_repo.get_stats(chat_id, days)

        await query.edit_message_text(
            Messages.chat_stats(stats, days), parse_mode="Markdown", reply_markup=Keyboards.stats_period(user_id)
        )

    # ═══════════════════════════════════════════════════════════
    # ⚙️ НАСТРОЙКИ
    # ═══════════════════════════════════════════════════════════

    async def _show_settings(self, query, context, chat_id: int, user_id: int) -> None:
        """Показывает настройки."""
        # Проверка прав
        is_admin = await self.admin_service.is_chat_admin(context, chat_id, user_id)

        settings = await self.settings_repo.get(chat_id)

        if is_admin:
            await query.edit_message_text(
                Messages.settings_overview(settings),
                parse_mode="Markdown",
                reply_markup=Keyboards.settings_menu(user_id),
            )
        else:
            await query.edit_message_text(
                Messages.settings_overview(settings) + "\n\n_Только админы могут менять настройки_",
                parse_mode="Markdown",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )

    async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка настроек."""
        query = update.callback_query
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        data = query.data

        # Извлекаем owner_id из callback_data
        owner_id = self._extract_owner_id(data)

        # Проверка владельца меню
        if owner_id and owner_id != user_id:
            await query.answer("❌ Это не твоё меню!", show_alert=True)
            return

        # Проверка прав
        is_admin = await self.admin_service.is_chat_admin(context, chat_id, user_id)
        if not is_admin:
            await query.answer("❌ Только админы!", show_alert=True)
            return

        await query.answer()
        settings = await self.settings_repo.get(chat_id)

        try:
            if data.startswith("settings_"):
                parts = data.split("_")
                setting_type = parts[1]

                if setting_type == "warning":
                    enabled = settings.get("warning_enabled", True)
                    await query.edit_message_text(
                        "⚠️ *Предупреждения*\n\n" "_Показывать предупреждение перед баном?_",
                        parse_mode="Markdown",
                        reply_markup=Keyboards.warning_toggle(enabled, user_id),
                    )
                else:
                    limit_key = f"{setting_type}_limit"
                    window_key = f"{setting_type}_window"
                    await query.edit_message_text(
                        Messages.setting_detail(setting_type, settings[limit_key], settings[window_key]),
                        parse_mode="Markdown",
                        reply_markup=Keyboards.setting_adjust(setting_type, settings[limit_key], user_id),
                    )

            elif data.startswith("setting_"):
                parts = data.split("_")
                setting_type = parts[1]
                action = parts[2]

                if setting_type == "warning":
                    new_value = 1 if action == "on" else 0
                    await self.settings_repo.set(chat_id, "warning_enabled", new_value)
                    await query.edit_message_text(
                        "⚠️ *Предупреждения*\n\n" f"{'✅ Включены!' if new_value else '❌ Выключены!'}",
                        parse_mode="Markdown",
                        reply_markup=Keyboards.warning_toggle(bool(new_value), user_id),
                    )
                else:
                    limit_key = f"{setting_type}_limit"
                    current = settings[limit_key]

                    if action == "inc":
                        new_value = min(current + 1, 20)
                    elif action == "dec":
                        new_value = max(current - 1, 1)
                    else:
                        new_value = int(action)

                    await self.settings_repo.set(chat_id, limit_key, new_value)
                    settings[limit_key] = new_value

                    await query.edit_message_text(
                        Messages.setting_detail(setting_type, new_value, settings[f"{setting_type}_window"]),
                        parse_mode="Markdown",
                        reply_markup=Keyboards.setting_adjust(setting_type, new_value, user_id),
                    )

        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Settings callback error: {e}")

    # ═══════════════════════════════════════════════════════════
    # 🤍 БЕЛЫЙ СПИСОК
    # ═══════════════════════════════════════════════════════════

    async def _show_whitelist(self, query, context, chat_id: int, user_id: int, page: int = 0) -> None:
        """Показывает белый список с пагинацией."""
        wl = await self.whitelist_repo.get_all(chat_id)

        # Получаем имена
        users = []
        for uid, _ in wl:
            try:
                member = await context.bot.get_chat_member(chat_id, uid)
                users.append((uid, member.user.first_name))
            except Exception:
                users.append((uid, f"ID {uid}"))

        await query.edit_message_text(
            Messages.whitelist_view(len(users)),
            parse_mode="Markdown",
            reply_markup=Keyboards.whitelist_menu(users, page, user_id),
        )

    async def handle_whitelist_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка белого списка."""
        query = update.callback_query
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        data = query.data

        # Извлекаем owner_id из callback_data
        owner_id = self._extract_owner_id(data)

        # Проверка владельца меню
        if owner_id and owner_id != user_id:
            await query.answer("❌ Это не твоё меню!", show_alert=True)
            return

        if data.startswith("whitelist_add_info"):
            await query.answer("Ответь на сообщение пользователя командой /trust", show_alert=True)
            return

        # Проверка прав для изменений
        is_admin = await self.admin_service.is_chat_admin(context, chat_id, user_id)
        if not is_admin:
            await query.answer("❌ Только админы!", show_alert=True)
            return

        await query.answer()

        if data.startswith("whitelist_add_"):
            parts = data.split("_")
            target_id = int(parts[2])
            await self.whitelist_repo.add(target_id, chat_id, user_id)

            try:
                member = await context.bot.get_chat_member(chat_id, target_id)
                user = UserInfo(target_id, member.user.first_name)
            except Exception:
                user = UserInfo(target_id, f"ID {target_id}")

            await query.edit_message_text(
                Messages.whitelist_added(user),
                parse_mode="Markdown",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )

        elif data.startswith("whitelist_remove_"):
            parts = data.split("_")
            target_id = int(parts[2])
            await self.whitelist_repo.remove(target_id, chat_id)

            try:
                member = await context.bot.get_chat_member(chat_id, target_id)
                user = UserInfo(target_id, member.user.first_name)
            except Exception:
                user = UserInfo(target_id, f"ID {target_id}")

            await query.edit_message_text(
                Messages.whitelist_removed(user),
                parse_mode="Markdown",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )

    # ═══════════════════════════════════════════════════════════
    # 🎮 DOTA 2
    # ═══════════════════════════════════════════════════════════

    async def _show_dota_menu(self, query, context, user_id: int) -> None:
        """Показывает меню Dota 2."""
        is_linked = False
        is_shame_subscribed = False

        if self.steam_repo:
            account_id = await self.steam_repo.get_account_id(user_id)
            is_linked = account_id is not None

            if is_linked:
                chat_id = query.message.chat_id
                is_shame_subscribed = await self.steam_repo.is_shame_subscribed(user_id, chat_id)

        text = "🎮 *Dota 2*\n\n"
        if is_linked:
            text += "✅ Steam привязан\n\nВыбери действие:"
        else:
            text += "❌ Steam не привязан\n\nПривяжи аккаунт чтобы использовать функции:"

        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=Keyboards.dota_menu(user_id, is_linked, is_shame_subscribed)
        )

    async def handle_dota_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка Dota меню."""
        query = update.callback_query
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        data = query.data

        # Извлекаем owner_id из callback_data
        owner_id = self._extract_owner_id(data)

        # Проверка владельца меню
        if owner_id and owner_id != user_id:
            await query.answer("❌ Это не твоё меню!", show_alert=True)
            return

        await query.answer()

        try:
            if data.startswith("dota_link_info"):
                await query.edit_message_text(
                    "🔗 *Как привязать Steam:*\n\n"
                    "Напиши мне в ЛС команду:\n"
                    "`/link <ссылка или ID>`\n\n"
                    f"{OpenDotaService.get_supported_formats()}\n"
                    "📌 *Примеры:*\n"
                    "• `/link 123456789`\n"
                    "• `/link https://dotabuff.com/players/123456789`\n"
                    "• `/link https://steamcommunity.com/id/nickname`",
                    parse_mode="Markdown",
                    reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
                )
                return

            # Для остальных команд нужна привязка
            if not self.steam_repo or not self.opendota:
                await query.edit_message_text(
                    "❌ Сервис временно недоступен",
                    reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
                )
                return

            account_id = await self.steam_repo.get_account_id(user_id)

            if not account_id:
                await query.edit_message_text(
                    "❌ Сначала привяжи Steam!\n" "Напиши мне в ЛС: /link",
                    reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
                )
                return

            if data.startswith("dota_game"):
                await self._dota_check_game(query, context, user_id, account_id)

            elif data.startswith("dota_last"):
                await self._dota_last_match(query, context, user_id, account_id)

            elif data.startswith("dota_profile"):
                await self._dota_profile(query, context, account_id, user_id)

            elif data.startswith("dota_toxic"):
                await self._dota_toxic(query, context, user_id, account_id)

            elif data.startswith("dota_shame_toggle"):
                await self._dota_shame_toggle(query, context, user_id, chat_id)

            elif data.startswith("dota_unlink"):
                await self.steam_repo.unlink(user_id)
                await query.edit_message_text(
                    "✅ Steam отвязан!", reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True)
                )

        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Dota callback error: {e}")

    async def _dota_check_game(self, query, context, user_id: int, account_id: int) -> None:
        """Проверяет в игре ли пользователь."""
        name = query.from_user.first_name

        await query.edit_message_text(f"🔍 Чекаю {name}...")

        live = await self.opendota.get_live_game(account_id)

        if live:
            mmr_text = f"📊 ~{live.avg_mmr} MMR" if live.avg_mmr else ""

            await query.edit_message_text(
                f"🎮 *{name} в игре!*\n\n"
                f"⏱ *{live.time_str}* минута\n"
                f"🦸 {live.player_hero}\n"
                f"⚔️ {live.player_team}\n"
                f"🎯 {live.game_mode}\n"
                f"{mmr_text}",
                parse_mode="Markdown",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )
        else:
            await query.edit_message_text(
                f"😴 *{name}* сейчас не в игре\n\n" f"_Или матч не отслеживается OpenDota_",
                parse_mode="Markdown",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )

    async def _dota_last_match(self, query, context, user_id: int, account_id: int) -> None:
        """Показывает детальную стату последнего матча."""
        name = query.from_user.first_name

        await query.edit_message_text(f"🔍 Загружаю матч {name}...")

        match = await self.opendota.get_match_details(account_id)

        if not match:
            await query.edit_message_text(
                "❌ Не удалось получить данные матча",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )
            return

        result = "✅ *ПОБЕДА*" if match["win"] else "❌ *ПОРАЖЕНИЕ*"
        kda = f"{match['kills']}/{match['deaths']}/{match['assists']}"

        def rank_emoji(rank):
            if rank == 1:
                return "🥇"
            elif rank == 2:
                return "🥈"
            elif rank == 3:
                return "🥉"
            return f"#{rank}"

        def fmt(n):
            if n >= 1000:
                return f"{n / 1000:.1f}k"
            return str(n)

        text = (
            f"📊 *Последний матч {name}*\n\n"
            f"{result} • {match['hero']}\n"
            f"⏱ {match['duration']} мин\n\n"
            f"⚔️ *KDA:* {kda}\n"
            f"💰 *GPM:* {match['gpm']} {rank_emoji(match['gpm_rank'])}\n"
            f"📈 *XPM:* {match['xpm']}\n\n"
            f"🗡 *Урон героям:* {fmt(match['hero_damage'])} {rank_emoji(match['hero_dmg_rank'])}\n"
            f"🏰 *Урон вышкам:* {fmt(match['tower_damage'])} {rank_emoji(match['tower_dmg_rank'])}\n\n"
            f"🌾 *LH/DN:* {match['last_hits']}/{match['denies']}\n"
            f"💎 *Net Worth:* {fmt(match['net_worth'])}\n"
            f"\n🔗 [Подробнее](https://www.opendota.com/matches/{match['match_id']})"
        )

        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True)
        )

    async def _dota_profile(self, query, context, account_id: int, user_id: int) -> None:
        """Показывает профиль игрока."""
        profile = await self.opendota.get_profile(account_id)

        if not profile:
            await query.edit_message_text(
                "❌ Не удалось загрузить профиль",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )
            return

        mmr_text = f"📈 ~{profile.mmr_estimate} MMR" if profile.mmr_estimate else ""

        await query.edit_message_text(
            f"👤 *{profile.persona_name}*\n\n"
            f"🏅 {profile.rank_name}\n"
            f"{mmr_text}\n\n"
            f"🔗 [OpenDota](https://www.opendota.com/players/{account_id}) | "
            f"[Dotabuff](https://www.dotabuff.com/players/{account_id})",
            parse_mode="Markdown",
            reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
        )

    async def _dota_toxic(self, query, context, user_id: int, account_id: int) -> None:
        """Показывает анализ токсичности."""
        name = query.from_user.first_name

        await query.edit_message_text(f"🔍 Анализирую токсичность {name}...")

        words = await self.opendota.get_wordcloud(account_id)

        if not words:
            await query.edit_message_text(
                f"😇 *{name}* — святой человек!\n\n" f"_Либо не пишет в чат, либо данных нет_",
                parse_mode="Markdown",
                reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
            )
            return

        sorted_words = sorted(words.items(), key=lambda x: x[1], reverse=True)
        top_words = sorted_words[:10]
        total_words = sum(words.values())

        toxic_words = {
            "gg",
            "ez",
            "noob",
            "report",
            "trash",
            "bad",
            "wtf",
            "fuck",
            "shit",
            "idiot",
            "stupid",
            "dog",
            "animal",
            "cyka",
            "blyat",
            "сука",
            "блять",
            "gg ez",
        }

        toxic_count = sum(count for word, count in words.items() if word.lower() in toxic_words)
        toxic_percent = (toxic_count / total_words * 100) if total_words > 0 else 0

        if toxic_percent > 20:
            rating = "☢️ ЯДЕРНЫЙ ТОКСИК"
        elif toxic_percent > 10:
            rating = "🔥 Токсичный"
        elif toxic_percent > 5:
            rating = "😤 Немного солёный"
        else:
            rating = "😇 Почти ангел"

        lines = [f"💬 *Словарь {name}*\n"]
        lines.append(f"{rating}\n")

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, (word, count) in enumerate(top_words):
            medal = medals[i] if i < len(medals) else "•"
            lines.append(f"{medal} `{word}` — {count}")

        lines.append(f"\n📊 Всего слов: {total_words}")

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True),
        )

    async def _dota_shame_toggle(self, query, context, user_id: int, chat_id: int) -> None:
        """Переключает подписку на позор."""
        is_subscribed = await self.steam_repo.is_shame_subscribed(user_id, chat_id)

        if is_subscribed:
            await self.steam_repo.unsubscribe_shame(user_id, chat_id)
            text = "❌ *Подписка отключена*\n\nБольше никакого позора... пока что 👀"
        else:
            await self.steam_repo.subscribe_shame(user_id, chat_id)
            text = "✅ *Подписка активирована!*\n\nТеперь после каждой катки бот определит самого бесполезного 😈"

        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=Keyboards.back_button(f"menu_main_{user_id}", as_markup=True)
        )
