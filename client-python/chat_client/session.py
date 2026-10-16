"""State of the running client: which screen is shown and the in-memory conversations."""

from enum import Enum
from typing import Any

Message = dict[str, Any]
"""A message: ``author``, ``contents``, ``sent`` (``yyyy-MM-dd HH:mm:ss``), ``chatname``."""


class AppState(Enum):
    """High-level state of the application."""

    AUTH = "auth"
    LIVE = "live"
    EXIT = "exit"


class AuthMode(Enum):
    """Screen inside :attr:`AppState.AUTH`."""

    MENU = "menu"
    LOGIN = "login"
    REGISTER = "register"


class LiveMode(Enum):
    """Screen inside :attr:`AppState.LIVE`."""

    NAVIGATION = "navigation"
    INPUT = "input"
    NEW_CHAT = "new_chat"


def sent_time(message: Any) -> str:
    """Send time of a message, ``""`` if it has none (older or local-only entries)."""
    return message.get("sent", "") if isinstance(message, dict) else ""


class AppSession:
    """The logged-in user, their chats and the messages loaded in memory."""

    def __init__(self) -> None:
        self.username: str | None = None
        self.chats: list[str] = []
        self.messages: dict[str, list[Message]] = {}
        self.active_chat: str | None = None
        self.unread_chats: set[str] = set()

    def set_user(self, username: str) -> None:
        """Records the authenticated user."""
        self.username = username

    def is_authenticated(self) -> bool:
        """Whether a user is logged in."""
        return self.username is not None

    def load_conversations(self, conversations: dict[str, list[Message]]) -> None:
        """Replaces the conversations; chats are ordered by their latest message, newest first.

        Chats without messages go last, and the first one becomes the active chat.
        """
        self.messages = {chat: sorted(msgs, key=sent_time) for chat, msgs in conversations.items()}

        def latest(chat: str) -> tuple[int, str]:
            msgs = self.messages[chat]
            return (1, sent_time(msgs[-1])) if msgs else (0, "")

        self.chats = sorted(self.messages, key=latest, reverse=True)
        if self.chats:
            self.active_chat = self.chats[0]

    def add_message(self, chat: str, message: Message) -> None:
        """Appends a message to ``chat`` (creating it) and moves the chat to the top."""
        self.messages.setdefault(chat, []).append(message)
        if chat in self.chats:
            self.chats.remove(chat)
        self.chats.insert(0, chat)

    def create_chat(self, chat_name: str) -> None:
        """Adds an empty chat and makes it the active one (no-op if it exists)."""
        if chat_name not in self.chats:
            self.chats.insert(0, chat_name)
            self.messages[chat_name] = []
            self.active_chat = chat_name

    def get_chat_messages(self, chat: str) -> list[Message]:
        """Messages of ``chat``, ``[]`` if unknown."""
        return self.messages.get(chat, [])

    def mark_unread(self, chat: str) -> None:
        """Flags ``chat`` as having unread messages."""
        self.unread_chats.add(chat)

    def mark_read(self, chat: str) -> None:
        """Clears the unread flag of ``chat``."""
        self.unread_chats.discard(chat)

    def clear(self) -> None:
        """Forgets everything (used on logout)."""
        self.__init__()
