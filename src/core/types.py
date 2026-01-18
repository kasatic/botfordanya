"""
Type aliases для улучшения читаемости кода.
"""

from typing import NewType

# Telegram типы
UserId = NewType("UserId", int)
ChatId = NewType("ChatId", int)
MessageId = NewType("MessageId", int)

# Steam типы
AccountId = NewType("AccountId", int)
SteamId64 = NewType("SteamId64", int)
MatchId = NewType("MatchId", int)

# Временные типы
Timestamp = NewType("Timestamp", str)  # ISO format
Minutes = NewType("Minutes", int)
Seconds = NewType("Seconds", int)

# Хеши
ContentHash = NewType("ContentHash", str)
