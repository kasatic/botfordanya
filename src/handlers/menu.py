"""
Обработчики меню и навигации.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.error import BadRequest

from src.ui import Keyboards, Messages
from src.ui.messages import UserInfo
from src.services import BanService, AdminService
from src.database import (
    WhitelistRepository, ViolationRepository, 
    ChatSettingsRepository, BanStatsRepository
)

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
        stats_repo: BanStatsRepository
    ):
        self.ban_service = ban_service
        self.admin_service = admin_service
        self.whitelist_repo = whitelist_repo
        self.violation_repo = violation_repo
        self.settings_repo = settings_repo
        self.stats_repo = stats_repo
    
    # ═══════════════════════════════════════════════════════════
    # 🏠 ГЛАВНОЕ МЕНЮ
    # ═══════════════════════════════════════════════════════════
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /menu — главное меню."""
        await update.message.reply_text(
            Messages.welcome(),
            parse_mode="Markdown",
            reply_markup=Keyboards.main_menu()
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
        
        try:
            if data == "menu_main":
                await query.edit_message_text(
                    Messages.welcome(),
                    parse_mode="Markdown",
                    reply_markup=Keyboards.main_menu()
                )
            
            elif data == "menu_stats":
                await self._show_user_stats(query, context, user_id, chat_id)
            
            elif data == "menu_top":
                await self._show_top(query, context, chat_id)
            
            elif data == "menu_chatstats":
                await query.edit_message_text(
                    "📈 *Статистика чата*\n\nВыбери период:",
                    parse_mode="Markdown",
                    reply_markup=Keyboards.stats_period()
                )
            
            elif data.startswith("chatstats_"):
                days = int(data.split("_")[1])
                await self._show_chat_stats(query, context, chat_id, days)
            
            elif data == "menu_settings":
                await self._show_settings(query, context, chat_id, user_id)
            
            elif data == "menu_whitelist":
                await self._show_whitelist(query, context, chat_id)
            
            elif data == "menu_help":
                await query.edit_message_text(
                    Messages.help_text(),
                    parse_mode="Markdown",
                    reply_markup=Keyboards.back_to_menu()
                )
            
            elif data == "noop":
                pass  # Ничего не делаем
                
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
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
        
        user = UserInfo(
            user_id=user_id,
            name=query.from_user.first_name,
            username=query.from_user.username
        )
        
        await query.edit_message_text(
            Messages.user_stats(user, violations, is_banned, remaining, is_whitelisted),
            parse_mode="Markdown",
            reply_markup=Keyboards.back_to_menu()
        )
    
    async def _show_top(self, query, context, chat_id: int) -> None:
        """Показывает топ нарушителей."""
        top_list = await self.violation_repo.get_top(chat_id, 10)
        
        # Получаем имена
        names = {}
        for user_id, _ in top_list:
            try:
                member = await context.bot.get_chat_member(chat_id, user_id)
                names[user_id] = member.user.first_name
            except:
                names[user_id] = f"ID {user_id}"
        
        await query.edit_message_text(
            Messages.top_violators(top_list, names),
            parse_mode="Markdown",
            reply_markup=Keyboards.back_to_menu()
        )
    
    async def _show_chat_stats(self, query, context, chat_id: int, days: int) -> None:
        """Показывает статистику чата."""
        stats = await self.stats_repo.get_stats(chat_id, days)
        
        await query.edit_message_text(
            Messages.chat_stats(stats, days),
            parse_mode="Markdown",
            reply_markup=Keyboards.stats_period()
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
                reply_markup=Keyboards.settings_menu()
            )
        else:
            await query.edit_message_text(
                Messages.settings_overview(settings) + "\n\n_Только админы могут менять настройки_",
                parse_mode="Markdown",
                reply_markup=Keyboards.back_to_menu()
            )
    
    async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка настроек."""
        query = update.callback_query
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        data = query.data
        
        # Проверка прав
        is_admin = await self.admin_service.is_chat_admin(context, chat_id, user_id)
        if not is_admin:
            await query.answer("❌ Только админы!", show_alert=True)
            return
        
        await query.answer()
        settings = await self.settings_repo.get(chat_id)
        
        try:
            if data.startswith("settings_"):
                setting_type = data.split("_")[1]
                
                if setting_type == "warning":
                    enabled = settings.get("warning_enabled", True)
                    await query.edit_message_text(
                        "⚠️ *Предупреждения*\n\n"
                        "_Показывать предупреждение перед баном?_",
                        parse_mode="Markdown",
                        reply_markup=Keyboards.warning_toggle(enabled)
                    )
                else:
                    limit_key = f"{setting_type}_limit"
                    window_key = f"{setting_type}_window"
                    await query.edit_message_text(
                        Messages.setting_detail(
                            setting_type, 
                            settings[limit_key], 
                            settings[window_key]
                        ),
                        parse_mode="Markdown",
                        reply_markup=Keyboards.setting_adjust(setting_type, settings[limit_key])
                    )
            
            elif data.startswith("set_"):
                parts = data.split("_")
                setting_type = parts[1]
                action = parts[2]
                
                if setting_type == "warning":
                    new_value = 1 if action == "on" else 0
                    await self.settings_repo.set(chat_id, "warning_enabled", new_value)
                    await query.edit_message_text(
                        "⚠️ *Предупреждения*\n\n"
                        f"{'✅ Включены!' if new_value else '❌ Выключены!'}",
                        parse_mode="Markdown",
                        reply_markup=Keyboards.warning_toggle(bool(new_value))
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
                        Messages.setting_detail(
                            setting_type, 
                            new_value, 
                            settings[f"{setting_type}_window"]
                        ),
                        parse_mode="Markdown",
                        reply_markup=Keyboards.setting_adjust(setting_type, new_value)
                    )
                    
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Settings callback error: {e}")
    
    # ═══════════════════════════════════════════════════════════
    # 🤍 БЕЛЫЙ СПИСОК
    # ═══════════════════════════════════════════════════════════
    
    async def _show_whitelist(self, query, context, chat_id: int) -> None:
        """Показывает белый список."""
        wl = await self.whitelist_repo.get_all(chat_id)
        
        # Получаем имена
        users = []
        for user_id, _ in wl:
            try:
                member = await context.bot.get_chat_member(chat_id, user_id)
                users.append((user_id, member.user.first_name))
            except:
                users.append((user_id, f"ID {user_id}"))
        
        await query.edit_message_text(
            Messages.whitelist_view(len(users)),
            parse_mode="Markdown",
            reply_markup=Keyboards.whitelist_menu(users)
        )
    
    async def handle_whitelist_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка белого списка."""
        query = update.callback_query
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        data = query.data
        
        if data == "whitelist_add_info":
            await query.answer(
                "Ответь на сообщение пользователя командой /trust",
                show_alert=True
            )
            return
        
        # Проверка прав для изменений
        is_admin = await self.admin_service.is_chat_admin(context, chat_id, user_id)
        if not is_admin:
            await query.answer("❌ Только админы!", show_alert=True)
            return
        
        await query.answer()
        
        if data.startswith("trust_"):
            target_id = int(data.split("_")[1])
            await self.whitelist_repo.add(target_id, chat_id, user_id)
            
            try:
                member = await context.bot.get_chat_member(chat_id, target_id)
                user = UserInfo(target_id, member.user.first_name)
            except:
                user = UserInfo(target_id, f"ID {target_id}")
            
            await query.edit_message_text(
                Messages.whitelist_added(user),
                parse_mode="Markdown",
                reply_markup=Keyboards.back_to_menu()
            )
        
        elif data.startswith("untrust_"):
            target_id = int(data.split("_")[1])
            await self.whitelist_repo.remove(target_id, chat_id)
            
            try:
                member = await context.bot.get_chat_member(chat_id, target_id)
                user = UserInfo(target_id, member.user.first_name)
            except:
                user = UserInfo(target_id, f"ID {target_id}")
            
            await query.edit_message_text(
                Messages.whitelist_removed(user),
                parse_mode="Markdown",
                reply_markup=Keyboards.back_to_menu()
            )
