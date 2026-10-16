"""Local copy of the conversations, one folder per user.

Layout of ``<base>/<user>/``:

* ``<chat>.txt`` - the chat's messages, one JSON object per line;
* ``last_sync.txt`` - time of the newest message known, used to ask the server only for what is new;
* ``images/`` - images received or sent.
"""

import json
import logging
from pathlib import Path

from .session import Message, sent_time

log = logging.getLogger(__name__)

DEFAULT_BASE_DIR = Path("chats")
EPOCH = "1970-01-01 00:00:00"


def _safe(name: str) -> str:
    """Keeps only letters, digits, ``-`` and ``_`` so that ``name`` is safe inside a path."""
    return "".join(c for c in name if c.isalnum() or c in "-_")


def _parse_line(line: str) -> Message | str:
    """A stored line: the message dict, or the raw text for entries of other formats."""
    try:
        value = json.loads(line)
    except ValueError:
        return line
    return value if isinstance(value, dict) else line


class PersistenceManager:
    """Reads and writes the local conversations.

    :param base_dir: Folder that holds every user's data (created when needed).
    """

    def __init__(self, base_dir: Path = DEFAULT_BASE_DIR):
        self.base_dir = Path(base_dir)

    def _user_dir(self, username: str) -> Path:
        return self.base_dir / _safe(username)

    def images_dir(self, username: str) -> Path:
        """Folder with the images of ``username``."""
        return self._user_dir(username) / "images"

    def load_last_sync(self, username: str) -> str:
        """Time of the newest message known for ``username``; the epoch if none."""
        try:
            return (self._user_dir(username) / "last_sync.txt").read_text(encoding="utf-8").strip() or EPOCH
        except OSError:
            return EPOCH

    def load_user_conversations(self, username: str) -> dict[str, list[Message]]:
        """All the stored chats of ``username`` as ``{chat: [message, ...]}``."""
        conversations: dict[str, list[Message]] = {}
        user_dir = self._user_dir(username)
        if not user_dir.is_dir():
            return conversations
        for path in sorted(user_dir.glob("*.txt")):
            if path.stem == "last_sync":
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    conversations[path.stem] = [_parse_line(line.rstrip("\n")) for line in handle if line.strip()]
            except OSError as error:
                log.warning("could not read %s: %s", path, error)
        return conversations

    def save_user_conversations(self, username: str, conversations: dict[str, list[Message]]) -> None:
        """Writes every chat and advances ``last_sync.txt`` to the newest message."""
        for chat, messages in conversations.items():
            self.update_user_chat(username, chat, messages)

    def update_user_chat(self, username: str, chat: str, messages: list[Message]) -> None:
        """Rewrites one chat and advances ``last_sync.txt`` if it holds a newer message.

        Messages flagged ``failed`` (not delivered) are not stored.
        """
        user_dir = self._user_dir(username)
        stored = [m for m in messages if not (isinstance(m, dict) and m.get("failed"))]
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            with open(user_dir / f"{_safe(chat)}.txt", "w", encoding="utf-8") as handle:
                for message in stored:
                    handle.write(
                        (json.dumps(message, ensure_ascii=False) if isinstance(message, dict) else str(message)) + "\n"
                    )
            newest = max((sent_time(m) for m in stored), default="")
            if newest > self.load_last_sync(username):
                (user_dir / "last_sync.txt").write_text(newest, encoding="utf-8")
        except OSError as error:
            log.error("could not save chat %r of %s: %s", chat, username, error)
