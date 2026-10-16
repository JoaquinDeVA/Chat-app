"""Curses presentation: the main screen and the small input helpers.

Nothing here decides anything: the screen is drawn from what :class:`~chat_client.app.MessagingApp`
hands over, and the text typed by the user is handed back.
"""

import curses
import locale

from . import images
from .session import Message

locale.setlocale(locale.LC_ALL, "")

ESCAPE = "\x1b"
BACKSPACE_KEYS = ("\x7f", "\x08")


def _put(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    """``addstr`` that ignores writes outside the screen (they raise ``curses.error``)."""
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_box(stdscr, height: int, width: int, title: str = "") -> tuple[int, int]:
    """Erases the screen and draws a centered box.

    :return: ``(top, left)`` of the box.
    """
    rows, cols = stdscr.getmaxyx()
    top = max(0, (rows - height) // 2)
    left = max(0, (cols - width) // 2)
    inner = width - 2
    if title:
        pad = max(0, (inner - len(title) - 2) // 2)
        header = "╔" + "═" * pad + f" {title} " + "═" * max(0, inner - pad - len(title) - 2) + "╗"
    else:
        header = "╔" + "═" * inner + "╗"
    stdscr.erase()  # erase(), not clear(): clear() repaints the whole terminal and makes it flicker
    _put(stdscr, top, left, header)
    for row in range(1, height - 1):
        _put(stdscr, top + row, left, "║" + " " * inner + "║")
    _put(stdscr, top + height - 1, left, "╚" + "═" * inner + "╝")
    return top, left


def read_line(stdscr, y: int, x: int, max_len: int = 30, hidden: bool = False) -> str | None:
    """Reads a line at ``(y, x)``. Backspace edits, Tab shows/hides a hidden field, Esc cancels.

    :return: The text, or ``None`` if the user pressed Esc.
    """
    text = ""
    reveal = False
    curses.curs_set(1)
    try:
        while True:
            shown = text if (reveal or not hidden) else "*" * len(text)
            _put(stdscr, y, x, " " * max_len)
            _put(stdscr, y, x, shown)
            stdscr.move(y, min(x + len(text), x + max_len))
            stdscr.refresh()
            try:
                key = stdscr.get_wch()
            except curses.error:
                continue
            if key in ("\n", "\r"):
                return text
            if key == ESCAPE:
                return None
            if key == "\t" and hidden:
                reveal = not reveal
            elif key in BACKSPACE_KEYS or key == curses.KEY_BACKSPACE:
                text = text[:-1]
            elif isinstance(key, str) and len(key) == 1 and ord(key) >= 32 and len(text) < max_len:
                text += key
    finally:
        curses.curs_set(0)


class TUI:
    """Main screen: chat list on the left, messages on the right, input bar and status line."""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        self.chat_list: list[str] = []
        self.messages: list[Message] = []
        self.status = ""
        self.active_chat: str | None = None
        self.unread_chats: set[str] = set()
        self.scroll = 0
        self.chat_selection = 0

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_RED, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)

    # ── state pushed in by the application ───────────────────────────────────────────────────

    def set_unread(self, unread: set[str]) -> None:
        """Chats with unread messages (marked with ◆)."""
        self.unread_chats = unread

    def set_status(self, message: str) -> None:
        """Text of the status line (last row)."""
        self.status = message

    def set_chats(self, chats: list[str]) -> None:
        """Replaces the chat list; the active chat falls back to the first if it disappeared."""
        self.chat_list = chats
        self.chat_selection = 0
        if self.active_chat not in chats and chats:
            self.active_chat = chats[0]

    def set_messages(self, messages: list[Message]) -> None:
        """Replaces the messages shown and scrolls to the newest."""
        self.messages = messages
        self.scroll = 0

    def set_active_chat(self, chat: str | None) -> None:
        """Marks ``chat`` as the open one."""
        self.active_chat = chat
        if chat in self.chat_list:
            self.chat_selection = self.chat_list.index(chat)

    def scroll_up(self) -> None:
        """Shows older messages."""
        if self.scroll < len(self.messages) - 1:
            self.scroll += 1

    def scroll_down(self) -> None:
        """Shows newer messages."""
        if self.scroll > 0:
            self.scroll -= 1

    # ── drawing ──────────────────────────────────────────────────────────────────────────────

    @staticmethod
    def format_message(message: Message | str) -> tuple[str, str]:
        """How a message is displayed.

        :return: ``(text, style)`` where style is ``"normal"``, ``"image"`` or ``"failed"``.
        """
        if not isinstance(message, dict):
            return str(message), "normal"
        author = message.get("author", "?")
        contents = message.get("contents", "")
        if images.is_image_ref(contents) or images.is_wire_format(contents):
            return f"{author}: [image: {images.get_filename(contents)}]", "image"
        if message.get("failed"):
            return f"[FAILED] {author}: {contents}", "failed"
        return f"{author}: {contents}", "normal"

    def draw(self) -> None:
        """Repaints the whole screen."""
        stdscr = self.stdscr
        stdscr.erase()
        self.height, self.width = stdscr.getmaxyx()
        chat_width = max(25, self.width // 4)

        _put(stdscr, 0, 0, "═ CHATS ═", curses.A_BOLD)
        if not self.chat_list:
            _put(stdscr, 1, 0, "(no chats)", curses.A_DIM)
        for index, chat in enumerate(self.chat_list):
            if index + 1 >= self.height - 1:
                break
            active, selected = chat == self.active_chat, index == self.chat_selection
            attr = (
                (curses.A_REVERSE | curses.A_BOLD)
                if active and selected
                else curses.A_BOLD
                if active
                else curses.A_REVERSE
                if selected
                else 0
            )
            prefix = "► " if active and selected else "● " if active else "  "
            _put(stdscr, index + 1, 0, (prefix + chat[: chat_width - 4]).ljust(chat_width - 1), attr)
            if chat in self.unread_chats:
                _put(stdscr, index + 1, chat_width - 2, "◆", curses.color_pair(2) | curses.A_BOLD)

        for row in range(self.height - 1):
            _put(stdscr, row, chat_width, "│")

        message_x = chat_width + 2
        message_width = self.width - message_x - 1
        message_rows = self.height - 5
        title = self.active_chat or "(no chat selected)"
        _put(stdscr, 0, message_x, f"╔ {title[: message_width - 4]} ╗"[:message_width], curses.A_BOLD)

        end = len(self.messages) - self.scroll
        for row, message in enumerate(self.messages[max(0, end - message_rows) : end]):
            text, style = self.format_message(message)
            attr = {
                "image": curses.color_pair(2) | curses.A_BOLD,
                "failed": curses.color_pair(1) | curses.A_BOLD,
            }.get(style, 0)
            _put(stdscr, row + 1, message_x, text[:message_width], attr)

        _put(stdscr, self.height - 3, 0, "─" * (self.width - 1))
        _put(stdscr, self.height - 2, 0, "Message: ")
        _put(stdscr, self.height - 1, 0, self.status[: self.width - 1], curses.A_DIM)
        stdscr.refresh()

    def get_input(self) -> str | None:
        """Reads a message in the input bar. Returns ``None`` if the user pressed Esc."""
        return read_line(self.stdscr, self.height - 2, 9, max_len=max(1, self.width - 11))
