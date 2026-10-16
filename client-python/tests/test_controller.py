import json

from chat_client import images
from chat_client.persistence import EPOCH

from .conftest import message


def delta_reply(**conversations):
    return {"code": 1, "msg": "", "conversations": conversations}


class TestSigningIn:
    def test_login_starts_the_session_and_downloads_the_history(self, controller, transport, session):
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(team=[message(contents="hello")], quiet=[]))

        reply = controller.sign_in("ana", "pw")

        assert reply.ok and session.username == "ana"
        assert [json.loads(m)["action"] for m in transport.sent] == ["login", "load_message_delta"]
        assert json.loads(transport.sent[1])["since"] == EPOCH
        assert session.chats == ["team", "quiet"] and session.messages["team"][0]["contents"] == "hello"

    def test_a_failed_login_leaves_no_session(self, controller, transport, session):
        transport.script({"processed": 0, "msg": "Authentication failed"})
        reply = controller.sign_in("ana", "bad")
        assert not reply.ok and not session.is_authenticated()
        assert len(transport.sent) == 1

    def test_registration_consumes_the_servers_second_reply(self, controller, transport, session):
        transport.script({"processed": 1, "msg": "User added"}, {"processed": 1, "msg": "ok"}, delta_reply())
        reply = controller.register("ana", "pw")
        assert reply.ok and session.username == "ana"
        assert transport.replies.empty(), "both replies of the registration were read"

    def test_a_rejected_registration_stops_there(self, controller, transport, session):
        transport.script({"processed": 0, "msg": "Could not add user"})
        reply = controller.register("ana", "pw")
        assert not reply.ok and reply.message == "Could not add user" and not session.is_authenticated()

    def test_a_failed_automatic_login_after_registering_is_explained(self, controller, transport, session):
        transport.script({"processed": 1, "msg": "User added"}, {"processed": 0, "msg": "Authentication failed"})
        reply = controller.register("ana", "pw")
        assert not reply.ok and "log in manually" in reply.message and not session.is_authenticated()


class TestSync:
    def test_only_new_messages_are_requested_and_merged_with_the_local_copy(
        self, controller, transport, persistence, session
    ):
        persistence.update_user_chat("ana", "team", [message(contents="old", sent="2026-05-01 09:00:00")])
        transport.script(
            {"processed": 1, "msg": "ok"}, delta_reply(team=[message(contents="new", sent="2026-05-02 09:00:00")])
        )

        controller.sign_in("ana", "pw")

        assert json.loads(transport.sent[1])["since"] == "2026-05-01 09:00:00"
        assert [m["contents"] for m in session.messages["team"]] == ["old", "new"]
        assert persistence.load_last_sync("ana") == "2026-05-02 09:00:00"

    def test_a_device_that_never_synced_ignores_stale_local_files(self, controller, transport, persistence, session):
        user_dir = persistence.base_dir / "ana"
        user_dir.mkdir(parents=True)
        (user_dir / "stale.txt").write_text('{"author": "x", "contents": "stale"}\n')
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(team=[]))
        controller.sign_in("ana", "pw")
        assert "stale" not in session.chats

    def test_pushes_received_before_the_request_cannot_be_mistaken_for_its_reply(self, controller, transport):
        transport.incoming = [message()]
        transport.script({"processed": 1, "msg": "ok"}, delta_reply())
        controller.sign_in("ana", "pw")
        assert transport.incoming == [], "the queue was drained before asking"

    def test_images_in_the_history_are_saved_and_replaced_by_references(
        self, controller, transport, persistence, session
    ):
        wire = f"{images.IMG_TAG}|.png|" + "QUJD"  # base64 of "ABC"
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(team=[message(contents=wire)]))
        controller.sign_in("ana", "pw")
        reference = session.messages["team"][0]["contents"]
        assert images.is_image_ref(reference)
        assert (persistence.images_dir("ana") / images.get_filename(reference)).read_bytes() == b"ABC"

    def test_a_failed_delta_still_gives_a_usable_session(self, controller, transport, session):
        transport.script({"processed": 1, "msg": "ok"})  # no delta reply -> timeout
        assert controller.sign_in("ana", "pw").ok and session.is_authenticated() and session.chats == []


class TestIncoming:
    def signed_in(self, controller, transport, **conversations):
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(**conversations))
        controller.sign_in("ana", "pw")

    def test_a_pushed_message_is_stored_and_flags_a_closed_chat_as_unread(
        self, controller, transport, session, persistence
    ):
        self.signed_in(controller, transport, team=[message(sent="2026-05-01 00:00:00")], other=[])
        session.active_chat = "other"
        transport.incoming = [message(author="ben", contents="ping", sent="2026-05-04 10:00:00")]

        assert controller.poll()

        assert session.messages["team"][-1]["contents"] == "ping"
        assert "team" in session.unread_chats and session.chats[0] == "team"
        assert persistence.load_user_conversations("ana")["team"][-1]["contents"] == "ping"

    def test_a_message_in_the_open_chat_is_not_flagged_unread(self, controller, transport, session):
        self.signed_in(controller, transport, team=[message()])
        session.active_chat = "team"
        transport.incoming = [message(author="ben")]
        controller.poll()
        assert not session.unread_chats

    def test_a_chat_notice_adds_an_empty_chat_once(self, controller, transport, session):
        self.signed_in(controller, transport)
        transport.incoming = [{"chatname": "fresh"}, {"chatname": "fresh"}]
        assert controller.poll()
        assert session.chats == ["fresh"]
        transport.incoming = [{"chatname": "fresh"}]
        assert not controller.poll(), "nothing changed"

    def test_unrelated_and_malformed_pushes_are_ignored(self, controller, transport):
        self.signed_in(controller, transport)
        transport.incoming = [{"processed": 1}, "text", {"chatname": ""}, {"conversations": {}}]
        assert not controller.poll()


