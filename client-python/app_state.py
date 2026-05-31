"""Modelo de estado de la aplicación: enums de modo y sesión de usuario."""

from enum import Enum
from typing import Dict, List, Optional, Set


class AppState(Enum):
    """Estado de alto nivel de la aplicación."""
    AUTH = "auth"   # Pantalla de login / registro
    LIVE = "live"   # Chat activo
    EXIT = "exit"   # Cierre solicitado


class AuthMode(Enum):
    """Subpantalla dentro del estado AUTH."""
    MENU     = "menu"
    LOGIN    = "login"
    REGISTER = "register"


class LiveMode(Enum):
    """Subpantalla dentro del estado LIVE."""
    NAVIGATION = "navigation"   # Navegando la lista de chats
    INPUT      = "input"        # Escribiendo un mensaje
    NEW_CHAT   = "new_chat"     # Formulario de nuevo chat


class AppSession:
    """Mantiene el estado de la sesión activa: usuario, chats y mensajes en memoria."""

    def __init__(self):
        """Inicializa la sesión vacía (sin usuario autenticado)."""
        self.username: Optional[str] = None
        self.chats: List[str] = []
        self.messages: Dict[str, List] = {}
        self.active_chat: Optional[str] = None
        self.unread_chats: Set[str] = set()

    def set_user(self, username: str):
        """Establece el nombre del usuario autenticado."""
        self.username = username

    def load_conversations(self, conversations: Dict[str, List]):
        """Carga el mapa de conversaciones en sesión, ordenando cada chat por fecha.

        Los chats se ordenan de más reciente a más antiguo según el último mensaje.
        """
        def _sent(msg):
            return msg.get('sent', '') if isinstance(msg, dict) else ''

        self.messages = {chat: sorted(msgs, key=_sent) for chat, msgs in conversations.items()}

        def _last_date(chat):
            msgs = self.messages[chat]
            return (1, _sent(msgs[-1])) if msgs else (0, '')

        self.chats = sorted(conversations.keys(), key=_last_date, reverse=True)
        if self.chats:
            self.active_chat = self.chats[0]

    def add_message(self, chat: str, message):
        """Añade un mensaje al chat indicado y lo mueve al inicio de la lista de chats."""
        if chat not in self.messages:
            self.messages[chat] = []
        self.messages[chat].append(message)
        if chat in self.chats:
            self.chats.remove(chat)
        self.chats.insert(0, chat)

    def create_chat(self, chat_name: str):
        """Registra un chat nuevo (vacío) en la sesión y lo convierte en activo."""
        if chat_name not in self.chats:
            self.chats.insert(0, chat_name)
            self.messages[chat_name] = []
            self.active_chat = chat_name

    def get_chat_messages(self, chat: str) -> List:
        """Devuelve la lista de mensajes del chat, o [] si no existe."""
        return self.messages.get(chat, [])

    def mark_unread(self, chat: str):
        """Marca un chat como con mensajes no leídos (muestra el indicador ◆)."""
        self.unread_chats.add(chat)

    def mark_read(self, chat: str):
        """Elimina la marca de no leído de un chat."""
        self.unread_chats.discard(chat)

    def is_authenticated(self) -> bool:
        """Indica si hay un usuario con sesión iniciada."""
        return self.username is not None

    def clear(self):
        """Resetea la sesión completamente (usado al cerrar sesión)."""
        self.username = None
        self.chats = []
        self.messages = {}
        self.active_chat = None
        self.unread_chats = set()
