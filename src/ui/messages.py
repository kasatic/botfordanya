"""
Шаблоны сообщений бота.
"""

import random
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class UserInfo:
    """Информация о пользователе для сообщений."""

    user_id: int
    name: str
    username: Optional[str] = None

    @property
    def mention(self) -> str:
        return f"[{self.name}](tg://user?id={self.user_id})"


class Messages:
    """Генератор сообщений бота."""

    # ═══════════════════════════════════════════════════════════
    # 🎨 ЭМОДЗИ
    # ═══════════════════════════════════════════════════════════

    TYPE_EMOJI = {
        "sticker": "🎭",
        "animation": "🎬",
        "text": "💬",
        "photo": "🖼",
        "video": "🎥",
    }

    # ═══════════════════════════════════════════════════════════
    # 😈 РАНДОМНЫЕ ФРАЗЫ
    # ═══════════════════════════════════════════════════════════

    BAN_PHRASES = [
        "Ну всё, допрыгался!",
        "Поздравляю, ты в муте!",
        "Отдохни от спама, братан",
        "Спамер детектед!",
        "Тебе пора помолчать",
        "Кто-то слишком активный...",
        "Мут заслужен!",
    ]

    WARNING_PHRASES = [
        "Эй, полегче!",
        "Ещё одно — и в мут!",
        "Последнее предупреждение!",
        "Тормози, братан!",
        "Осторожнее со спамом!",
    ]

    UNBAN_PHRASES = [
        "Свобода!",
        "Добро пожаловать обратно!",
        "Веди себя хорошо!",
        "Второй шанс получен!",
    ]

    # ═══════════════════════════════════════════════════════════
    # 📝 ШАБЛОНЫ
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _random(phrases: list) -> str:
        return random.choice(phrases)

    @staticmethod
    def _progress_bar(value: int, max_value: int = 5, filled: str = "🔴", empty: str = "⚪") -> str:
        """Генерирует прогресс-бар."""
        filled_count = min(value, max_value)
        return filled * filled_count + empty * (max_value - filled_count)

    @staticmethod
    def _format_time(minutes: int) -> str:
        """Форматирует время красиво."""
        if minutes < 60:
            return f"{minutes} мин"
        hours = minutes // 60
        mins = minutes % 60
        if hours >= 24:
            days = hours // 24
            hours = hours % 24
            if hours == 0:
                return f"{days} д"
            return f"{days} д {hours} ч"
        if mins == 0:
            return f"{hours} ч"
        return f"{hours} ч {mins} мин"

    # ═══════════════════════════════════════════════════════════
    # 🏠 ГЛАВНОЕ МЕНЮ
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def welcome(cls) -> str:
        return (
            "👋 *Привет!*\n\n"
            "Я слежу за порядком в чате — не даю спамить "
            "стикерами, гифками и прочим.\n\n"
            "🎮 Напиши «го дота» — призову всех игроков!\n\n"
            "Выбери действие:"
        )

    @classmethod
    def help_text(cls) -> str:
        return (
            "❓ *Как я работаю:*\n\n"
            "1️⃣ Слежу за спамом стикерами, GIF, фото, видео\n"
            "2️⃣ Если кто-то превысит лимит — мут\n"
            "3️⃣ При муте можно писать только текст\n"
            "4️⃣ Баны прогрессивные: 10м → 1ч → 5ч → 24ч\n\n"
            "📋 *Команды:*\n"
            "`/menu` — главное меню\n"
            "`/stats` — твоя статистика\n"
            "`/top` — топ нарушителей\n"
            "`/settings` — настройки чата\n\n"
            "🤍 *Белый список* — для тех, кому можно всё"
        )

    # ═══════════════════════════════════════════════════════════
    # 📊 СТАТИСТИКА
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def user_stats(
        cls, user: UserInfo, violations: int, is_banned: bool, remaining_minutes: Optional[int], is_whitelisted: bool
    ) -> str:
        if is_whitelisted:
            return f"📊 *Статистика: {user.name}*\n\n" f"🤍 *В белом списке*\n" f"Спам-контроль не применяется 😎"

        if violations == 0:
            return f"📊 *Статистика: {user.name}*\n\n" f"✅ *Чисто!*\n" f"Нарушений нет. Красавчик! 👊"

        bar = cls._progress_bar(violations)
        text = f"📊 *Статистика: {user.name}*\n\n" f"⚠️ Нарушений: *{violations}*\n" f"📈 Уровень: {bar}\n\n"

        if is_banned and remaining_minutes:
            text += f"🔒 *В муте!* Осталось: *{cls._format_time(remaining_minutes)}*\n"
            text += "📝 Можно писать только текст"
        else:
            text += "🔓 Не в муте"

        return text

    @classmethod
    def chat_stats(cls, stats: Dict[str, Any], period_days: int) -> str:
        period_text = {1: "сегодня", 7: "за неделю", 30: "за месяц"}.get(period_days, f"за {period_days} дней")

        if stats["total_bans"] == 0:
            return f"📈 *Статистика чата ({period_text}):*\n\n" f"🎉 Банов не было!\n" f"Все молодцы! 👊"

        # По типам
        type_lines = []
        for ban_type, cnt in stats["by_type"].items():
            emoji = cls.TYPE_EMOJI.get(ban_type, "📌")
            type_lines.append(f"  {emoji} {ban_type}: *{cnt}*")

        text = (
            f"📈 *Статистика чата ({period_text}):*\n\n"
            f"🔒 Всего банов: *{stats['total_bans']}*\n"
            f"⏱ Суммарное время: *{cls._format_time(stats['total_ban_minutes'])}*\n\n"
        )

        if type_lines:
            text += "📊 *По типам:*\n" + "\n".join(type_lines) + "\n\n"

        if stats["top_violators"]:
            text += "👥 *Топ нарушителей:*\n"
            medals = ["🥇", "🥈", "🥉"]
            for idx, (user_id, cnt) in enumerate(stats["top_violators"][:3]):
                medal = medals[idx] if idx < 3 else "•"
                text += f"  {medal} ID {user_id}: *{cnt}*\n"

        return text

    @classmethod
    def top_violators(cls, top_list: list, names: Dict[int, str]) -> str:
        if not top_list:
            return "🏆 *Топ нарушителей:*\n\n" "🎉 Пусто! Все ведут себя хорошо 👊"

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        lines = ["🏆 *Топ нарушителей:*\n"]
        for idx, (user_id, count) in enumerate(top_list):
            name = names.get(user_id, f"ID {user_id}")
            medal = medals[idx] if idx < len(medals) else "•"
            bar = cls._progress_bar(count, 10, "█", "░")
            lines.append(f"{medal} {name}\n    {bar} *{count}*")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # ⚙️ НАСТРОЙКИ
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def settings_overview(cls, settings: Dict[str, Any]) -> str:
        warning_status = "✅" if settings.get("warning_enabled") else "❌"
        return (
            "⚙️ *Настройки чата:*\n\n"
            f"🎭 Стикеры/GIF: *{settings['sticker_limit']}* за *{settings['sticker_window']}с*\n"
            f"💬 Текст: *{settings['text_limit']}* за *{settings['text_window']}с*\n"
            f"🖼 Картинки: *{settings['image_limit']}* за *{settings['image_window']}с*\n"
            f"🎥 Видео: *{settings['video_limit']}* за *{settings['video_window']}с*\n\n"
            f"⚠️ Предупреждения: {warning_status}\n\n"
            "Выбери что настроить:"
        )

    @classmethod
    def setting_detail(cls, setting_type: str, limit: int, window: int) -> str:
        emoji = {"sticker": "🎭", "text": "💬", "image": "🖼", "video": "🎥"}.get(setting_type, "⚙️")
        name = {"sticker": "Стикеры/GIF", "text": "Текст", "image": "Картинки", "video": "Видео"}.get(
            setting_type, setting_type
        )

        return (
            f"{emoji} *Настройка: {name}*\n\n"
            f"📊 Лимит: *{limit}* сообщений\n"
            f"⏱ Окно: *{window}* секунд\n\n"
            f"_Если отправить {limit}+ за {window}с — мут_\n\n"
            "Измени лимит:"
        )

    # ═══════════════════════════════════════════════════════════
    # 🚨 МОДЕРАЦИЯ
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def warning(cls, user: UserInfo, count: int, limit: int, reason: str, spam_type: str) -> str:
        emoji = cls.TYPE_EMOJI.get(spam_type, "⚠️")
        phrase = cls._random(cls.WARNING_PHRASES)

        return f"{emoji} *{user.name}*, {phrase}\n\n" f"📊 Счётчик: `{count}/{limit}` {reason}\n" f"⏳ Ещё *1* — и мут!"

    @classmethod
    def ban_notification(
        cls, user: UserInfo, violation_count: int, ban_minutes: int, spam_count: int, reason: str, spam_type: str
    ) -> str:
        emoji = cls.TYPE_EMOJI.get(spam_type, "🚫")
        phrase = cls._random(cls.BAN_PHRASES)
        bar = cls._progress_bar(violation_count)
        time_str = cls._format_time(ban_minutes)

        return (
            f"{emoji} *МУТ!* {phrase}\n\n"
            f"👤 {user.mention}\n"
            f"📊 Нарушение: *#{violation_count}* {bar}\n"
            f"⏱ Срок: *{time_str}*\n"
            f"📝 Режим: только текст\n"
            f"💬 Причина: {spam_count} {reason}"
        )

    @classmethod
    def unban_notification(cls, user: UserInfo, admin_name: str) -> str:
        phrase = cls._random(cls.UNBAN_PHRASES)
        return f"🔓 *Разбанен!* {phrase}\n\n" f"👤 {user.mention}\n" f"👮 Админ: {admin_name}"

    @classmethod
    def pardon_notification(cls, user: UserInfo, admin_name: str) -> str:
        return f"🎉 *Полностью прощён!*\n\n" f"👤 {user.mention}\n" f"👮 Админ: {admin_name}\n" f"🧹 История очищена!"

    # ═══════════════════════════════════════════════════════════
    # 🤍 БЕЛЫЙ СПИСОК
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def whitelist_view(cls, count: int) -> str:
        if count == 0:
            return (
                "🤍 *Белый список*\n\n"
                "Пусто! Никому не доверяем 😈\n\n"
                "_Чтобы добавить — ответь на сообщение_\n"
                "_пользователя командой /trust_"
            )
        return f"🤍 *Белый список ({count}):*\n\n" "_Эти пользователи могут спамить_"

    @classmethod
    def whitelist_added(cls, user: UserInfo) -> str:
        return f"🤍 *Добавлен в белый список!*\n\n" f"👤 {user.mention}\n" f"Теперь может спамить сколько хочет 😎"

    @classmethod
    def whitelist_removed(cls, user: UserInfo) -> str:
        return f"⛔ *Убран из белого списка!*\n\n" f"👤 {user.mention}\n" f"Снова под контролем!"
