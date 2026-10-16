"""The curses layer, against a fake screen that records what is drawn."""

import curses

import pytest

from chat_client import tui as tui_module
from chat_client.tui import TUI, draw_box, read_line

from .conftest import FakeScreen, message


@pytest.fixture(autouse=True)
def no_curses_runtime(monkeypatch):
    monkeypatch.setattr(curses, "curs_set", lambda *_: None)
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    monkeypatch.setattr(curses, "color_pair", lambda n: 0)


class TestMainScreen:
    def screen_with(self, **state):
        screen = FakeScreen()
        view = TUI(screen)
        view.set_chats(state.get("chats", []))
        view.set_active_chat(state.get("active"))
        view.set_messages(state.get("messages", []))
        view.set_unread(state.get("unread", set()))
        return screen, view

    def test_empty_screen_says_there_are_no_chats(self):
        screen, view = self.screen_with()
        view.draw()
        assert "(no chats)" in screen.text() and "(no chat selected)" in screen.text()

    def test_chats_messages_unread_marker_and_images_are_drawn(self):
        screen, view = self.screen_with(
            chats=["team", "other"],
            active="team",
            unread={"other"},
            messages=[message(contents="hello"), message(author="ben", contents="[[img]]|abc.png")],
        )
        view.draw()
        text = screen.text()
        assert "team" in text and "other" in text and "◆" in text
        assert "ana: hello" in text and "ben: [image: abc.png]" in text

    def test_failed_messages_are_labelled(self):
        assert TUI.format_message(message(contents="x", failed=True)) == ("[FAILED] ana: x", "failed")
        assert TUI.format_message("legacy line") == ("legacy line", "normal")

    def test_drawing_never_flickers_and_survives_a_tiny_terminal(self):
        screen, view = self.screen_with(chats=["a"] * 50, active="a", messages=[message()] * 100)
        view.draw()
        assert screen.erased == 1 and screen.cleared == 0, "erase(), not clear(): clear() makes the screen flicker"
        small = FakeScreen(rows=6, cols=20)
        TUI(small).draw()

    def test_scrolling_stays_within_the_messages(self):
        _, view = self.screen_with(chats=["a"], active="a", messages=[message()] * 3)
        for _ in range(10):
            view.scroll_up()
        assert view.scroll == 2
        for _ in range(10):
            view.scroll_down()
        assert view.scroll == 0

    def test_active_chat_falls_back_to_the_first(self):
        _, view = self.screen_with(chats=["a", "b"], active="gone")
        view.set_chats(["a", "b"])
        assert view.active_chat == "a"


class TestReadLine:
    def test_typing_backspace_and_enter(self):
        screen = FakeScreen(keys=["h", "i", "x", "\x7f", "\n"])
        assert read_line(screen, 1, 1, 10) == "hi"

    def test_escape_cancels(self):
        assert read_line(FakeScreen(keys=["a", "\x1b"]), 1, 1, 10) is None

    def test_the_length_is_limited_and_control_characters_are_ignored(self):
        screen = FakeScreen(keys=["a", "b", "c", "d", "\x01", "\n"])
        assert read_line(screen, 1, 1, 3) == "abc"

    def test_hidden_fields_show_asterisks_until_tab_reveals_them(self):
        screen = FakeScreen(keys=["s", "e", "\n"])
        assert read_line(screen, 1, 1, 10, hidden=True) == "se"
        assert any(w[2] == "**" for w in screen.writes) and not any(w[2] == "se" for w in screen.writes)
        revealing = FakeScreen(keys=["s", "e", "\t", "\n"])
        read_line(revealing, 1, 1, 10, hidden=True)
        assert any(w[2] == "se" for w in revealing.writes)

    def test_curses_errors_while_reading_are_retried(self):
        class Flaky(FakeScreen):
            calls = 0

            def get_wch(self):
                self.calls += 1
                if self.calls == 1:
                    raise curses.error("no input")
                return super().get_wch()

        assert read_line(Flaky(keys=["a", "\n"]), 1, 1, 5) == "a"


def test_boxes_are_centered_and_titled():
    screen = FakeScreen(rows=20, cols=60)
    top, left = draw_box(screen, 7, 30, "TITLE")
    assert (top, left) == (6, 15) and "TITLE" in screen.text()
    assert screen.erased == 1
    assert tui_module.ESCAPE == "\x1b"
