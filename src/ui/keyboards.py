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
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📊 Моя статистика", callback_data="menu_stats"),
                    InlineKeyboardButton("🏆 Топ", callback_data="menu_top"),
                ],
                [
                    InlineKeyboardButton("📈 Статистика чата", callback_data="menu_chatstats"),
                    InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
                ],
                [
                    InlineKeyboardButton("🎮 Dota 2", callback_data="menu_dota"),
                    InlineKeyboardButton("🤍 Белый список", callback_data="menu_whitelist"),
                ],
                [
                    InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
                ],
            ]
        )

    @staticmethod
    def dota_menu(is_linked: bool = False, is_shame_subscribed: bool = False) -> InlineKeyboardMarkup:
        """Меню Dota 2."""
        buttons = []

        if is_linked:
            buttons.append(
                [
                    InlineKeyboardButton("🎮 В игре?", callback_data="dota_game"),
                    InlineKeyboardButton("📊 Последний матч", callback_data="dota_last"),
                ]
            )
            buttons.append(
                [
                    InlineKeyboardButton("👤 Мой профиль", callback_data="dota_profile"),
                    InlineKeyboardButton("☢️ Токсичность", callback_data="dota_toxic"),
                ]
            )

            shame_text = "😈 Позор: ВКЛ" if is_shame_subscribed else "😇 Позор: ВЫКЛ"
            buttons.append(
                [
                    InlineKeyboardButton(shame_text, callback_data="dota_shame_toggle"),
                ]
            )
            buttons.append(
                [
                    InlineKeyboardButton("🔗 Отвязать Steam", callback_data="dota_unlink"),
                ]
            )
        else:
            buttons.append(
                [
                    InlineKeyboardButton("🔗 Привязать Steam", callback_data="dota_link_info"),
                ]
            )

        buttons.append(Keyboards.back_button())
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def back_button(callback: str = "menu_main", as_markup: bool = False):
        """
        Универсальная кнопка "Назад".

        Args:
            callback: callback_data для кнопки (по умолчанию "menu_main")
            as_markup: если True, возвращает InlineKeyboardMarkup, иначе list

        Returns:
            InlineKeyboardMarkup или list с кнопкой назад
        """
        button = [InlineKeyboardButton("◀️ Назад", callback_data=callback)]
        return InlineKeyboardMarkup([button]) if as_markup else button

    # ═══════════════════════════════════════════════════════════
    # ⚙️ НАСТРОЙКИ
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Меню настроек."""
        return InlineKeyboardMarkup(
            [
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
                Keyboards.back_button(),
            ]
        )

    @staticmethod
    def setting_adjust(setting_type: str, current_limit: int) -> InlineKeyboardMarkup:
        """Кнопки изменения лимита."""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("➖", callback_data=f"setting_{setting_type}_dec"),
                    InlineKeyboardButton(f"📊 {current_limit}", callback_data="ignore"),
                    InlineKeyboardButton("➕", callback_data=f"setting_{setting_type}_inc"),
                ],
                [
                    InlineKeyboardButton("1️⃣", callback_data=f"setting_{setting_type}_1"),
                    InlineKeyboardButton("3️⃣", callback_data=f"setting_{setting_type}_3"),
                    InlineKeyboardButton("5️⃣", callback_data=f"setting_{setting_type}_5"),
                    InlineKeyboardButton("🔟", callback_data=f"setting_{setting_type}_10"),
                ],
                [InlineKeyboardButton("◀️ К настройкам", callback_data="menu_settings")],
            ]
        )

    @staticmethod
    def warning_toggle(enabled: bool) -> InlineKeyboardMarkup:
        """Переключатель предупреждений."""
        status = "✅ Включены" if enabled else "❌ Выключены"
        action = "off" if enabled else "on"
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(status, callback_data="ignore")],
                [
                    InlineKeyboardButton(
                        "🔕 Выключить" if enabled else "🔔 Включить", callback_data=f"setting_warning_{action}"
                    )
                ],
                [InlineKeyboardButton("◀️ К настройкам", callback_data="menu_settings")],
            ]
        )

    # ═══════════════════════════════════════════════════════════
    # 🚨 МОДЕРАЦИЯ
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def ban_actions(user_id: int) -> InlineKeyboardMarkup:
        """Кнопки действий при бане."""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔓 Разбанить", callback_data=f"action_unban_{user_id}"),
                    InlineKeyboardButton("🎉 Простить", callback_data=f"action_pardon_{user_id}"),
                ],
                [
                    InlineKeyboardButton("📊 Инфо", callback_data=f"user_info_{user_id}"),
                ],
            ]
        )

    @staticmethod
    def user_actions(user_id: int, is_banned: bool, is_whitelisted: bool) -> InlineKeyboardMarkup:
        """Кнопки действий с пользователем."""
        buttons = []

        if is_banned:
            buttons.append(
                [
                    InlineKeyboardButton("🔓 Разбанить", callback_data=f"action_unban_{user_id}"),
                    InlineKeyboardButton("🎉 Простить всё", callback_data=f"action_pardon_{user_id}"),
                ]
            )

        if is_whitelisted:
            buttons.append(
                [InlineKeyboardButton("⛔ Убрать из белого списка", callback_data=f"whitelist_remove_{user_id}")]
            )
        else:
            buttons.append([InlineKeyboardButton("🤍 В белый список", callback_data=f"whitelist_add_{user_id}")])

        buttons.append(Keyboards.back_button())
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def confirm_action(action: str, user_id: int) -> InlineKeyboardMarkup:
        """Подтверждение действия."""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Да", callback_data=f"action_{action}_{user_id}"),
                    InlineKeyboardButton("❌ Нет", callback_data="action_cancel"),
                ]
            ]
        )

    @staticmethod
    def confirm_unban(user_id: int) -> InlineKeyboardMarkup:
        """Подтверждение разбана."""
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Да, разбанить", callback_data=f"action_unban_{user_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data="action_cancel")],
            ]
        )

    @staticmethod
    def confirm_pardon(user_id: int) -> InlineKeyboardMarkup:
        """Подтверждение прощения."""
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Да, простить", callback_data=f"action_pardon_{user_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data="action_cancel")],
            ]
        )

    # ═══════════════════════════════════════════════════════════
    # 🤍 БЕЛЫЙ СПИСОК
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def whitelist_menu(users: list, page: int = 0) -> InlineKeyboardMarkup:
        """Меню белого списка с пагинацией."""
        buttons = []

        # Пагинация: 8 пользователей на страницу
        page_size = 8
        start_idx = page * page_size
        end_idx = start_idx + page_size
        page_users = users[start_idx:end_idx]

        for user_id, name in page_users:
            buttons.append(
                [
                    InlineKeyboardButton(f"👤 {name}", callback_data=f"user_info_{user_id}"),
                    InlineKeyboardButton("❌", callback_data=f"whitelist_remove_{user_id}"),
                ]
            )

        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"whitelist_page_{page-1}"))
        if end_idx < len(users):
            nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"whitelist_page_{page+1}"))

        if nav_buttons:
            buttons.append(nav_buttons)

        buttons.append([InlineKeyboardButton("➕ Добавить", callback_data="whitelist_add_info")])
        buttons.append(Keyboards.back_button())

        return InlineKeyboardMarkup(buttons)

    # ═══════════════════════════════════════════════════════════
    # 📊 СТАТИСТИКА
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def stats_period() -> InlineKeyboardMarkup:
        """Выбор периода статистики."""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 Сегодня", callback_data="chatstats_1"),
                    InlineKeyboardButton("📆 Неделя", callback_data="chatstats_7"),
                    InlineKeyboardButton("🗓 Месяц", callback_data="chatstats_30"),
                ],
                Keyboards.back_button(),
            ]
        )

    @staticmethod
    def top_actions(user_id: int) -> InlineKeyboardMarkup:
        """Действия в топе нарушителей."""
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📋 Подробнее", callback_data=f"user_info_{user_id}")],
                Keyboards.back_button("menu_top"),
            ]
        )
