"""
DEPRECATED: Используйте src.core.config вместо этого модуля.

Этот файл оставлен для обратной совместимости.
"""

import warnings

# Импортируем из нового расположения
from src.core.config import (
    BanConfig,
    Config,
    Files,
    SpamLimits,
    config,
    get_config,
)

warnings.warn("src.config is deprecated, use src.core.config instead", DeprecationWarning, stacklevel=2)

__all__ = [
    "Config",
    "SpamLimits",
    "BanConfig",
    "Files",
    "get_config",
    "config",
]
