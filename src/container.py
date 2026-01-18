"""
Dependency Injection Container для управления зависимостями бота.

Поддерживает:
- Singleton паттерн (один экземпляр на весь контейнер)
- Factory паттерн (новый экземпляр при каждом запросе)
- Автоматическое разрешение зависимостей
- Ленивую инициализацию
"""

import logging
from typing import Any, Callable, Dict, Optional, TypeVar, Type
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Время жизни сервиса."""

    SINGLETON = "singleton"  # Один экземпляр на весь контейнер
    TRANSIENT = "transient"  # Новый экземпляр при каждом запросе


class ServiceDescriptor:
    """Описание зарегистрированного сервиса."""

    def __init__(self, service_type: Type, factory: Callable, lifetime: ServiceLifetime):
        self.service_type = service_type
        self.factory = factory
        self.lifetime = lifetime
        self.instance: Optional[Any] = None


class ServiceContainer:
    """
    Контейнер для управления зависимостями.

    Пример использования:

    ```python
    # Создание контейнера
    container = ServiceContainer()

    # Регистрация singleton
    container.register(
        Database,
        lambda: Database("bot.db"),
        lifetime=ServiceLifetime.SINGLETON
    )

    # Регистрация с зависимостями
    container.register(
        BanService,
        lambda: BanService(
            violation_repo=container.get(ViolationRepository),
            spam_repo=container.get(SpamRepository),
            stats_repo=container.get(BanStatsRepository)
        ),
        lifetime=ServiceLifetime.SINGLETON
    )

    # Получение сервиса
    ban_service = container.get(BanService)
    ```
    """

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._resolving: set = set()  # Для обнаружения циклических зависимостей

    def register(
        self, service_type: Type[T], factory: Callable[[], T], lifetime: ServiceLifetime = ServiceLifetime.SINGLETON
    ) -> None:
        """
        Регистрирует сервис в контейнере.

        Args:
            service_type: Тип сервиса (класс)
            factory: Функция для создания экземпляра
            lifetime: Время жизни сервиса (SINGLETON или TRANSIENT)

        Example:
            container.register(
                Database,
                lambda: Database("bot.db"),
                ServiceLifetime.SINGLETON
            )
        """
        if service_type in self._services:
            logger.warning(f"⚠️ Service {service_type.__name__} is already registered. Overwriting.")

        descriptor = ServiceDescriptor(service_type, factory, lifetime)
        self._services[service_type] = descriptor

        logger.debug(f"✅ Registered {service_type.__name__} as {lifetime.value}")

    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """
        Регистрирует уже созданный экземпляр как singleton.

        Args:
            service_type: Тип сервиса
            instance: Готовый экземпляр

        Example:
            db = Database("bot.db")
            container.register_instance(Database, db)
        """
        descriptor = ServiceDescriptor(service_type, lambda: instance, ServiceLifetime.SINGLETON)
        descriptor.instance = instance
        self._services[service_type] = descriptor

        logger.debug(f"✅ Registered instance of {service_type.__name__}")

    def get(self, service_type: Type[T]) -> T:
        """
        Получает экземпляр сервиса из контейнера.

        Args:
            service_type: Тип запрашиваемого сервиса

        Returns:
            Экземпляр сервиса

        Raises:
            KeyError: Если сервис не зарегистрирован
            RuntimeError: Если обнаружена циклическая зависимость

        Example:
            ban_service = container.get(BanService)
        """
        if service_type not in self._services:
            raise KeyError(
                f"❌ Service {service_type.__name__} is not registered. "
                f"Available services: {', '.join(s.__name__ for s in self._services.keys())}"
            )

        # Проверка циклических зависимостей
        if service_type in self._resolving:
            raise RuntimeError(f"❌ Circular dependency detected while resolving {service_type.__name__}")

        descriptor = self._services[service_type]

        # Singleton: возвращаем существующий экземпляр или создаем новый
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if descriptor.instance is None:
                self._resolving.add(service_type)
                try:
                    descriptor.instance = descriptor.factory()
                    logger.debug(f"✅ Created singleton instance of {service_type.__name__}")
                finally:
                    self._resolving.discard(service_type)
            return descriptor.instance

        # Transient: всегда создаем новый экземпляр
        else:
            self._resolving.add(service_type)
            try:
                instance = descriptor.factory()
                logger.debug(f"✅ Created transient instance of {service_type.__name__}")
                return instance
            finally:
                self._resolving.discard(service_type)

    def try_get(self, service_type: Type[T]) -> Optional[T]:
        """
        Пытается получить сервис, возвращает None если не зарегистрирован.

        Args:
            service_type: Тип запрашиваемого сервиса

        Returns:
            Экземпляр сервиса или None

        Example:
            opendota = container.try_get(OpenDotaService)
            if opendota:
                # использовать сервис
        """
        try:
            return self.get(service_type)
        except KeyError:
            return None

    def is_registered(self, service_type: Type) -> bool:
        """
        Проверяет, зарегистрирован ли сервис.

        Args:
            service_type: Тип сервиса

        Returns:
            True если сервис зарегистрирован
        """
        return service_type in self._services

    def clear(self) -> None:
        """
        Очищает контейнер, удаляя все зарегистрированные сервисы.

        Полезно для тестов.
        """
        self._services.clear()
        self._resolving.clear()
        logger.debug("🧹 Container cleared")

    def get_registered_services(self) -> list[Type]:
        """
        Возвращает список всех зарегистрированных типов сервисов.

        Returns:
            Список типов сервисов
        """
        return list(self._services.keys())

    def __repr__(self) -> str:
        """Строковое представление контейнера."""
        services = [f"{s.__name__} ({d.lifetime.value})" for s, d in self._services.items()]
        return f"ServiceContainer({len(services)} services: {', '.join(services)})"
