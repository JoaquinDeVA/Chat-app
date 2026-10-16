"""What the client does, independent of how it is displayed.

:class:`ChatController` coordinates the server API, the in-memory session and the local copy:
signing in and out, synchronizing history, receiving pushes, sending messages and creating
chats. The curses interface only calls it and draws the result.
"""

import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from . import images
from .api import APIClient, Reply
from .persistence import EPOCH, PersistenceManager
from .session import AppSession, Message

log = logging.getLogger(__name__)

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"  # microseconds, like the server


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


class ChatController:
    """Application logic of the client.

    :param api: Operations against the server.
    :param session: In-memory state (shared with the interface).
    :param persistence: Local copy of the conversations.
    :param clock: Source of timestamps for messages the server did not stamp (tests).
    """

    def __init__(
        self,
        api: APIClient,
        session: AppSession,
        persistence: PersistenceManager,
        clock: Callable[[], str] = _now,
    ):
        self.api = api
        self.session = session
        self.persistence = persistence
        self.clock = clock

    # ── signing in and out ───────────────────────────────────────────────────────────────────

    def sign_in(self, username: str, password: str) -> Reply:
        """Logs in and loads the user's history."""
        reply = self.api.login(username, password)
        if reply.ok:
            self._start_session(username)
        return reply

    def register(self, username: str, password: str) -> Reply:
        """Registers a user and starts their session (the server logs them in itself)."""
        reply = self.api.register(username, password)
        if not reply.ok:
            return reply
        login_reply = self.api.net.recv(timeout=5)  # the second reply of a registration
        if not (isinstance(login_reply, dict) and (login_reply.get("processed") or login_reply.get("code") == 1)):
            return Reply(False, "Registered, but the automatic login failed: log in manually")
        self._start_session(username)
        return reply

    def _start_session(self, username: str) -> None:
        self.session.set_user(username)
        self.sync()

    def sign_out(self) -> None:
        """Logs out, saves the conversations and clears the session."""
        if self.session.is_authenticated():
            self.api.logout()
            self.persistence.save_user_conversations(self.session.username, self.session.messages)

    # ── synchronization ──────────────────────────────────────────────────────────────────────

    def sync(self) -> None:
        """Loads the local copy and asks the server for everything newer than it.

        If this device has never synchronized, the (possibly stale) local files are ignored and the
        whole history is requested.
        """
        username = self.session.username
        since = self.persistence.load_last_sync(username)
        conversations = {} if since == EPOCH else self.persistence.load_user_conversations(username)

        self.api.net.drain()  # nothing received before this point answers the request below
        reply = self.api.load_delta(since)
        if reply.ok:
            for chat, new_messages in reply.data.get("conversations", {}).items():
                known = conversations.setdefault(chat, [])
                known.extend(self._store_images(m) for m in new_messages if isinstance(m, dict))

        self.session.load_conversations(conversations)
        self.persistence.save_user_conversations(username, self.session.messages)

    def _store_images(self, message: Message) -> Message:
        """Saves the picture of a message received in wire format and swaps in its reference."""
        contents = message.get("contents", "")
        if images.is_wire_format(contents):
            reference = images.decode_and_save(contents, self.persistence.images_dir(self.session.username))
            return {**message, "contents": reference}
        return message

    # ── incoming ─────────────────────────────────────────────────────────────────────────────

    def poll(self) -> bool:
        """Applies every push received since the last call.

        :return: Whether the screen needs to be redrawn.
        """
        changed = False
        for message in self.api.net.drain():
            if isinstance(message, dict) and "chatname" in message:
                if "author" in message:
                    changed |= self.apply_push(message)
                else:
                    changed |= self.apply_new_chat(message)
        return changed

    def apply_push(self, message: Message) -> bool:
        """Stores a message pushed by the server and flags its chat as unread if it is not open."""
        chat = message["chatname"]
        message = self._store_images(message)
        self.session.add_message(chat, message)
        self.persistence.update_user_chat(self.session.username, chat, self.session.messages[chat])
        if chat != self.session.active_chat:
            self.session.mark_unread(chat)
        return True

    def apply_new_chat(self, notice: dict[str, Any]) -> bool:
        """Adds a chat the server told us we now belong to. Returns whether anything changed."""
        chat = notice.get("chatname")
        if not chat or chat in self.session.chats:
            return False
        self.session.chats.insert(0, chat)
        self.session.messages[chat] = []
        self.persistence.update_user_chat(self.session.username, chat, [])
        return True

    # ── outgoing ─────────────────────────────────────────────────────────────────────────────

    def send(self, text: str) -> Reply:
        """Sends ``text`` to the active chat; if it is the path of an image, sends the image.

        A message the server rejected stays in the chat flagged ``failed`` (shown, never stored).
        """
        chat = self.session.active_chat
        text = text.strip()
        if not chat or not text:
            return Reply(False, "Nothing to send")

        wire = images.encode_file(text) if os.path.isfile(text) else None
        if wire is None and os.path.isfile(text) and text.lower().endswith(tuple(images.SUPPORTED_EXTENSIONS)):
            return Reply(False, f"Image too large or unreadable (limit {images.MAX_IMAGE_BYTES // 2**20} MB)")

        reply = self.api.send_message(chat, wire or text)
        contents = text
        if reply.ok and wire:
            contents = images.decode_and_save(wire, self.persistence.images_dir(self.session.username))
        message: Message = {
            "author": self.session.username,
            "contents": contents,
            "sent": reply.data.get("sent") or self.clock(),
            "chatname": chat,
        }
        if reply.ok:
            self.session.add_message(chat, message)
            self.persistence.update_user_chat(self.session.username, chat, self.session.messages[chat])
        else:
            self.session.add_message(chat, {**message, "failed": True})
        return reply

    def create_chat(self, name: str, participants_text: str) -> Reply:
        """Creates a chat from a name and a comma-separated list of usernames."""
        name = name.strip()
        participants = [p.strip() for p in participants_text.split(",") if p.strip()]
        if not name or not participants:
            return Reply(False, "A name and at least one participant are required")
        reply = self.api.create_chat(name, participants)
        if reply.ok:
            self.session.create_chat(name)
            self.persistence.update_user_chat(self.session.username, name, [])
        return reply
