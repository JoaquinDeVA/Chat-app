from chat_client.session import AppSession

from .conftest import message


def test_chats_are_ordered_by_their_newest_message_and_empty_ones_go_last(session):
    session.load_conversations(
        {
            "old": [message(sent="2026-01-01 10:00:00", chat="old")],
            "empty": [],
            "new": [message(sent="2026-03-01 10:00:00", chat="new"), message(sent="2026-02-01 10:00:00", chat="new")],
        }
    )
    assert session.chats == ["new", "old", "empty"]
    assert session.active_chat == "new"
    assert [m["sent"] for m in session.messages["new"]] == ["2026-02-01 10:00:00", "2026-03-01 10:00:00"]


def test_add_message_creates_the_chat_and_moves_it_to_the_top(session):
    session.load_conversations({"a": [message(chat="a")], "b": [message(chat="b", sent="2026-06-01 00:00:00")]})
    session.add_message("a", message(chat="a", sent="2026-07-01 00:00:00"))
    session.add_message("fresh", message(chat="fresh"))
    assert session.chats[0] == "fresh" and session.chats[1] == "a"
    assert len(session.messages["a"]) == 2


def test_create_chat_activates_it_once(session):
    session.create_chat("team")
    session.create_chat("team")
    assert session.chats == ["team"] and session.active_chat == "team"


def test_unread_flags_and_unknown_chats(session):
    session.mark_unread("a")
    assert "a" in session.unread_chats
    session.mark_read("a")
    session.mark_read("never-seen")
    assert not session.unread_chats
    assert session.get_chat_messages("nope") == []


def test_clear_forgets_the_user():
    session = AppSession()
    session.set_user("ana")
    session.create_chat("team")
    assert session.is_authenticated()
    session.clear()
    assert not session.is_authenticated() and not session.chats and not session.messages
