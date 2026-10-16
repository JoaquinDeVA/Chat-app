"""One method per operation of the server: send the request and interpret the reply."""

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import protocol

log = logging.getLogger(__name__)

REPLY_TIMEOUT = 5.0
DELTA_TIMEOUT = 10.0


class Transport(Protocol):
    """What the API needs from the network layer (:class:`~chat_client.network.NetworkClient`)."""

    running: bool

    def send(self, message: str | bytes) -> None: ...

    def recv(self, timeout: float | None = None) -> Any: ...

    def drain(self) -> list[Any]: ...


@dataclass
class Reply:
    """Outcome of an operation.

    :ivar ok: Whether the server accepted it.
    :ivar message: The server's explanation, or the reason it failed.
    :ivar data: The whole reply, for operations that return more than a status.
    """

    ok: bool
    message: str
    data: dict = field(default_factory=dict)


def _is_ok(reply: dict) -> bool:
    """The server marks success with ``processed: 1`` (data operations) or ``code: 1`` (login)."""
    return bool(reply.get("processed")) or reply.get("code") == 1 or bool(reply.get("authorized"))


class APIClient:
    """High-level operations against the server.

    :param transport: A connected network client.
    """

    def __init__(self, transport: Transport):
        self.net = transport

    def _request(self, message: str, timeout: float = REPLY_TIMEOUT) -> Reply:
        """Sends ``message`` and turns the next reply into a :class:`Reply`."""
        try:
            self.net.send(message)
            reply = self.net.recv(timeout=timeout)
        except OSError as error:
            return Reply(False, f"Connection error: {error}")
        if not isinstance(reply, dict):
            return Reply(False, "No valid reply from the server")
        return Reply(_is_ok(reply), str(reply.get("msg", "")), reply)

    def login(self, username: str, password: str) -> Reply:
        """Logs in as an existing user."""
        return self._request(protocol.build_login(username, password))

    def register(self, username: str, password: str) -> Reply:
        """Registers a user.

        On success the server answers **twice**: the registration result, then the result of
        logging the new user in. This returns the first; the caller must consume the second.
        """
        return self._request(protocol.build_create_user(username, password))

    def send_message(self, chat: str, text: str) -> Reply:
        """Sends a message; ``data["sent"]`` holds the time the server stamped it with."""
        return self._request(protocol.build_send_msg(chat, text))

    def create_chat(self, chat_name: str, participants: list[str]) -> Reply:
        """Creates a chat (the server adds the creator to the participants)."""
        return self._request(protocol.build_create_chat(chat_name, participants))

    def load_delta(self, since: str) -> Reply:
        """Messages sent after ``since`` in all my chats; ``data["conversations"]`` maps chat to list."""
        return self._request(protocol.build_load_message_delta(since), timeout=DELTA_TIMEOUT)

    def logout(self) -> None:
        """Tells the server the user is leaving; failures are ignored (we are closing anyway)."""
        try:
            if self.net.running:
                self.net.send(protocol.build_logout())
        except OSError:
            log.debug("logout could not be sent", exc_info=True)
