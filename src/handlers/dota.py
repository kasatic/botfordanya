"""
Обработчики команд для Dota 2.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.services.opendota_service import OpenDotaService
from src.database.steam_repository import SteamLinkRepository

logger = logging.getLogger(__name__)


class DotaHandlers:
    """Обработчики Dota команд."""
    
    def __init__(self, opendota: OpenDotaService, steam_repo: SteamLinkRepository):
        self.opendota = opendota
        self.steam_repo = steam_repo
    
    async def link_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /link <steam_id или ссылка> — привязать Steam аккаунт.
        Поддерживает разные форматы: ID, ссылки Dotabuff/OpenDota/Steam.
        Ответ виден только пользователю.
        """
        user_id = update.effective_user.id
        
        # Удаляем команду чтобы ID не светился в чате
        try:
            await update.message.delete()
        except:
            pass
        
        if not context.args:
            # Отправляем приватно с подробной инструкцией
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎮 *Как привязать Steam:*\n\n"
                    "Просто скопируй ссылку на свой профиль и отправь:\n"
                    "`/link <ссылка или ID>`\n\n"
                    f"{OpenDotaService.get_supported_formats()}\n"
                    "📌 *Примеры:*\n"
                    "• `/link 123456789`\n"
                    "• `/link https://dotabuff.com/players/123456789`\n"
                    "• `/link https://steamcommunity.com/id/nickname`"
                ),
                parse_mode="Markdown"
            )
            return
        
        # Собираем весь ввод (ссылка может содержать пробелы если скопирована криво)
        steam_input = " ".join(context.args)
        
        # Показываем что обрабатываем (для кастомных URL может быть задержка)
        processing_msg = None
        if "steamcommunity.com/id/" in steam_input.lower():
            try:
                processing_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text="🔍 Ищу профиль по кастомному URL..."
                )
            except:
                pass
        
        # Используем новый умный парсер
        account_id = await self.opendota.parse_account_id(steam_input)
        
        # Удаляем сообщение о поиске
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
        
        if not account_id:
            # Определяем тип ошибки для более точной подсказки
            error_hint = ""
            if "steamcommunity.com/id/" in steam_input.lower():
                error_hint = (
                    "\n\n💡 *Кастомный Steam URL не найден.*\n"
                    "Попробуй:\n"
                    "• Использовать числовой Steam ID\n"
                    "• Скопировать ссылку с Dotabuff/OpenDota"
                )
            elif "steamcommunity.com" in steam_input.lower():
                error_hint = "\n\n💡 Убедись что ссылка содержит `/profiles/` или `/id/`"
            
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"❌ *Не удалось распознать ID*{error_hint}\n\n"
                    f"{OpenDotaService.get_supported_formats()}"
                ),
                parse_mode="Markdown"
            )
            return
        
        # Проверяем что профиль существует
        profile = await self.opendota.get_profile(account_id)
        
        if not profile:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"❌ *Профиль не найден на OpenDota*\n\n"
                    f"🆔 Распознанный ID: `{account_id}`\n\n"
                    "Убедись что:\n"
                    "• ID правильный\n"
                    "• Профиль публичный в Steam\n"
                    "• Включено \"Expose Public Match Data\" в Dota 2\n"
                    "• Была хотя бы 1 игра\n\n"
                    "🔗 Проверь профиль: [OpenDota](https://www.opendota.com/players/{account_id})"
                ),
                parse_mode="Markdown"
            )
            return
        
        # Сохраняем
        await self.steam_repo.link(user_id, account_id, profile.persona_name)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ *Привязано!*\n\n"
                f"👤 {profile.persona_name}\n"
                f"🏅 {profile.rank_name}\n"
                f"🆔 `{account_id}`\n\n"
                f"🔗 [OpenDota](https://www.opendota.com/players/{account_id}) | "
                f"[Dotabuff](https://www.dotabuff.com/players/{account_id})\n\n"
                f"Теперь можно юзать /game, /lastgame, /last, /toxic"
            ),
            parse_mode="Markdown"
        )
    
    async def unlink_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/unlink — отвязать Steam."""
        user_id = update.effective_user.id
        
        removed = await self.steam_repo.unlink(user_id)
        
        if removed:
            await update.message.reply_text("✅ Steam отвязан!")
        else:
            await update.message.reply_text("ℹ️ У тебя и не было привязки")
    
    async def game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /game [@user] — проверить в игре ли человек.
        Без аргумента — проверяет себя.
        """
        chat_id = update.effective_chat.id
        
        # Определяем кого чекаем
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        elif context.args and context.args[0].startswith("@"):
            # TODO: резолв по username — сложно без БД
            await update.message.reply_text("💡 Лучше ответь на сообщение человека")
            return
        else:
            target_user = update.effective_user
        
        target_id = target_user.id
        target_name = target_user.first_name
        
        # Получаем привязку
        account_id = await self.steam_repo.get_account_id(target_id)
        
        if not account_id:
            if target_id == update.effective_user.id:
                await update.message.reply_text(
                    "❌ Сначала привяжи Steam!\n"
                    "Напиши мне в ЛС: /link"
                )
            else:
                await update.message.reply_text(f"❌ У {target_name} не привязан Steam")
            return
        
        # Чекаем live игру
        await update.message.reply_text(f"🔍 Чекаю {target_name}...")
        
        live = await self.opendota.get_live_game(account_id)
        
        if live:
            mmr_text = f"📊 ~{live.avg_mmr} MMR" if live.avg_mmr else ""
            
            await update.message.reply_text(
                f"🎮 *{target_name} в игре!*\n\n"
                f"⏱ *{live.time_str}* минута\n"
                f"🦸 {live.player_hero}\n"
                f"⚔️ {live.player_team}\n"
                f"🎯 {live.game_mode}\n"
                f"{mmr_text}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"😴 *{target_name}* сейчас не в игре\n\n"
                f"_Или матч не отслеживается OpenDota_",
                parse_mode="Markdown"
            )
    
    async def lastgame_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /lastgame [@user] — последний матч.
        """
        # Определяем кого чекаем
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        else:
            target_user = update.effective_user
        
        target_id = target_user.id
        target_name = target_user.first_name
        
        account_id = await self.steam_repo.get_account_id(target_id)
        
        if not account_id:
            if target_id == update.effective_user.id:
                await update.message.reply_text("❌ Сначала привяжи Steam! /link")
            else:
                await update.message.reply_text(f"❌ У {target_name} не привязан Steam")
            return
        
        match = await self.opendota.get_last_match(account_id)
        
        if not match:
            await update.message.reply_text("❌ Не удалось получить матч")
            return
        
        result = "✅ Победа" if match["win"] else "❌ Поражение"
        kda = f"{match['kills']}/{match['deaths']}/{match['assists']}"
        
        await update.message.reply_text(
            f"🎮 *Последний матч {target_name}:*\n\n"
            f"{result}\n"
            f"🦸 {match['hero']}\n"
            f"⚔️ KDA: *{kda}*\n"
            f"⏱ {match['duration']} мин\n"
            f"🎯 {match['game_mode']}\n\n"
            f"🔗 [OpenDota](https://www.opendota.com/matches/{match['match_id']})",
            parse_mode="Markdown"
        )
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/profile — показать свой профиль."""
        user_id = update.effective_user.id
        
        account_id = await self.steam_repo.get_account_id(user_id)
        
        if not account_id:
            await update.message.reply_text("❌ Сначала привяжи Steam! /link")
            return
        
        profile = await self.opendota.get_profile(account_id)
        
        if not profile:
            await update.message.reply_text("❌ Не удалось загрузить профиль")
            return
        
        mmr_text = f"📈 ~{profile.mmr_estimate} MMR" if profile.mmr_estimate else ""
        
        await update.message.reply_text(
            f"👤 *{profile.persona_name}*\n\n"
            f"🏅 {profile.rank_name}\n"
            f"{mmr_text}\n\n"
            f"🔗 [OpenDota](https://www.opendota.com/players/{account_id}) | "
            f"[Dotabuff](https://www.dotabuff.com/players/{account_id})",
            parse_mode="Markdown"
        )
    
    async def last_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /last [@user] — детальная стата последнего матча.
        """
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        else:
            target_user = update.effective_user
        
        target_id = target_user.id
        target_name = target_user.first_name
        
        account_id = await self.steam_repo.get_account_id(target_id)
        
        if not account_id:
            if target_id == update.effective_user.id:
                await update.message.reply_text("❌ Сначала привяжи Steam! /link")
            else:
                await update.message.reply_text(f"❌ У {target_name} не привязан Steam")
            return
        
        msg = await update.message.reply_text(f"🔍 Загружаю матч {target_name}...")
        
        match = await self.opendota.get_match_details(account_id)
        
        if not match:
            await msg.edit_text("❌ Не удалось получить данные матча")
            return
        
        result = "✅ *ПОБЕДА*" if match["win"] else "❌ *ПОРАЖЕНИЕ*"
        kda = f"{match['kills']}/{match['deaths']}/{match['assists']}"
        
        # Эмодзи для рангов в команде
        def rank_emoji(rank):
            if rank == 1:
                return "🥇"
            elif rank == 2:
                return "🥈"
            elif rank == 3:
                return "🥉"
            return f"#{rank}"
        
        # Форматируем числа
        def fmt(n):
            if n >= 1000:
                return f"{n/1000:.1f}k"
            return str(n)
        
        text = (
            f"📊 *Последний матч {target_name}*\n\n"
            f"{result} • {match['hero']}\n"
            f"⏱ {match['duration']} мин\n\n"
            
            f"⚔️ *KDA:* {kda}\n"
            f"💰 *GPM:* {match['gpm']} {rank_emoji(match['gpm_rank'])}\n"
            f"📈 *XPM:* {match['xpm']}\n\n"
            
            f"🗡 *Урон героям:* {fmt(match['hero_damage'])} {rank_emoji(match['hero_dmg_rank'])}\n"
            f"🏰 *Урон вышкам:* {fmt(match['tower_damage'])} {rank_emoji(match['tower_dmg_rank'])}\n\n"
            
            f"🌾 *LH/DN:* {match['last_hits']}/{match['denies']}\n"
            f"💎 *Net Worth:* {fmt(match['net_worth'])}\n"
        )
        
        # Доп инфа если есть
        extras = []
        if match.get("camps_stacked", 0) > 0:
            extras.append(f"📦 Стаков: {match['camps_stacked']}")
        if match.get("obs_placed", 0) > 0:
            extras.append(f"👁 Вардов: {match['obs_placed']}")
        if match.get("roshans", 0) > 0:
            extras.append(f"🐉 Рошанов: {match['roshans']}")
        
        if extras:
            text += "\n" + " • ".join(extras) + "\n"
        
        text += f"\n🔗 [Подробнее](https://www.opendota.com/matches/{match['match_id']})"
        
        await msg.edit_text(text, parse_mode="Markdown")
    
    async def toxic_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /toxic [@user] — топ слов из чата игрока.
        """
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        else:
            target_user = update.effective_user
        
        target_id = target_user.id
        target_name = target_user.first_name
        
        account_id = await self.steam_repo.get_account_id(target_id)
        
        if not account_id:
            if target_id == update.effective_user.id:
                await update.message.reply_text("❌ Сначала привяжи Steam! /link")
            else:
                await update.message.reply_text(f"❌ У {target_name} не привязан Steam")
            return
        
        msg = await update.message.reply_text(f"🔍 Анализирую токсичность {target_name}...")
        
        words = await self.opendota.get_wordcloud(account_id)
        
        if not words:
            await msg.edit_text(
                f"😇 *{target_name}* — святой человек!\n\n"
                f"_Либо не пишет в чат, либо данных нет_",
                parse_mode="Markdown"
            )
            return
        
        # Сортируем по частоте
        sorted_words = sorted(words.items(), key=lambda x: x[1], reverse=True)
        
        # Берём топ-10
        top_words = sorted_words[:10]
        total_words = sum(words.values())
        
        # Определяем "токсичность" по ключевым словам
        toxic_words = {"gg", "ez", "noob", "report", "trash", "bad", "wtf", "fuck", "shit", "idiot", 
                       "stupid", "dog", "animal", "cyka", "blyat", "сука", "блять", "gg ez"}
        
        toxic_count = sum(count for word, count in words.items() if word.lower() in toxic_words)
        toxic_percent = (toxic_count / total_words * 100) if total_words > 0 else 0
        
        # Рейтинг токсичности
        if toxic_percent > 20:
            rating = "☢️ ЯДЕРНЫЙ ТОКСИК"
        elif toxic_percent > 10:
            rating = "🔥 Токсичный"
        elif toxic_percent > 5:
            rating = "😤 Немного солёный"
        else:
            rating = "😇 Почти ангел"
        
        # Формируем вывод
        lines = [f"💬 *Словарь {target_name}*\n"]
        lines.append(f"{rating}\n")
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, (word, count) in enumerate(top_words):
            medal = medals[i] if i < len(medals) else "•"
            # Цензурим особо жёсткие слова (опционально)
            display_word = word
            lines.append(f"{medal} `{display_word}` — {count}")
        
        lines.append(f"\n📊 Всего слов: {total_words}")
        
        await msg.edit_text("\n".join(lines), parse_mode="Markdown")
    
    async def shame_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /shame on|off — подписка на уведомления о позоре после матчей.
        """
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Проверяем что это групповой чат
        if update.effective_chat.type not in ("supergroup", "group"):
            await update.message.reply_text(
                "❌ Эта команда работает только в группах!\n"
                "Добавь бота в чат с друзьями."
            )
            return
        
        # Проверяем привязку Steam
        account_id = await self.steam_repo.get_account_id(user_id)
        if not account_id:
            await update.message.reply_text(
                "❌ Сначала привяжи Steam!\n"
                "Напиши мне в ЛС: /link"
            )
            return
        
        # Парсим аргумент
        if not context.args:
            # Показываем статус
            is_subscribed = await self.steam_repo.is_shame_subscribed(user_id, chat_id)
            status = "✅ включены" if is_subscribed else "❌ выключены"
            await update.message.reply_text(
                f"🔔 *Уведомления о позоре:* {status}\n\n"
                f"Используй:\n"
                f"`/shame on` — включить\n"
                f"`/shame off` — выключить\n\n"
                f"_После каждой катки бот найдёт самого бесполезного и опозорит его в чате_ 😈",
                parse_mode="Markdown"
            )
            return
        
        action = context.args[0].lower()
        
        if action == "on":
            await self.steam_repo.subscribe_shame(user_id, chat_id)
            await update.message.reply_text(
                "✅ *Подписка активирована!*\n\n"
                "Теперь после каждой катки бот определит "
                "самого бесполезного игрока и опозорит его 😈\n\n"
                "_Проверка происходит каждые 2 минуты_",
                parse_mode="Markdown"
            )
        
        elif action == "off":
            await self.steam_repo.unsubscribe_shame(user_id, chat_id)
            await update.message.reply_text(
                "❌ *Подписка отключена*\n\n"
                "Больше никакого позора... пока что 👀",
                parse_mode="Markdown"
            )
        
        else:
            await update.message.reply_text(
                "❓ Используй `/shame on` или `/shame off`",
                parse_mode="Markdown"
            )
