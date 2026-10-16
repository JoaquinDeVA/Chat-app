"""NetworkClient against a real socket server run in a thread."""

import socket
import threading
import time

import pytest

from chat_client.network import NetworkClient


@pytest.fixture
def server():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    holder = {}

    def accept():
        holder["conn"], _ = listener.accept()

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield listener.getsockname(), holder, thread
    for sock in (holder.get("conn"), listener):
        if sock:
            sock.close()


def connect(server) -> tuple[NetworkClient, socket.socket]:
    (host, port), holder, thread = server
    client = NetworkClient(host, port)
    client.connect()
    thread.join(2)
    return client, holder["conn"]


def test_send_adds_the_terminator(server):
    client, conn = connect(server)
    client.send('{"action": "logout"}')
    conn.settimeout(2)
    assert conn.recv(100) == b'{"action": "logout"}\x04'
    client.close()


def test_messages_are_split_on_the_terminator_even_when_glued_or_fragmented(server):
    client, conn = connect(server)
    conn.sendall(b'{"n": 1}\x04{"n"')
    time.sleep(0.05)
    conn.sendall(b": 2}\x04")
    assert client.recv(timeout=2) == {"n": 1}
    assert client.recv(timeout=2) == {"n": 2}
    client.close()


def test_recv_times_out_with_none_and_try_recv_does_not_block(server):
    client, _ = connect(server)
    assert client.recv(timeout=0.05) is None
    assert client.try_recv() is None
    client.close()


def test_drain_returns_everything_waiting(server):
    client, conn = connect(server)
    conn.sendall(b'{"a": 1}\x04{"b": 2}\x04')
    time.sleep(0.1)
    assert client.drain() == [{"a": 1}, {"b": 2}]
    assert client.drain() == []
    client.close()


def test_a_closed_connection_stops_the_receiver(server):
    client, conn = connect(server)
    conn.close()
    deadline = time.time() + 2
    while client.running and time.time() < deadline:
        time.sleep(0.02)
    assert not client.running


def test_connecting_to_nothing_raises_and_sending_without_connection_fails():
    free = socket.socket()
    free.bind(("127.0.0.1", 0))
    port = free.getsockname()[1]
    free.close()
    client = NetworkClient("127.0.0.1", port)
    with pytest.raises(OSError):
        client.connect(timeout=0.5)
    with pytest.raises(OSError):
        client.send("x")
