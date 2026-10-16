"""Screens and key handling of the curses application, with a fake screen and a stub controller."""

import curses

import pytest

from chat_client import app as app_module
from chat_client import images
from chat_client.api import Reply
from chat_client.app import MessagingApp
from chat_client.config import ServerAddress
from chat_client.session import AppState, AuthMode, LiveMode

from .conftest import FakeScreen, message


class StubController:
    """Records calls and answers with the replies it was given."""

    def __init__(self, session):
        self.session = session
        self.calls = []
        self.reply = Reply(True, "ok")
        self.changed = False

    def sign_in(self, username, password):
        self.calls.append(("sign_in", username, password))
        return self.reply

    def register(self, username, password):
        self.calls.append(("register", username, password))
        return self.reply

    def send(self, text):
        self.calls.append(("send", text))
        return self.reply

    def create_chat(self, name, participants):
        self.calls.append(("create_chat", name, participants))
        return self.reply

    def poll(self):
        return self.changed

    def sign_out(self):
        self.calls.append(("sign_out",))


@pytest.fixture(autouse=True)
def quiet_curses(monkeypatch):
    monkeypatch.setattr(curses, "curs_set", lambda *_: None)
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    monkeypatch.setattr(curses, "color_pair", lambda n: 0)


@pytest.fixture
def make_app(tmp_path):
    def build(keys=(), connected=False):
        screen = FakeScreen(keys=keys)
        application = MessagingApp(screen, ServerAddress("127.0.0.1", 1), persistence=None)
        application.persistence.base_dir = tmp_path / "chats"
        application.controller = StubController(application.session)
        application.connected = connected
        return application, screen

    return build


def feed_lines(monkeypatch, *values):
    """Makes read_line return the given values in order (None simulates Esc)."""
    queue = list(values)
    monkeypatch.setattr(app_module, "read_line", lambda *a, **k: queue.pop(0))


class TestAuthMenu:
    @pytest.mark.parametrize(
        ("key", "mode", "state"),
        [
            ("l", AuthMode.LOGIN, AppState.AUTH),
            ("r", AuthMode.REGISTER, AppState.AUTH),
            ("q", AuthMode.MENU, AppState.EXIT),
        ],
    )
    def test_keys_choose_the_next_screen(self, make_app, key, mode, state):
        application, _ = make_app(keys=[ord(key)])
        application.show_auth_menu()
        assert (application.auth_mode, application.state) == (mode, state)

    def test_the_menu_shows_the_connection_state_and_is_drawn_once(self, make_app):
        application, screen = make_app(keys=[ord("x")], connected=False)
        application.show_auth_menu()
        assert "No connection" in screen.text() and screen.erased == 1 and screen.cleared == 0
        application, screen = make_app(keys=[ord("x")], connected=True)
        application.show_auth_menu()
        assert "Connected" in screen.text()


class TestAuthForm:
    def start(self, make_app, monkeypatch, *lines, register=False):
        application, screen = make_app(connected=True, keys=[ord("k")])
        feed_lines(monkeypatch, *lines)
        application.show_auth_form(register=register)
        return application, screen

    def test_a_successful_login_enters_the_chat_screen(self, make_app, monkeypatch):
        application, _ = self.start(make_app, monkeypatch, " ana ", " pw ")
        assert application.controller.calls == [("sign_in", "ana", "pw")]
        assert application.state == AppState.LIVE and application.needs_redraw

    def test_registration_uses_the_register_operation(self, make_app, monkeypatch):
        application, _ = self.start(make_app, monkeypatch, "ana", "pw", register=True)
        assert application.controller.calls == [("register", "ana", "pw")]

    def test_escape_at_either_field_goes_back_without_contacting_the_server(self, make_app, monkeypatch):
        """Regression: there was no way to leave the form."""
        application, _ = self.start(make_app, monkeypatch, None)
        assert application.controller.calls == [] and application.state == AppState.AUTH
        application, _ = self.start(make_app, monkeypatch, "ana", None)
        assert application.controller.calls == []

    def test_blank_fields_are_refused(self, make_app, monkeypatch):
        application, screen = self.start(make_app, monkeypatch, "  ", "pw")
        assert application.controller.calls == [] and "required" in screen.text()

    def test_the_servers_explanation_is_shown_when_it_refuses(self, make_app, monkeypatch):
        application, screen = make_app(connected=True, keys=[ord("k")])
        application.controller.reply = Reply(False, "Authentication failed")
        feed_lines(monkeypatch, "ana", "bad")
        application.show_auth_form(register=False)
        assert "Authentication failed" in screen.text() and application.state == AppState.AUTH

    def test_without_a_connection_the_form_explains_why(self, make_app, monkeypatch):
        application, screen = make_app(connected=False, keys=[ord("k")])
        application.show_auth_form(register=False)
        assert "No connection" in screen.text() and application.controller.calls == []


