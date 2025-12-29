"""
Главный модуль бота с graceful shutdown.
"""
import logging
import signal
import asyncio
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from src.config import config
from src.database import (
    Database, SpamRepository, ViolationRepository, 
    WhitelistRepository, ChatSettingsRepository, BanStatsRepository
)
from src.database.steam_repository import SteamLinkRepository
from src.services import SpamDetector, BanService, AdminService, DotaService
from src.services.opendota_service import OpenDotaService
from src.services.shame_service import ShameService
from src.handlers import register_spam_handlers, MenuHandlers, ModerationHandlers
from src.handlers.dota import DotaHandlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class Bot:
    """Главный класс бота."""
    
    def __init__(self):
        self.application: Application = None
        self.db: Database = None
        self.opendota: OpenDotaService = None
        self.shame_service: ShameService = None
        self._shutdown_event = asyncio.Event()
    
    async def setup(self) -> None:
        """Инициализация бота."""
        # База данных
        self.db = Database(config.files.database)
        await self.db.init_schema()
        
        # Репозитории
        spam_repo = SpamRepository(self.db)
        violation_repo = ViolationRepository(self.db)
        whitelist_repo = WhitelistRepository(self.db)
        settings_repo = ChatSettingsRepository(self.db)
        stats_repo = BanStatsRepository(self.db)
        steam_repo = SteamLinkRepository(self.db)
        await steam_repo.init_table()
        
        # Сервисы
        spam_detector = SpamDetector(spam_repo, whitelist_repo, settings_repo)
        ban_service = BanService(violation_repo, spam_repo, stats_repo)
        admin_service = AdminService(config.files.admins)
        dota_service = DotaService(config.files.dota_users)
        self.opendota = OpenDotaService()
        
        # Приложение
        self.application = Application.builder().token(config.token).build()
        
        # Обработчики меню
        menu = MenuHandlers(
            ban_service, admin_service, whitelist_repo,
            violation_repo, settings_repo, stats_repo
        )
        
        # Обработчики модерации
        moderation = ModerationHandlers(
            ban_service, admin_service, whitelist_repo, violation_repo
        )
        
        # Обработчики Dota
        dota_handlers = DotaHandlers(self.opendota, steam_repo)
        
        # Команды
        self.application.add_handler(CommandHandler("start", menu.start_command))
        self.application.add_handler(CommandHandler("menu", menu.menu_command))
        self.application.add_handler(CommandHandler("help", menu.start_command))
        self.application.add_handler(CommandHandler("stats", moderation.stats_command))
        self.application.add_handler(CommandHandler("top", moderation.top_command))
        self.application.add_handler(CommandHandler("trust", moderation.trust_command))
        self.application.add_handler(CommandHandler("untrust", moderation.untrust_command))
        
        # Dota команды
        self.application.add_handler(CommandHandler("link", dota_handlers.link_command))
        self.application.add_handler(CommandHandler("unlink", dota_handlers.unlink_command))
        self.application.add_handler(CommandHandler("game", dota_handlers.game_command))
        self.application.add_handler(CommandHandler("lastgame", dota_handlers.lastgame_command))
        self.application.add_handler(CommandHandler("last", dota_handlers.last_command))
        self.application.add_handler(CommandHandler("profile", dota_handlers.profile_command))
        self.application.add_handler(CommandHandler("toxic", dota_handlers.toxic_command))
        self.application.add_handler(CommandHandler("shame", dota_handlers.shame_command))
        
        # Shame service
        self.shame_service = ShameService(self.opendota, steam_repo, self.application)
        
        # Callback handlers (порядок важен!)
        self.application.add_handler(CallbackQueryHandler(
            menu.handle_menu_callback, 
            pattern="^menu_|^chatstats_|^noop$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            menu.handle_settings_callback, 
            pattern="^settings_|^set_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            menu.handle_whitelist_callback, 
            pattern="^whitelist_|^trust_|^untrust_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            moderation.handle_moderation_callback,
            pattern="^unban_|^pardon_|^userinfo_|^cancel$"
        ))
        
        # Спам-хендлеры
        register_spam_handlers(
            self.application, spam_detector, ban_service, 
            admin_service, dota_service
        )
        
        logger.info("✅ Bot initialized")
    
    async def run(self) -> None:
        """Запуск бота."""
        await self.setup()
        
        # Graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown()))
        
        logger.info("🚀 Bot started!")
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        # Запускаем shame service
        await self.shame_service.start()
        
        await self._shutdown_event.wait()
    
    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("🛑 Shutting down...")
        
        if self.shame_service:
            await self.shame_service.stop()
        
        if self.opendota:
            await self.opendota.close()
        
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        self._shutdown_event.set()
        logger.info("👋 Bot stopped")


def main() -> None:
    """Точка входа."""
    try:
        bot = Bot()
        asyncio.run(bot.run())
    except ValueError as e:
        logger.error(f"❌ Config error: {e}")
        exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Interrupted")
    except Exception as e:
        logger.error(f"❌ Fatal: {e}")
        raise


if __name__ == "__main__":
    main()
