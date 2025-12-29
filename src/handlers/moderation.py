"""
Обработчики модерации (баны, разбаны, прощения).
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.error import BadRequest

from src.ui import Keyboards, Messages
from src.ui.messages import UserInfo
from src.services import BanService, AdminService
from src.database import WhitelistRepository, ViolationRepository

logger = logging.getLogger(__name__)


class ModerationHandlers:
    """Обработчики модерации."""
    
    def __init__(
        self,
        ban_service: BanService,
        admin_service: AdminService,
        whitelist_repo: WhitelistRepository,
        violation_repo: ViolationRepository
    ):
        self.ban_service = ban_service
        self.admin_service = admin_service
        self.whitelist_repo = whitelist_repo
        self.violation_repo = violation_repo
    
    async def handle_moderation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка действий модерации."""
        query = update.callback_query
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        username = query.from_user.username or ""
        data = query.data
        
        # Проверка прав
        can_moderate = await self.admin_service.can_unban(context, chat_id, user_id, username)
        if not can_moderate:
            await query.answer("❌ Только админы!", show_alert=True)
            return
        
        try:
            await query.answer()
        except BadRequest:
            pass
        
        admin_name = query.from_user.first_name
        
        try:
            if data.startswith("unban_"):
                target_id = int(data.split("_")[1])
                await self._handle_unban(query, context, chat_id, target_id, admin_name)
            
            elif data.startswith("pardon_"):
                target_id = int(data.split("_")[1])
                await self._handle_pardon(query, context, chat_id, target_id, admin_name)
            
            elif data.startswith("userinfo_"):
                target_id = int(data.split("_")[1])
                await self._show_user_info(query, context, chat_id, target_id)
            
            elif data == "cancel":
                await query.edit_message_text("❌ Отменено!")
                
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Moderation callback error: {e}")
    
    async def _handle_unban(self, query, context, chat_id: int, target_id: int, admin_name: str) -> None:
        """Разбан пользователя."""
        success = await self.ban_service.remove_ban(context, chat_id, target_id)
        
        try:
            member = await context.bot.get_chat_member(chat_id, target_id)
            user = UserInfo(target_id, member.user.first_name, member.user.username)
        except:
            user = UserInfo(target_id, f"ID {target_id}")
        
        if success:
            await query.edit_message_text(
                Messages.unban_notification(user, admin_name),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("⚠️ Ошибка снятия ограничений")
    
    async def _handle_pardon(self, query, context, chat_id: int, target_id: int, admin_name: str) -> None:
        """Полное прощение пользователя."""
        await self.ban_service.remove_ban(context, chat_id, target_id)
        await self.ban_service.pardon_user(target_id, chat_id)
        
        try:
            member = await context.bot.get_chat_member(chat_id, target_id)
            user = UserInfo(target_id, member.user.first_name, member.user.username)
        except:
            user = UserInfo(target_id, f"ID {target_id}")
        
        await query.edit_message_text(
            Messages.pardon_notification(user, admin_name),
            parse_mode="Markdown"
        )
    
    async def _show_user_info(self, query, context, chat_id: int, target_id: int) -> None:
        """Показывает информацию о пользователе."""
        violations, _ = await self.violation_repo.get_info(target_id, chat_id)
        is_banned = await self.ban_service.is_banned(target_id, chat_id)
        remaining = await self.ban_service.get_remaining_time(target_id, chat_id)
        is_whitelisted = await self.whitelist_repo.is_whitelisted(target_id, chat_id)
        
        try:
            member = await context.bot.get_chat_member(chat_id, target_id)
            user = UserInfo(target_id, member.user.first_name, member.user.username)
        except:
            user = UserInfo(target_id, f"ID {target_id}")
        
        await query.edit_message_text(
            Messages.user_stats(user, violations, is_banned, remaining, is_whitelisted),
            parse_mode="Markdown",
            reply_markup=Keyboards.user_actions(target_id, is_banned, is_whitelisted)
        )
    
    # ═══════════════════════════════════════════════════════════
    # 📋 КОМАНДЫ
    # ═══════════════════════════════════════════════════════════
    
    async def trust_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /trust — добавить в белый список."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await self.admin_service.is_chat_admin(context, chat_id, user_id):
            await update.message.reply_text("❌ Только админы!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "ℹ️ *Как добавить в белый список:*\n\n"
                "Ответь на сообщение пользователя\n"
                "командой /trust",
                parse_mode="Markdown"
            )
            return
        
        target = update.message.reply_to_message.from_user
        await self.whitelist_repo.add(target.id, chat_id, user_id)
        
        user = UserInfo(target.id, target.first_name, target.username)
        await update.message.reply_text(
            Messages.whitelist_added(user),
            parse_mode="Markdown"
        )
    
    async def untrust_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /untrust — убрать из белого списка."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await self.admin_service.is_chat_admin(context, chat_id, user_id):
            await update.message.reply_text("❌ Только админы!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "ℹ️ Ответь на сообщение пользователя командой /untrust"
            )
            return
        
        target = update.message.reply_to_message.from_user
        removed = await self.whitelist_repo.remove(target.id, chat_id)
        
        if removed:
            user = UserInfo(target.id, target.first_name, target.username)
            await update.message.reply_text(
                Messages.whitelist_removed(user),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("ℹ️ Пользователь не был в белом списке")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /stats — статистика пользователя."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        violations, _ = await self.violation_repo.get_info(user_id, chat_id)
        is_banned = await self.ban_service.is_banned(user_id, chat_id)
        remaining = await self.ban_service.get_remaining_time(user_id, chat_id)
        is_whitelisted = await self.whitelist_repo.is_whitelisted(user_id, chat_id)
        
        user = UserInfo(user_id, update.effective_user.first_name)
        
        await update.message.reply_text(
            Messages.user_stats(user, violations, is_banned, remaining, is_whitelisted),
            parse_mode="Markdown",
            reply_markup=Keyboards.back_to_menu()
        )
    
    async def top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /top — топ нарушителей."""
        chat_id = update.effective_chat.id
        top_list = await self.violation_repo.get_top(chat_id, 10)
        
        names = {}
        for uid, _ in top_list:
            try:
                member = await context.bot.get_chat_member(chat_id, uid)
                names[uid] = member.user.first_name
            except:
                names[uid] = f"ID {uid}"
        
        await update.message.reply_text(
            Messages.top_violators(top_list, names),
            parse_mode="Markdown",
            reply_markup=Keyboards.back_to_menu()
        )