class TestNavigation:
    def open_chats(self, make_app, keys):
        application, screen = make_app(keys=keys, connected=True)
        application.net.running = True
        application.session.load_conversations(
            {"a": [message(chat="a", sent="2026-02-01 00:00:00")], "b": [message(chat="b", sent="2026-01-01 00:00:00")]}
        )
        application.state = AppState.LIVE
        return application, screen

    def test_arrows_move_between_chats_and_mark_them_read(self, make_app):
        application, _ = self.open_chats(make_app, [curses.KEY_DOWN])
        application.session.mark_unread("b")
        application.handle_navigation()
        assert application.session.active_chat == "b" and "b" not in application.session.unread_chats
        application.stdscr.keys = [curses.KEY_UP]
        application.handle_navigation()
        assert application.session.active_chat == "a"

    @pytest.mark.parametrize(
        ("key", "mode"), [(ord("\n"), LiveMode.INPUT), (ord(" "), LiveMode.INPUT), (ord("n"), LiveMode.NEW_CHAT)]
    )
    def test_keys_open_the_input_and_new_chat_screens(self, make_app, key, mode):
        application, _ = self.open_chats(make_app, [key])
        application.handle_navigation()
        assert application.live_mode == mode

    def test_q_quits_and_no_key_just_polls(self, make_app):
        application, _ = self.open_chats(make_app, [ord("q")])
        application.handle_navigation()
        assert application.state == AppState.EXIT
        application, _ = self.open_chats(make_app, [])
        application.controller.changed = True
        application.needs_redraw = False
        application.handle_navigation()
        assert application.needs_redraw, "a push redraws the screen"

    def test_a_lost_connection_is_announced(self, make_app):
        application, _ = self.open_chats(make_app, [])
        application.net.running = False
        application.handle_navigation()
        assert "lost" in application.tui.status

    def test_navigation_waits_for_input_in_slices_instead_of_busy_looping(self, make_app):
        application, screen = self.open_chats(make_app, [])
        application.handle_navigation()
        assert screen.timeouts[-1] == app_module.POLL_INTERVAL_MS


class TestWritingMessages:
    def prepare(self, make_app, monkeypatch, typed):
        application, screen = make_app(keys=[], connected=True)
        application.session.create_chat("team")
        application.live_mode = LiveMode.INPUT
        monkeypatch.setattr(application.tui, "get_input", lambda: typed)
        return application, screen

    def test_text_is_sent_to_the_open_chat(self, make_app, monkeypatch):
        application, _ = self.prepare(make_app, monkeypatch, "hello")
        application.handle_message_input()
        assert application.controller.calls == [("send", "hello")]
        assert application.live_mode == LiveMode.NAVIGATION and "Sent" in application.tui.status

    def test_escape_cancels_the_message_without_sending(self, make_app, monkeypatch):
        """Regression: once a message was started it could not be cancelled."""
        application, _ = self.prepare(make_app, monkeypatch, None)
        application.handle_message_input()
        assert application.controller.calls == [] and application.live_mode == LiveMode.NAVIGATION

    def test_blank_text_is_not_sent_and_failures_are_reported(self, make_app, monkeypatch):
        application, _ = self.prepare(make_app, monkeypatch, "   ")
        application.handle_message_input()
        assert application.controller.calls == []
        application, _ = self.prepare(make_app, monkeypatch, "hi")
        application.controller.reply = Reply(False, "Could not send message")
        application.handle_message_input()
        assert "Could not send message" in application.tui.status


class TestNewChat:
    def test_the_form_creates_a_chat(self, make_app, monkeypatch):
        application, _ = make_app(connected=True)
        application.live_mode = LiveMode.NEW_CHAT
        feed_lines(monkeypatch, "team", "ben, cat")
        application.handle_new_chat()
        assert application.controller.calls == [("create_chat", "team", "ben, cat")]
        assert application.live_mode == LiveMode.NAVIGATION and "created" in application.tui.status

    @pytest.mark.parametrize("answers", [(None,), ("team", None)])
    def test_escape_cancels_the_form(self, make_app, monkeypatch, answers):
        application, _ = make_app(connected=True)
        feed_lines(monkeypatch, *answers)
        application.handle_new_chat()
        assert application.controller.calls == [] and application.live_mode == LiveMode.NAVIGATION


class TestImagesAndLifecycle:
    def test_the_newest_image_of_the_chat_is_opened(self, make_app, monkeypatch):
        application, _ = make_app(connected=True)
        application.session.set_user("ana")
        application.session.add_message("team", message(contents=f"{images.IMG_TAG}|old.png"))
        application.session.add_message("team", message(contents=f"{images.IMG_TAG}|new.png"))
        application.session.active_chat = "team"
        opened = []
        monkeypatch.setattr(images, "open_image", lambda ref, folder: opened.append(ref) or True)
        application.open_latest_image()
        assert opened == [f"{images.IMG_TAG}|new.png"]
        application.session.messages["team"].clear()
        application.open_latest_image()
        assert "No images" in application.tui.status

    def test_cleanup_signs_out_only_when_connected(self, make_app):
        application, _ = make_app(connected=True)
        application.cleanup()
        assert ("sign_out",) in application.controller.calls
        application, _ = make_app(connected=False)
        application.cleanup()
        assert application.controller.calls == []

    def test_run_loops_until_exit(self, make_app):
        application, _ = make_app(keys=[ord("l"), 0x1B], connected=True)
        application.handle_auth = lambda: setattr(application, "state", AppState.EXIT)
        application.run()
        assert application.state == AppState.EXIT

    def test_live_screen_is_drawn_only_when_needed(self, make_app):
        application, screen = make_app(keys=[], connected=True)
        application.session.set_user("ana")
        application.state = AppState.LIVE
        application.net.running = True
        application.handle_live()
        assert screen.erased == 1 and not application.needs_redraw
        application.handle_live()
        assert screen.erased == 1, "no change, no repaint (this is what removes the flicker)"
