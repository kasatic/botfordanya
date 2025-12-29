"""
Обработчики спама.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from src.ui import Keyboards, Messages
from src.ui.messages import UserInfo
from src.services import SpamDetector, BanService, AdminService, DotaService
from src.services.spam_detector import SpamType

logger = logging.getLogger(__name__)


class SpamHandlers:
    """Обработчики спама."""
    
    def __init__(
        self, 
        spam_detector: SpamDetector, 
        ban_service: BanService,
        admin_service: AdminService,
        dota_service: DotaService
    ):
        self.spam_detector = spam_detector
        self.ban_service = ban_service
        self.admin_service = admin_service
        self.dota_service = dota_service
    
    async def _process_spam(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        spam_type: SpamType,
        content_hash: str = None
    ) -> None:
        """Общая логика обработки спама."""
        if update.effective_chat.type not in ("supergroup", "group"):
            return
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Админы чата не банятся
        if await self.admin_service.is_chat_admin(context, chat_id, user_id):
            return
        
        # Проверяем на спам
        result = await self.spam_detector.check(user_id, chat_id, spam_type, content_hash)
        
        user = UserInfo(
            user_id=user_id,
            name=update.effective_user.first_name,
            username=update.effective_user.username
        )
        
        # Предупреждение
        if result.is_warning:
            await context.bot.send_message(
                chat_id,
                Messages.warning(user, result.count, result.limit, result.reason, spam_type.value),
                parse_mode="Markdown",
                reply_to_message_id=update.message.message_id
            )
            return
        
        if not result.is_spam:
            return
        
        # Удаляем сообщение
        try:
            await context.bot.delete_message(chat_id, update.message.message_id)
        except Exception as e:
            logger.warning(f"Cannot delete message: {e}")
        
        # Если уже забанен — просто удаляем
        if await self.ban_service.is_banned(user_id, chat_id):
            return
        
        # Баним
        success, violation_count, ban_minutes = await self.ban_service.apply_ban(
            context, chat_id, user_id, 
            ban_type=spam_type.value,
            reason=f"{result.count} {result.reason}"
        )
        
        if success:
            text = Messages.ban_notification(
                user, violation_count, ban_minutes,
                result.count, result.reason, spam_type.value
            )
        else:
            text = (
                f"⚖️ *{user.name}* превысил лимит ({result.count} {result.reason})\n"
                f"⚠️ Записано, но ограничить не могу (админ?)"
            )
        
        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="Markdown",
            reply_markup=Keyboards.ban_actions(user_id)
        )
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._process_spam(update, context, SpamType.STICKER)
    
    async def handle_animation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._process_spam(update, context, SpamType.ANIMATION)
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        unique_id = update.message.photo[-1].file_unique_id
        await self._process_spam(update, context, SpamType.PHOTO, unique_id)
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        unique_id = update.message.video.file_unique_id
        await self._process_spam(update, context, SpamType.VIDEO, unique_id)
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat.type not in ("supergroup", "group"):
            return
        
        text = update.message.text
        
        # Проверка на "го дота"
        if self.dota_service.check_trigger(text):
            mention_text = self.dota_service.get_mention_text()
            if mention_text:
                await update.message.reply_text(mention_text)
        
        # Проверка на спам
        await self._process_spam(update, context, SpamType.TEXT, text)


def register_spam_handlers(
    application,
    spam_detector: SpamDetector,
    ban_service: BanService,
    admin_service: AdminService,
    dota_service: DotaService
) -> None:
    """Регистрирует обработчики спама."""
    handlers = SpamHandlers(spam_detector, ban_service, admin_service, dota_service)
    
    application.add_handler(MessageHandler(filters.Sticker.ALL, handlers.handle_sticker))
    application.add_handler(MessageHandler(filters.ANIMATION, handlers.handle_animation))
    application.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    application.add_handler(MessageHandler(filters.VIDEO, handlers.handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))
