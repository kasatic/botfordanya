"""
Доменные исключения.

Все исключения бизнес-логики должны наследоваться от DomainException.
"""


class DomainException(Exception):
    """Базовое исключение доменного слоя."""

    def __init__(self, message: str, code: str = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__


class UserNotFound(DomainException):
    """Пользователь не найден."""

    def __init__(self, user_id: int):
        super().__init__(f"User with ID {user_id} not found", code="USER_NOT_FOUND")
        self.user_id = user_id


class InvalidAccountId(DomainException):
    """Некорректный Account ID."""

    def __init__(self, account_id: str):
        super().__init__(f"Invalid Account ID: {account_id}", code="INVALID_ACCOUNT_ID")
        self.account_id = account_id


class InvalidChatId(DomainException):
    """Некорректный Chat ID."""

    def __init__(self, chat_id: int):
        super().__init__(f"Invalid Chat ID: {chat_id}", code="INVALID_CHAT_ID")
        self.chat_id = chat_id


class BanNotFound(DomainException):
    """Бан не найден."""

    def __init__(self, user_id: int, chat_id: int):
        super().__init__(f"Ban not found for user {user_id} in chat {chat_id}", code="BAN_NOT_FOUND")
        self.user_id = user_id
        self.chat_id = chat_id


class AlreadyBanned(DomainException):
    """Пользователь уже забанен."""

    def __init__(self, user_id: int, chat_id: int, until: str):
        super().__init__(f"User {user_id} is already banned in chat {chat_id} until {until}", code="ALREADY_BANNED")
        self.user_id = user_id
        self.chat_id = chat_id
        self.until = until


class NotBanned(DomainException):
    """Пользователь не забанен."""

    def __init__(self, user_id: int, chat_id: int):
        super().__init__(f"User {user_id} is not banned in chat {chat_id}", code="NOT_BANNED")
        self.user_id = user_id
        self.chat_id = chat_id


class InvalidSpamType(DomainException):
    """Некорректный тип спама."""

    def __init__(self, spam_type: str):
        super().__init__(f"Invalid spam type: {spam_type}", code="INVALID_SPAM_TYPE")
        self.spam_type = spam_type


class WhitelistError(DomainException):
    """Ошибка работы с белым списком."""

    pass


class ViolationError(DomainException):
    """Ошибка работы с нарушениями."""

    pass
