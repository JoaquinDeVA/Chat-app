"""The curses application: screens and key handling, on top of :class:`ChatController`."""

import curses
import logging

from . import images
from .api import APIClient
from .config import ServerAddress
from .controller import ChatController
from .network import NetworkClient
from .persistence import PersistenceManager
from .session import AppSession, AppState, AuthMode, LiveMode
from .tui import TUI, draw_box, read_line

log = logging.getLogger(__name__)

POLL_INTERVAL_MS = 100


class MessagingApp:
    """State machine ``AUTH -> LIVE -> EXIT`` that owns the screens.

    :param stdscr: Curses root window.
    :param address: Where the server is.
    :param persistence: Local storage (default: ``./chats``).
    """

    def __init__(self, stdscr, address: ServerAddress, persistence: PersistenceManager | None = None):
        self.stdscr = stdscr
        self.session = AppSession()
        self.persistence = persistence or PersistenceManager()
        self.net = NetworkClient(address.host, address.port)
        self.api = APIClient(self.net)
        self.controller = ChatController(self.api, self.session, self.persistence)
        self.tui = TUI(stdscr)

        self.state = AppState.AUTH
        self.auth_mode = AuthMode.MENU
        self.live_mode = LiveMode.NAVIGATION
        self.needs_redraw = True
        self.connected = False
        self.connect_error = ""
        curses.curs_set(0)
        self._try_connect()

    # ── lifecycle ────────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Main loop: hands control to the handler of the current state."""
        while self.state != AppState.EXIT:
            if self.state == AppState.AUTH:
                self.handle_auth()
            else:
                self.handle_live()

    def cleanup(self) -> None:
        """Logs out, saves the conversations and closes the connection."""
        if self.connected:
            self.controller.sign_out()
        self.net.close()

    def _try_connect(self) -> bool:
        """Connects and opens the conversation with the protocol version."""
        try:
            self.net.connect()
        except OSError as error:
            self.connected, self.connect_error = False, str(error)
            return False
        reply = self.api.hello()
        if not reply.ok:
            self.net.close()
            self.connected, self.connect_error = False, reply.message
            return False
        self.connected, self.connect_error = True, ""
        return True

    # ── helpers ──────────────────────────────────────────────────────────────────────────────

    def _error_attr(self) -> int:
        return (curses.color_pair(1) | curses.A_BOLD) if curses.has_colors() else curses.A_BOLD

    def show_message(self, text: str, title: str = "ERROR") -> None:
        """Shows a box with ``text`` and waits for a key."""
        width = max(len(text) + 8, 38)
        top, left = draw_box(self.stdscr, 6, width, title)
        self.stdscr.addstr(
            top + 2, left + 2, text[: width - 4], self._error_attr() if title == "ERROR" else curses.A_BOLD
        )
        self.stdscr.addstr(top + 4, left + 2, "Press any key...")
        self.stdscr.refresh()
        self.stdscr.timeout(-1)
        self.stdscr.getch()

    # ── authentication ───────────────────────────────────────────────────────────────────────

    def handle_auth(self) -> None:
        """Runs the screen of the current authentication mode."""
        if self.auth_mode == AuthMode.MENU:
            self.show_auth_menu()
        else:
            self.show_auth_form(register=self.auth_mode == AuthMode.REGISTER)

    def show_auth_menu(self) -> None:
        """Main menu; it is drawn once and then waits for a key (no redraw loop, no flicker)."""
        top, left = draw_box(self.stdscr, 11, 28, "CHAT")
        if self.connected:
            self.stdscr.addstr(top + 2, left + 2, "● Connected", curses.A_DIM)
        else:
            self.stdscr.addstr(top + 2, left + 2, "✗ No connection", self._error_attr())
        self.stdscr.addstr(top + 4, left + 2, "(l)  Log in")
        self.stdscr.addstr(top + 5, left + 2, "(r)  Register")
        self.stdscr.addstr(top + 6, left + 2, "(q)  Quit")
        self.stdscr.addstr(top + 9, left + 2, "Option: ")
        self.stdscr.refresh()
        self.stdscr.timeout(-1)
        key = self.stdscr.getch()
        if key == ord("l"):
            self.auth_mode = AuthMode.LOGIN
        elif key == ord("r"):
            self.auth_mode = AuthMode.REGISTER
        elif key == ord("q"):
            self.state = AppState.EXIT

    def show_auth_form(self, register: bool) -> None:
        """Login or registration form; Esc goes back to the menu."""
        self.auth_mode = AuthMode.MENU
        if not self.connected and not self._try_connect():
            self.show_message(f"No connection: {self.connect_error}")
            return

        top, left = draw_box(self.stdscr, 9, 46, "REGISTER" if register else "LOG IN")
        self.stdscr.addstr(top + 2, left + 2, "Username: ")
        username = read_line(self.stdscr, top + 2, left + 12, 28)
        if username is None:
            return
        self.stdscr.addstr(top + 3, left + 2, "Password: ")
        self.stdscr.addstr(top + 4, left + 2, "(Tab shows/hides, Esc cancels)", curses.A_DIM)
        password = read_line(self.stdscr, top + 3, left + 12, 28, hidden=True)
        if password is None:
            return
        username, password = username.strip(), password.strip()
        if not username or not password:
            self.show_message("Username and password are required")
            return

        self.stdscr.addstr(top + 6, left + 2, "Registering..." if register else "Signing in...", curses.A_DIM)
        self.stdscr.refresh()
        reply = (
            self.controller.register(username, password) if register else self.controller.sign_in(username, password)
        )
        if not reply.ok:
            self.show_message(reply.message or "Authentication failed")
            return

        self.state = AppState.LIVE
        self.needs_redraw = True

    # ── chat screen ──────────────────────────────────────────────────────────────────────────

    def handle_live(self) -> None:
        """Redraws if needed and runs the handler of the current chat mode."""
        if self.needs_redraw:
            self.draw_live()
            self.needs_redraw = False
        if self.live_mode == LiveMode.NAVIGATION:
            self.handle_navigation()
        elif self.live_mode == LiveMode.INPUT:
            self.handle_message_input()
        else:
            self.handle_new_chat()

    def draw_live(self) -> None:
        """Pushes the session into the TUI and paints it."""
        self.tui.set_chats(self.session.chats)
        self.tui.set_active_chat(self.session.active_chat)
        self.tui.set_unread(self.session.unread_chats)
        if self.session.active_chat:
            self.tui.set_messages(self.session.get_chat_messages(self.session.active_chat))
        if not self.tui.status:
            self.tui.set_status(
                f"{self.session.username} | ↑↓ chats | Enter write | n new chat | o open image | q quit"
            )
        self.tui.draw()

    def _set_status(self, text: str) -> None:
        self.tui.set_status(text)
        self.needs_redraw = True

    def handle_navigation(self) -> None:
        """Applies pushes from the server and handles one key."""
        self.stdscr.timeout(POLL_INTERVAL_MS)
        key = self.stdscr.getch()
        if self.controller.poll():
            self.needs_redraw = True
        if not self.net.running:
            self._set_status("✗ Connection to the server lost (q to quit)")
        if key == -1:
            return

        chats = self.session.chats
        if key == ord("q"):
            self.state = AppState.EXIT
        elif key in (curses.KEY_UP, curses.KEY_DOWN) and chats:
            index = chats.index(self.session.active_chat) if self.session.active_chat in chats else 0
            index = max(0, index - 1) if key == curses.KEY_UP else min(len(chats) - 1, index + 1)
            self.session.active_chat = chats[index]
            self.session.mark_read(self.session.active_chat)
            self.needs_redraw = True
        elif key in (ord("\n"), ord(" ")) and self.session.active_chat:
            self.live_mode = LiveMode.INPUT
        elif key == ord("n"):
            self.live_mode = LiveMode.NEW_CHAT
        elif key == ord("o") and self.session.active_chat:
            self.open_latest_image()

    def handle_message_input(self) -> None:
        """Reads a message (Esc cancels it) and sends it; paths of images are sent as images."""
        self.stdscr.timeout(-1)
        self._set_status("Writing... (Enter sends, Esc cancels)")
        self.tui.draw()
        text = self.tui.get_input()
        if text and text.strip():
            reply = self.controller.send(text)
            self.tui.set_status("✓ Sent" if reply.ok else f"✗ {reply.message}")
        else:
            self.tui.set_status("")
        self.live_mode = LiveMode.NAVIGATION
        self.needs_redraw = True

    def handle_new_chat(self) -> None:
        """Form to create a chat (Esc cancels)."""
        self.stdscr.timeout(-1)
        self.stdscr.erase()
        self.stdscr.addstr(2, 2, "╔═ NEW CHAT ═╗", curses.A_BOLD)
        self.stdscr.addstr(4, 2, "Name: ")
        name = read_line(self.stdscr, 4, 8, 30)
        participants = None
        if name is not None:
            self.stdscr.addstr(5, 2, "Participants (comma-separated): ")
            participants = read_line(self.stdscr, 5, 34, 100)
        if name is not None and participants is not None:
            reply = self.controller.create_chat(name, participants)
            self.tui.set_status(f"✓ Chat '{name.strip()}' created" if reply.ok else f"✗ {reply.message}")
        else:
            self.tui.set_status("")
        self.live_mode = LiveMode.NAVIGATION
        self.needs_redraw = True

    def open_latest_image(self) -> None:
        """Opens the newest image of the active chat with the system viewer."""
        for message in reversed(self.session.get_chat_messages(self.session.active_chat)):
            contents = message.get("contents", "") if isinstance(message, dict) else ""
            if images.is_image_ref(contents):
                opened = images.open_image(contents, self.persistence.images_dir(self.session.username))
                self._set_status("Opening image..." if opened else "✗ No image viewer found")
                return
        self._set_status("No images in this chat")