class TestSending:
    def open_chat(self, controller, transport, session):
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(team=[]))
        controller.sign_in("ana", "pw")
        session.active_chat = "team"

    def test_a_sent_message_is_stored_with_the_servers_timestamp(self, controller, transport, session, persistence):
        self.open_chat(controller, transport, session)
        transport.script({"processed": 1, "msg": "Message sent", "sent": "2026-05-04 10:31:07"})

        reply = controller.send("  hello  ")

        assert reply.ok
        assert json.loads(transport.sent[-1]) == {"action": "send_msg", "chat": "team", "msg": "hello"}
        assert session.messages["team"][-1] == {
            "author": "ana",
            "contents": "hello",
            "sent": "2026-05-04 10:31:07",
            "chatname": "team",
        }
        assert persistence.load_last_sync("ana") == "2026-05-04 10:31:07"

    def test_without_a_server_timestamp_the_local_clock_is_used(self, controller, transport, session):
        self.open_chat(controller, transport, session)
        transport.script({"processed": 1, "msg": "Message sent"})
        controller.send("hi")
        assert session.messages["team"][-1]["sent"] == "2026-05-04 10:30:00"

    def test_a_rejected_message_is_shown_as_failed_but_never_stored(self, controller, transport, session, persistence):
        self.open_chat(controller, transport, session)
        transport.script({"processed": 0, "msg": "Could not send message"})
        reply = controller.send("hi")
        assert not reply.ok
        assert session.messages["team"][-1]["failed"] is True
        controller.sign_out()
        assert persistence.load_user_conversations("ana").get("team", []) == []

    def test_nothing_is_sent_without_an_open_chat_or_text(self, controller, transport, session):
        self.open_chat(controller, transport, session)
        sent_before = len(transport.sent)
        assert not controller.send("   ").ok
        session.active_chat = None
        assert not controller.send("hi").ok
        assert len(transport.sent) == sent_before

    def test_the_path_of_an_image_sends_the_image(self, controller, transport, session, persistence, tmp_path):
        self.open_chat(controller, transport, session)
        picture = tmp_path / "pic.png"
        picture.write_bytes(b"\x89PNGdata")
        transport.script({"processed": 1, "msg": "Message sent", "sent": "2026-05-04 10:31:07"})

        assert controller.send(str(picture)).ok

        wire = json.loads(transport.sent[-1])["msg"]
        assert images.is_wire_format(wire)
        reference = session.messages["team"][-1]["contents"]
        assert (persistence.images_dir("ana") / images.get_filename(reference)).read_bytes() == picture.read_bytes()

    def test_an_image_that_is_too_large_is_refused_locally(self, controller, transport, session, tmp_path, monkeypatch):
        self.open_chat(controller, transport, session)
        monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 4)
        picture = tmp_path / "big.png"
        picture.write_bytes(b"x" * 100)
        sent_before = len(transport.sent)
        reply = controller.send(str(picture))
        assert not reply.ok and "too large" in reply.message and len(transport.sent) == sent_before


class TestCreatingChats:
    def test_a_chat_is_created_from_a_comma_separated_list(self, controller, transport, session, persistence):
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(), {"processed": 1, "msg": "Chat created"})
        controller.sign_in("ana", "pw")
        assert controller.create_chat(" team ", "ben, cat ,, ").ok
        assert json.loads(transport.sent[-1]) == {
            "action": "create_chat",
            "chat_name": "team",
            "participants": ["ben", "cat"],
        }
        assert session.chats == ["team"] and session.active_chat == "team"
        assert "team" in persistence.load_user_conversations("ana")

    def test_invalid_input_never_reaches_the_server(self, controller, transport, session):
        transport.script({"processed": 1, "msg": "ok"}, delta_reply())
        controller.sign_in("ana", "pw")
        sent_before = len(transport.sent)
        assert not controller.create_chat("", "ben").ok
        assert not controller.create_chat("team", " , ").ok
        assert len(transport.sent) == sent_before

    def test_a_rejected_chat_is_not_added(self, controller, transport, session):
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(), {"processed": 0, "msg": "Could not create chat"})
        controller.sign_in("ana", "pw")
        assert not controller.create_chat("team", "ghost").ok and session.chats == []


class TestSigningOut:
    def test_sign_out_tells_the_server_and_saves_everything(self, controller, transport, session, persistence):
        transport.script({"processed": 1, "msg": "ok"}, delta_reply(team=[message(sent="2026-05-04 10:00:00")]))
        controller.sign_in("ana", "pw")
        controller.sign_out()
        assert json.loads(transport.sent[-1]) == {"action": "logout"}
        assert persistence.load_last_sync("ana") == "2026-05-04 10:00:00"

    def test_signing_out_without_a_session_does_nothing(self, controller, transport):
        controller.sign_out()
        assert transport.sent == []
