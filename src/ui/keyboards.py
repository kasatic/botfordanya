"""
Клавиатуры и кнопки бота.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    """Фабрика клавиатур."""
    
    # ═══════════════════════════════════════════════════════════
    # 🏠 ГЛАВНОЕ МЕНЮ
    # ═══════════════════════════════════════════════════════════
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Главное меню бота."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Моя статистика", callback_data="menu_stats"),
                InlineKeyboardButton("🏆 Топ", callback_data="menu_top"),
            ],
            [
                InlineKeyboardButton("📈 Статистика чата", callback_data="menu_chatstats"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
            ],
            [
                InlineKeyboardButton("🤍 Белый список", callback_data="menu_whitelist"),
                InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
            ],
        ])
    
    @staticmethod
    def back_to_menu() -> InlineKeyboardMarkup:
        """Кнопка возврата в меню."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_main")]
        ])
    
    @staticmethod
    def back_button(callback: str = "menu_main") -> list:
        """Кнопка назад (для добавления в другие клавиатуры)."""
        return [InlineKeyboardButton("◀️ Назад", callback_data=callback)]
    
    # ═══════════════════════════════════════════════════════════
    # ⚙️ НАСТРОЙКИ
    # ═══════════════════════════════════════════════════════════
    
    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Меню настроек."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎭 Стикеры/GIF", callback_data="settings_sticker"),
                InlineKeyboardButton("💬 Текст", callback_data="settings_text"),
            ],
            [
                InlineKeyboardButton("🖼 Картинки", callback_data="settings_image"),
                InlineKeyboardButton("🎥 Видео", callback_data="settings_video"),
            ],
            [
                InlineKeyboardButton("⚠️ Предупреждения", callback_data="settings_warning"),
            ],
            Keyboards.back_button()
        ])
    
    @staticmethod
    def setting_adjust(setting_type: str, current_limit: int) -> InlineKeyboardMarkup:
        """Кнопки изменения лимита."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➖", callback_data=f"set_{setting_type}_dec"),
                InlineKeyboardButton(f"📊 {current_limit}", callback_data="noop"),
                InlineKeyboardButton("➕", callback_data=f"set_{setting_type}_inc"),
            ],
            [
                InlineKeyboardButton("1️⃣", callback_data=f"set_{setting_type}_1"),
                InlineKeyboardButton("3️⃣", callback_data=f"set_{setting_type}_3"),
                InlineKeyboardButton("5️⃣", callback_data=f"set_{setting_type}_5"),
                InlineKeyboardButton("🔟", callback_data=f"set_{setting_type}_10"),
            ],
            [InlineKeyboardButton("◀️ К настройкам", callback_data="menu_settings")]
        ])
    
    @staticmethod
    def warning_toggle(enabled: bool) -> InlineKeyboardMarkup:
        """Переключатель предупреждений."""
        status = "✅ Включены" if enabled else "❌ Выключены"
        action = "off" if enabled else "on"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(status, callback_data="noop")],
            [InlineKeyboardButton(
                "🔕 Выключить" if enabled else "🔔 Включить", 
                callback_data=f"set_warning_{action}"
            )],
            [InlineKeyboardButton("◀️ К настройкам", callback_data="menu_settings")]
        ])
    
    # ═══════════════════════════════════════════════════════════
    # 🚨 МОДЕРАЦИЯ
    # ═══════════════════════════════════════════════════════════
    
    @staticmethod
    def ban_actions(user_id: int) -> InlineKeyboardMarkup:
        """Кнопки действий при бане."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_{user_id}"),
                InlineKeyboardButton("🎉 Простить", callback_data=f"pardon_{user_id}"),
            ],
            [
                InlineKeyboardButton("📊 Инфо", callback_data=f"userinfo_{user_id}"),
            ]
        ])
    
    @staticmethod
    def user_actions(user_id: int, is_banned: bool, is_whitelisted: bool) -> InlineKeyboardMarkup:
        """Кнопки действий с пользователем."""
        buttons = []
        
        if is_banned:
            buttons.append([
                InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_{user_id}"),
                InlineKeyboardButton("🎉 Простить всё", callback_data=f"pardon_{user_id}"),
            ])
        
        if is_whitelisted:
            buttons.append([
                InlineKeyboardButton("⛔ Убрать из белого списка", callback_data=f"untrust_{user_id}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("🤍 В белый список", callback_data=f"trust_{user_id}")
            ])
        
        buttons.append(Keyboards.back_button())
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def confirm_action(action: str, user_id: int) -> InlineKeyboardMarkup:
        """Подтверждение действия."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}_{user_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="cancel"),
            ]
        ])
    
    # ═══════════════════════════════════════════════════════════
    # 🤍 БЕЛЫЙ СПИСОК
    # ═══════════════════════════════════════════════════════════
    
    @staticmethod
    def whitelist_menu(users: list) -> InlineKeyboardMarkup:
        """Меню белого списка."""
        buttons = []
        
        for user_id, name in users[:8]:  # Максимум 8 пользователей
            buttons.append([
                InlineKeyboardButton(f"👤 {name}", callback_data=f"userinfo_{user_id}"),
                InlineKeyboardButton("❌", callback_data=f"untrust_{user_id}"),
            ])
        
        buttons.append([
            InlineKeyboardButton("➕ Добавить", callback_data="whitelist_add_info")
        ])
        buttons.append(Keyboards.back_button())
        
        return InlineKeyboardMarkup(buttons)
    
    # ═══════════════════════════════════════════════════════════
    # 📊 СТАТИСТИКА
    # ═══════════════════════════════════════════════════════════
    
    @staticmethod
    def stats_period() -> InlineKeyboardMarkup:
        """Выбор периода статистики."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="chatstats_1"),
                InlineKeyboardButton("📆 Неделя", callback_data="chatstats_7"),
                InlineKeyboardButton("🗓 Месяц", callback_data="chatstats_30"),
            ],
            Keyboards.back_button()
        ])
    
    @staticmethod
    def top_actions(user_id: int) -> InlineKeyboardMarkup:
        """Действия в топе нарушителей."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Подробнее", callback_data=f"userinfo_{user_id}")],
            Keyboards.back_button("menu_top")
        ])
