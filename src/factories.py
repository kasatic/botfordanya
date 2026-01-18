"""
Фабрики для создания сложных объектов с зависимостями.

Фабрики инкапсулируют логику создания объектов и управления их зависимостями,
делая код более тестируемым и поддерживаемым.
"""

import logging
from typing import Optional
from telegram.ext import Application

from src.core.config import config
from src.container import ServiceContainer
from src.database import (
    Database,
    SpamRepository,
    ViolationRepository,
    WhitelistRepository,
    ChatSettingsRepository,
    BanStatsRepository,
    SteamLinkRepository,
)
from src.services import (
    SpamDetector,
    BanService,
    AdminService,
    DotaService,
    OpenDotaService,
    ShameService,
    DatabaseCleanupService,
)

logger = logging.getLogger(__name__)


class DatabaseFactory:
    """Фабрика для создания и инициализации базы данных."""

    @staticmethod
    async def create(db_path: str) -> Database:
        """
        Создает и инициализирует базу данных.

        Args:
            db_path: Путь к файлу базы данных

        Returns:
            Инициализированный экземпляр Database
        """
        db = Database(db_path)
        await db.init()  # Миграции применяются автоматически
        logger.info(f"✅ Database initialized at {db_path}")
        return db


class RepositoryFactory:
    """Фабрика для создания репозиториев."""

    @staticmethod
    def create_all(db: Database) -> dict:
        """
        Создает все репозитории.

        Args:
            db: Экземпляр базы данных

        Returns:
            Словарь с репозиториями
        """
        repos = {
            "spam": SpamRepository(db),
            "violation": ViolationRepository(db),
            "whitelist": WhitelistRepository(db),
            "settings": ChatSettingsRepository(db),
            "stats": BanStatsRepository(db),
            "steam": SteamLinkRepository(db),
        }
        logger.info(f"✅ Created {len(repos)} repositories")
        return repos


class ServiceFactory:
    """Фабрика для создания сервисов с зависимостями."""

    @staticmethod
    def create_spam_detector(
        spam_repo: SpamRepository, whitelist_repo: WhitelistRepository, settings_repo: ChatSettingsRepository
    ) -> SpamDetector:
        """Создает SpamDetector с зависимостями."""
        return SpamDetector(spam_repo, whitelist_repo, settings_repo)

    @staticmethod
    def create_ban_service(
        violation_repo: ViolationRepository, spam_repo: SpamRepository, stats_repo: BanStatsRepository
    ) -> BanService:
        """Создает BanService с зависимостями."""
        return BanService(violation_repo, spam_repo, stats_repo)

    @staticmethod
    def create_admin_service(admin_file: str) -> AdminService:
        """Создает AdminService."""
        return AdminService(admin_file)

    @staticmethod
    def create_dota_service(users_file: str) -> DotaService:
        """Создает DotaService."""
        return DotaService(users_file)

    @staticmethod
    async def create_opendota_service() -> OpenDotaService:
        """Создает и инициализирует OpenDotaService."""
        service = OpenDotaService(steam_api_key=config.steam_api_key)
        await service.init()
        logger.info("✅ OpenDotaService initialized")
        if config.steam_api_key:
            logger.info("✅ Steam API key configured - vanity URLs will work")
        else:
            logger.warning("⚠️ Steam API key not configured - vanity URLs may not resolve correctly")
        return service

    @staticmethod
    def create_shame_service(
        opendota: OpenDotaService, steam_repo: SteamLinkRepository, application: Application
    ) -> ShameService:
        """Создает ShameService с зависимостями."""
        return ShameService(opendota, steam_repo, application)

    @staticmethod
    def create_cleanup_service(
        spam_repo: SpamRepository, interval_hours: int = 1, retention_hours: int = 24
    ) -> DatabaseCleanupService:
        """Создает DatabaseCleanupService."""
        return DatabaseCleanupService(
            spam_repo=spam_repo, interval_hours=interval_hours, retention_hours=retention_hours
        )


class ContainerFactory:
    """Фабрика для настройки DI контейнера."""

    @staticmethod
    async def create_configured_container() -> ServiceContainer:
        """
        Создает и настраивает DI контейнер со всеми зависимостями.

        Returns:
            Настроенный ServiceContainer
        """
        from src.container import ServiceLifetime

        container = ServiceContainer()

        # 1. База данных (singleton)
        db = await DatabaseFactory.create(config.files.database)
        container.register_instance(Database, db)

        # 2. Репозитории (singleton)
        repos = RepositoryFactory.create_all(db)
        container.register_instance(SpamRepository, repos["spam"])
        container.register_instance(ViolationRepository, repos["violation"])
        container.register_instance(WhitelistRepository, repos["whitelist"])
        container.register_instance(ChatSettingsRepository, repos["settings"])
        container.register_instance(BanStatsRepository, repos["stats"])

        # Инициализируем таблицу Steam
        await repos["steam"].init_table()
        container.register_instance(SteamLinkRepository, repos["steam"])

        # 3. Сервисы (singleton)
        container.register(
            SpamDetector,
            lambda: ServiceFactory.create_spam_detector(
                container.get(SpamRepository), container.get(WhitelistRepository), container.get(ChatSettingsRepository)
            ),
            ServiceLifetime.SINGLETON,
        )

        container.register(
            BanService,
            lambda: ServiceFactory.create_ban_service(
                container.get(ViolationRepository), container.get(SpamRepository), container.get(BanStatsRepository)
            ),
            ServiceLifetime.SINGLETON,
        )

        container.register(
            AdminService, lambda: ServiceFactory.create_admin_service(config.files.admins), ServiceLifetime.SINGLETON
        )

        container.register(
            DotaService, lambda: ServiceFactory.create_dota_service(config.files.dota_users), ServiceLifetime.SINGLETON
        )

        # OpenDotaService требует async init
        opendota = await ServiceFactory.create_opendota_service()
        container.register_instance(OpenDotaService, opendota)

        logger.info(f"✅ DI Container configured with {len(container.get_registered_services())} services")

        return container

    @staticmethod
    def register_application_services(container: ServiceContainer, application: Application) -> None:
        """
        Регистрирует сервисы, которые зависят от Application.

        Вызывается после создания Application.

        Args:
            container: DI контейнер
            application: Telegram Application
        """
        from src.container import ServiceLifetime

        # ShameService зависит от Application
        container.register(
            ShameService,
            lambda: ServiceFactory.create_shame_service(
                container.get(OpenDotaService), container.get(SteamLinkRepository), application
            ),
            ServiceLifetime.SINGLETON,
        )

        # DatabaseCleanupService
        container.register(
            DatabaseCleanupService,
            lambda: ServiceFactory.create_cleanup_service(
                container.get(SpamRepository), interval_hours=1, retention_hours=24
            ),
            ServiceLifetime.SINGLETON,
        )

        logger.info("✅ Application-dependent services registered")
