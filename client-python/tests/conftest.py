"""Shared fixtures: a fake transport and a controller wired to temporary storage."""

import curses
import queue
from typing import Any

import pytest

from chat_client.api import APIClient
from chat_client.controller import ChatController
from chat_client.persistence import PersistenceManager
from chat_client.session import AppSession


class FakeTransport:
    """Stands in for NetworkClient: records what is sent and plays back scripted replies."""

    def __init__(self) -> None:
        self.running = True
        self.sent: list[Any] = []
        self.replies: queue.Queue = queue.Queue()
        self.incoming: list[Any] = []  # pushes waiting to be drained

    def script(self, *replies: Any) -> None:
        for reply in replies:
            self.replies.put(reply)

    def send(self, message: str | bytes) -> None:
        if not self.running:
            raise OSError("closed")
        self.sent.append(message)

    def recv(self, timeout: float | None = None) -> Any:
        try:
            return self.replies.get_nowait()
        except queue.Empty:
            return None

    def drain(self) -> list[Any]:
        items, self.incoming = self.incoming, []
        return items


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def session() -> AppSession:
    return AppSession()


@pytest.fixture
def persistence(tmp_path) -> PersistenceManager:
    return PersistenceManager(tmp_path / "chats")


@pytest.fixture
def controller(transport, session, persistence) -> ChatController:
    return ChatController(APIClient(transport), session, persistence, clock=lambda: "2026-05-04 10:30:00")


def message(author="ana", contents="hi", sent="2026-05-04 10:00:00", chat="team", **extra) -> dict:
    return {"author": author, "contents": contents, "sent": sent, "chatname": chat, **extra}


class FakeScreen:
    def __init__(self, rows=24, cols=80, keys=()):
        self.rows, self.cols = rows, cols
        self.keys = list(keys)
        self.writes: list[tuple[int, int, str]] = []
        self.erased = 0
        self.cleared = 0
        self.timeouts: list[int] = []

    def getmaxyx(self):
        return self.rows, self.cols

    def addstr(self, y, x, text, attr=0):
        if y >= self.rows or x + len(text) > self.cols + 200:
            raise curses.error("outside")
        self.writes.append((y, x, text))

    def erase(self):
        self.erased += 1
        self.writes.clear()

    def clear(self):
        self.cleared += 1

    def refresh(self):
        pass

    def move(self, y, x):
        pass

    def get_wch(self):
        return self.keys.pop(0)

    def getch(self):
        return self.keys.pop(0) if self.keys else -1

    def timeout(self, ms):
        self.timeouts.append(ms)

    def text(self):
        return "\n".join(w[2] for w in self.writes)
