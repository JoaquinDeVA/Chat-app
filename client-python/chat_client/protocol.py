"""Messages of the client/server protocol and their framing.

Every message is a JSON object followed by the end-of-transmission byte (``0x04``). See
``docs/PROTOCOL.md`` for the full description.
"""

import json
from typing import Any

EOT = b"\x04"

#: Version of the protocol this client speaks. Version 2 is the full protocol: Unicode text and
#: images (see ``docs/PROTOCOL.md``); the simple clients (version 1) are text-only ASCII.
PROTOCOL_VERSION = 2


def build_hello(version: int = PROTOCOL_VERSION) -> str:
    """Opening message: tells the server which protocol version this client speaks."""
    return json.dumps({"action": "hello", "version": version})


def build_login(username: str, password: str) -> str:
    """Request to log in as an existing user."""
    return json.dumps({"action": "login", "username": username, "password": password})


def build_create_user(username: str, password: str) -> str:
    """Request to register a new user (the server logs it in as well)."""
    return json.dumps({"action": "create_user", "username": username, "password": password})


def build_create_chat(chat_name: str, participants: list[str]) -> str:
    """Request to create a chat with the given participants."""
    return json.dumps({"action": "create_chat", "chat_name": chat_name, "participants": participants})


def build_send_msg(chat: str, msg: str) -> str:
    """Request to send ``msg`` to ``chat`` (the author is the logged-in user)."""
    return json.dumps({"action": "send_msg", "chat": chat, "msg": msg})


def build_logout() -> str:
    """Notification that the user is leaving."""
    return json.dumps({"action": "logout"})


def build_load_message_delta(since: str) -> str:
    """Request for the messages of all my chats sent after ``since`` (``yyyy-MM-dd HH:mm:ss``)."""
    return json.dumps({"action": "load_message_delta", "since": since})


def frame_message(message: str | bytes) -> bytes:
    """Encodes ``message`` as UTF-8 and appends the end-of-transmission byte."""
    if isinstance(message, str):
        message = message.encode("utf-8")
    return message + EOT


def parse_response(raw: bytes | str) -> Any:
    """Decodes a received message.

    :param raw: The message, with or without its trailing end-of-transmission byte.
    :return: The decoded JSON value, or the text itself if it is not valid JSON.
    """
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    text = text.rstrip("\x04")
    try:
        return json.loads(text)
    except ValueError:
        return text
