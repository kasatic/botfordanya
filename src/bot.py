"""
Главный модуль бота с graceful shutdown и Dependency Injection.
"""

import asyncio
import logging
import signal

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from src.container import ServiceContainer
from src.core.config import config
from src.database import (
    BanStatsRepository,
    ChatSettingsRepository,
    Database,
    SteamLinkRepository,
    ViolationRepository,
    WhitelistRepository,
)
from src.factories import ContainerFactory
from src.handlers import MenuHandlers, ModerationHandlers, register_spam_handlers
from src.handlers.dota import DotaHandlers
from src.services import AdminService, BanService, DotaService, SpamDetector
from src.services.database_cleanup import DatabaseCleanupService
from src.services.opendota_service import OpenDotaService
from src.services.shame_service import ShameService

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


async def error_handler(update, context):
    """Глобальный обработчик ошибок."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Логируем информацию об update если доступна
    if update:
        logger.error(f"Update that caused error: {update}")


class Bot:
    """
    Главный класс бота с Dependency Injection.

    Использует DI контейнер для управления зависимостями,
    что делает код более тестируемым и поддерживаемым.
    """

    def __init__(self):
        self.application: Application = None
        self.container: ServiceContainer = None
        self._shutdown_event = asyncio.Event()

    async def setup(self) -> None:
        """
        Инициализация бота с использованием DI контейнера.

        Все зависимости создаются и регистрируются через фабрики,
        что обеспечивает единую точку конфигурации.
        """
        # Создаем и настраиваем DI контейнер
        self.container = await ContainerFactory.create_configured_container()

        # Создаем Telegram Application
        self.application = Application.builder().token(config.token).build()

        # Регистрируем сервисы, зависящие от Application
        ContainerFactory.register_application_services(self.container, self.application)

        # Получаем сервисы из контейнера
        spam_detector = self.container.get(SpamDetector)
        ban_service = self.container.get(BanService)
        admin_service = self.container.get(AdminService)
        dota_service = self.container.get(DotaService)
        opendota = self.container.get(OpenDotaService)

        # Получаем репозитории
        whitelist_repo = self.container.get(WhitelistRepository)
        violation_repo = self.container.get(ViolationRepository)
        settings_repo = self.container.get(ChatSettingsRepository)
        stats_repo = self.container.get(BanStatsRepository)
        steam_repo = self.container.get(SteamLinkRepository)

        # Создаем обработчики (handlers не регистрируются в контейнере,
        # так как они не переиспользуются и создаются один раз)
        menu = MenuHandlers(
            ban_service,
            admin_service,
            whitelist_repo,
            violation_repo,
            settings_repo,
            stats_repo,
            steam_repo=steam_repo,
            opendota=opendota,
        )

        moderation = ModerationHandlers(ban_service, admin_service, whitelist_repo, violation_repo)

        dota_handlers = DotaHandlers(opendota, steam_repo)

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

        # Callback handlers (порядок важен!)
        self.application.add_handler(
            CallbackQueryHandler(menu.handle_menu_callback, pattern="^menu_|^chatstats_|^ignore$")
        )
        self.application.add_handler(CallbackQueryHandler(menu.handle_dota_callback, pattern="^dota_"))
        self.application.add_handler(
            CallbackQueryHandler(menu.handle_settings_callback, pattern="^settings_|^setting_")
        )
        self.application.add_handler(CallbackQueryHandler(menu.handle_whitelist_callback, pattern="^whitelist_"))
        self.application.add_handler(
            CallbackQueryHandler(moderation.handle_moderation_callback, pattern="^action_|^user_info_")
        )

        # Спам-хендлеры
        register_spam_handlers(self.application, spam_detector, ban_service, admin_service, dota_service)

        # Глобальный error handler
        self.application.add_error_handler(error_handler)

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

        # Регистрируем команды в меню Telegram
        await self._set_commands()

        await self.application.updater.start_polling()

        # Запускаем фоновые сервисы из контейнера
        shame_service = self.container.get(ShameService)
        await shame_service.start()

        cleanup_service = self.container.get(DatabaseCleanupService)
        await cleanup_service.start()

        await self._shutdown_event.wait()

    async def _set_commands(self) -> None:
        """Регистрирует команды в меню Telegram."""
        commands = [
            BotCommand("menu", "🏠 Главное меню"),
            BotCommand("stats", "📊 Моя статистика"),
            BotCommand("top", "🏆 Топ нарушителей"),
            BotCommand("settings", "⚙️ Настройки чата"),
            # Dota 2
            BotCommand("link", "🔗 Привязать Steam"),
            BotCommand("game", "🎮 Проверить в игре ли"),
            BotCommand("last", "📈 Статистика последнего матча"),
            BotCommand("lastgame", "📊 Краткая инфа о матче"),
            BotCommand("profile", "👤 Мой профиль Dota"),
            BotCommand("toxic", "☢️ Анализ токсичности"),
            BotCommand("shame", "😈 Подписка на позор"),
            # Модерация
            BotCommand("trust", "🤍 Добавить в белый список"),
            BotCommand("untrust", "⛔ Убрать из белого списка"),
            BotCommand("help", "❓ Помощь"),
        ]

        await self.application.bot.set_my_commands(commands)
        logger.info("📋 Bot commands registered")

    async def shutdown(self) -> None:
        """
        Graceful shutdown с очисткой всех ресурсов.

        Останавливает сервисы в правильном порядке:
        1. Фоновые задачи (cleanup, shame)
        2. HTTP сессии (OpenDota)
        3. База данных
        4. Telegram Application
        """
        logger.info("🛑 Shutting down...")

        if self.container:
            # Останавливаем фоновые сервисы
            cleanup_service = self.container.try_get(DatabaseCleanupService)
            if cleanup_service:
                await cleanup_service.stop()

            shame_service = self.container.try_get(ShameService)
            if shame_service:
                await shame_service.stop()

            # Закрываем HTTP сессии
            opendota = self.container.try_get(OpenDotaService)
            if opendota:
                await opendota.close()

            # Закрываем базу данных
            db = self.container.try_get(Database)
            if db:
                await db.close()

        # Останавливаем Telegram Application
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
