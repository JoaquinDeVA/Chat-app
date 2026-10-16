import json

from chat_client.api import APIClient


def test_login_is_ok_when_the_server_says_processed(transport):
    transport.script({"processed": 1, "msg": "ok"})
    reply = APIClient(transport).login("ana", "pw")
    assert reply.ok and reply.message == "ok"
    assert json.loads(transport.sent[0])["action"] == "login"


def test_login_failure_carries_the_servers_message(transport):
    transport.script({"processed": 0, "msg": "Authentication failed"})
    reply = APIClient(transport).login("ana", "bad")
    assert not reply.ok and reply.message == "Authentication failed"


def test_code_one_also_means_success(transport):
    transport.script({"code": 1, "msg": "", "conversations": {}})
    assert APIClient(transport).load_delta("1970-01-01 00:00:00").ok


def test_send_message_exposes_the_server_timestamp(transport):
    transport.script({"processed": 1, "msg": "Message sent", "sent": "2026-05-04 10:30:00"})
    reply = APIClient(transport).send_message("team", "hi")
    assert reply.ok and reply.data["sent"] == "2026-05-04 10:30:00"


def test_no_reply_or_a_non_object_reply_is_a_failure(transport):
    api = APIClient(transport)
    assert not api.login("ana", "pw").ok  # nothing scripted -> timeout -> None
    transport.script("garbage")
    assert not api.create_chat("c", ["ana"]).ok


def test_a_closed_connection_is_reported_not_raised(transport):
    transport.running = False
    reply = APIClient(transport).send_message("team", "hi")
    assert not reply.ok and "Connection error" in reply.message


def test_logout_is_sent_only_while_connected_and_never_raises(transport):
    api = APIClient(transport)
    api.logout()
    assert json.loads(transport.sent[0]) == {"action": "logout"}
    transport.running = False
    api.logout()
    assert len(transport.sent) == 1


def test_hello_is_the_version_announcement(transport):
    transport.script({"processed": 1, "msg": "ok", "version": 2})
    reply = APIClient(transport).hello()
    assert reply.ok and json.loads(transport.sent[0]) == {"action": "hello", "version": 2}


def test_a_refused_version_explains_which_ones_the_server_speaks(transport):
    transport.script({"processed": 0, "msg": "Unsupported protocol version", "supported": [1]})
    reply = APIClient(transport).hello()
    assert not reply.ok and "[1]" in reply.message
