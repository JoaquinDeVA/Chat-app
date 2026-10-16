"""The whole system, for real: MySQL, Java backend, Rust server and the clients.

* the *full* client (protocol v2) is the real Python client (network, API and controller layers);
* the *simple* client (protocol v1) is a raw socket speaking v1, the way the C client does.
"""

import json
import signal
import socket
import time
import uuid

import pytest
from chat_client import images
from chat_client.api import APIClient
from chat_client.controller import ChatController
from chat_client.network import NetworkClient
from chat_client.persistence import PersistenceManager
from chat_client.session import AppSession

from .conftest import mysql


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class FullClient:
    """A version 2 client: the Python client's real layers over a real connection."""

    def __init__(self, stack, tmp_path, name=None):
        self.name = name or unique("full")
        self.net = NetworkClient("127.0.0.1", stack.server_port)
        self.net.connect()
        self.api = APIClient(self.net)
        assert self.api.hello().ok
        self.session = AppSession()
        self.persistence = PersistenceManager(tmp_path / self.name)
        self.controller = ChatController(self.api, self.session, self.persistence)

    def wait_for(self, condition, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.controller.poll()
            if condition():
                return True
            time.sleep(0.05)
        return False

    def close(self):
        self.controller.sign_out()
        self.net.close()


class SimpleClient:
    """A version 1 client over a raw socket."""

    def __init__(self, stack):
        self.sock = socket.create_connection(("127.0.0.1", stack.server_port), timeout=5)
        self.buffer = b""
        assert self.request({"action": "hello", "version": 1})["version"] == 1

    def send(self, message: dict) -> None:
        self.sock.sendall(json.dumps(message).encode() + b"\x04")

    def receive(self) -> dict | None:
        while b"\x04" not in self.buffer:
            chunk = self.sock.recv(65536)
            if not chunk:
                return None
            self.buffer += chunk
        raw, self.buffer = self.buffer.split(b"\x04", 1)
        return json.loads(raw)

    def request(self, message: dict) -> dict:
        self.send(message)
        return self.receive()

    def close(self):
        self.sock.close()


@pytest.fixture
def full(stack, tmp_path):
    clients = []

    def make(name=None):
        client = FullClient(stack, tmp_path, name)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.net.close()


@pytest.fixture
def simple(stack):
    clients = []

    def make():
        client = SimpleClient(stack)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


def test_registration_and_login_store_a_bcrypt_hash_never_the_password(full):
    ana = full()
    assert ana.controller.register(ana.name, "s3cret pw").ok
    stored = mysql(f"SELECT password_hash FROM users WHERE username='{ana.name}'")
    assert stored.startswith("$2") and len(stored) == 60 and "s3cret" not in stored

    other = full(unique("other"))
    assert not other.controller.sign_in(ana.name, "wrong").ok
    assert other.controller.sign_in(ana.name, "s3cret pw").ok, "the same user may log in from another client"


def test_a_registration_with_a_taken_or_invalid_name_is_refused(full):
    ana = full()
    assert ana.controller.register(ana.name, "pw").ok
    again = full(unique("x"))
    assert not again.controller.register(ana.name, "pw").ok
    for bad in ("with space", "équipe", "a/b"):
        assert not full(unique("y")).api.register(bad, "pw").ok


def test_two_full_clients_chat_in_real_time_and_catch_up_after_reconnecting(full):
    ana, ben = full(), full()
    assert ana.controller.register(ana.name, "pw").ok and ben.controller.register(ben.name, "pw").ok

    chat = unique("team")
    assert ana.controller.create_chat(chat, ben.name).ok
    assert ben.wait_for(lambda: chat in ben.session.chats), "ben is told about the new chat"

    ana.session.active_chat = chat
    reply = ana.controller.send("héllo ben 😀 ñ")
    assert reply.ok and reply.data["sent"]
    assert ben.wait_for(lambda: ben.session.messages.get(chat))
    pushed = ben.session.messages[chat][0]
    assert (pushed["author"], pushed["contents"]) == (ana.name, "héllo ben 😀 ñ")
    assert chat in ben.session.unread_chats

    ben.net.close()  # ben goes offline and misses a message
    ana.controller.send("while you were away")
    ben2 = full(ben.name)
    ben2.persistence = ben.persistence
    ben2.controller = ChatController(ben2.api, ben2.session, ben.persistence)
    assert ben2.controller.sign_in(ben.name, "pw").ok
    contents = [m["contents"] for m in ben2.session.messages[chat]]
    assert contents == ["héllo ben 😀 ñ", "while you were away"], "local copy + delta, with no duplicates"


def test_only_members_can_write_in_a_chat(full):
    ana, eve = full(), full()
    ana.controller.register(ana.name, "pw")
    eve.controller.register(eve.name, "pw")
    chat = unique("private")
    assert ana.controller.create_chat(chat, ana.name + "_x").ok is False  # unknown participant
    assert ana.controller.create_chat(chat, ana.name).ok

    eve.session.active_chat = chat
    assert not eve.controller.send("let me in").ok
    assert mysql(f"SELECT COUNT(*) FROM messages m JOIN chats c ON c.id=m.chat_id WHERE c.name='{chat}'") == "0"


def test_images_and_large_messages_survive_the_whole_path(full, simple, tmp_path):
    ana = full()
    ana.controller.register(ana.name, "pw")
    bob = simple()
    bob_name = unique("bob")
    assert bob.request({"action": "create_user", "username": bob_name, "password": "pw"})["processed"] == 1
    chat = unique("pics")
    assert ana.controller.create_chat(chat, bob_name).ok
    ana.session.active_chat = chat

    picture = tmp_path / "pic.png"
    picture.write_bytes(b"\x89PNG\r\n" + bytes(range(256)) * 400)  # ~100 KB, over the 64 KB of a TEXT column
    assert ana.controller.send(str(picture)).ok

    assert bob.receive() == {"chatname": chat}
    assert bob.receive()["contents"] == "[image]", "a simple client sees a placeholder"

    big = "x" * 300_000
    assert ana.controller.send(big).ok

    reloaded = full(ana.name)
    assert reloaded.controller.sign_in(ana.name, "pw").ok
    stored = reloaded.session.messages[chat]
    reference = stored[0]["contents"]
    assert images.is_image_ref(reference)
    assert (reloaded.persistence.images_dir(ana.name) / images.get_filename(reference)).read_bytes() == picture.read_bytes()
    assert stored[1]["contents"] == big


def test_a_simple_client_uses_the_whole_protocol_in_plain_ascii(full, simple):
    ana, bob = full(), simple()
    ana.controller.register(ana.name, "pw")
    bob_name = unique("bob")

    reply = bob.request({"action": "create_user", "username": bob_name, "password": "pw"})
    assert (reply["processed"], reply["msg"]) == (1, "User added and logged in")

    chat = unique("duo")
    assert bob.request({"action": "create_chat", "chat_name": chat, "participants": [ana.name]})["processed"] == 1
    assert ana.wait_for(lambda: chat in ana.session.chats)

    sent = bob.request({"action": "send_msg", "chat": chat, "msg": "plain ASCII text"})
    assert sent["processed"] == 1 and sent["sent"]
    assert ana.wait_for(lambda: ana.session.messages.get(chat))
    assert ana.session.messages[chat][0]["contents"] == "plain ASCII text"

    ana.session.active_chat = chat
    ana.controller.send("café ☕ for bob")
    pushed = bob.receive()
    assert pushed["contents"] == "caf? ? for bob"

    refused = bob.request({"action": "send_msg", "chat": chat, "msg": "café"})
    assert refused["processed"] == 0 and "ASCII" in refused["msg"]

    delta = bob.request({"action": "load_message_delta", "since": "1970-01-01 00:00:00"})
    assert delta["code"] == 1
    assert [m["contents"] for m in delta["conversations"][chat]] == ["plain ASCII text", "caf? ? for bob"]


def test_a_connection_has_to_say_hello_with_a_known_version(stack):
    with socket.create_connection(("127.0.0.1", stack.server_port), timeout=5) as sock:
        sock.sendall(json.dumps({"action": "login", "username": "x", "password": "y"}).encode() + b"\x04")
        reply = json.loads(sock.recv(4096).rstrip(b"\x04"))
        assert reply["msg"] == "Say hello with your protocol version first"

        sock.sendall(json.dumps({"action": "hello", "version": 7}).encode() + b"\x04")
        reply = json.loads(sock.recv(4096).rstrip(b"\x04"))
        assert reply["processed"] == 0 and reply["supported"] == [1, 2]
        assert sock.recv(4096) == b"", "the server closed the connection"


def test_one_interrupt_shuts_everything_down_cleanly(stack):
    """Regression: the server used to need two Ctrl+C because it blocked in select()."""
    started = time.time()
    stack.server.send_signal(signal.SIGINT)
    assert stack.server.wait(5) == 0
    assert time.time() - started < 3
    assert stack.backend.wait(15) == 0, "the server told the backend to stop"
    assert "Shutdown requested" in (stack.log_dir / "backend.log").read_text()
