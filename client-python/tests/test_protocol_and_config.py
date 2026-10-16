import json

import pytest

from chat_client import protocol
from chat_client.config import DEFAULT_HOST, DEFAULT_PORT, resolve_address


class TestProtocol:
    def test_requests_carry_their_action(self):
        assert json.loads(protocol.build_login("ana", "pw")) == {"action": "login", "username": "ana", "password": "pw"}
        assert json.loads(protocol.build_create_user("ana", "pw"))["action"] == "create_user"
        assert json.loads(protocol.build_create_chat("team", ["ana", "ben"])) == {
            "action": "create_chat",
            "chat_name": "team",
            "participants": ["ana", "ben"],
        }
        assert json.loads(protocol.build_send_msg("team", "hi")) == {"action": "send_msg", "chat": "team", "msg": "hi"}
        assert json.loads(protocol.build_load_message_delta("2026-01-01 00:00:00")) == {
            "action": "load_message_delta",
            "since": "2026-01-01 00:00:00",
        }
        assert json.loads(protocol.build_logout()) == {"action": "logout"}

    def test_special_characters_survive_the_roundtrip(self):
        text = 'quote " backslash \\ newline \n unicode ñ 😀 pipe |'
        assert json.loads(protocol.build_send_msg("c", text))["msg"] == text

    def test_frames_end_with_eot_and_are_utf8(self):
        assert protocol.frame_message("ñ") == "ñ".encode() + b"\x04"
        assert protocol.frame_message(b"raw") == b"raw\x04"

    def test_parse_response_decodes_json_with_or_without_eot(self):
        assert protocol.parse_response(b'{"a": 1}\x04') == {"a": 1}
        assert protocol.parse_response('{"a": 1}') == {"a": 1}
        assert protocol.parse_response("not json\x04") == "not json"
        assert protocol.parse_response(b"\xff\xfe") != ""  # invalid UTF-8 does not raise


class TestConfig:
    def test_defaults(self):
        address = resolve_address([], {})
        assert (address.host, address.port) == (DEFAULT_HOST, DEFAULT_PORT)

    def test_environment_overrides_defaults_and_flags_override_the_environment(self):
        env = {"CHAT_SERVER_HOST": "10.0.0.5", "CHAT_SERVER_PORT": "7000"}
        assert resolve_address([], env).port == 7000
        address = resolve_address(["--host", "example.org", "--port", "7100"], env)
        assert (address.host, address.port) == ("example.org", 7100)

    @pytest.mark.parametrize("port", ["0", "70000", "-5"])
    def test_invalid_ports_are_rejected(self, port):
        with pytest.raises(SystemExit):
            resolve_address(["--port", port], {})
