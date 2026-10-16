"""TCP transport with a background receiver.

The receiver thread accumulates bytes until it finds the end-of-transmission byte and queues
every complete message; :meth:`NetworkClient.recv` and :meth:`NetworkClient.try_recv` take them
from the queue, so the interface never blocks on the socket.
"""

import logging
import socket
import threading
from queue import Empty, Queue
from typing import Any

from .protocol import EOT, frame_message, parse_response

log = logging.getLogger(__name__)


class NetworkClient:
    """TCP client that decouples sending from receiving through an internal queue.

    :param host: Server host.
    :param port: Server port.
    """

    def __init__(self, host: str, port: int):
        self.address = (host, port)
        self.sock: socket.socket | None = None
        self.recv_queue: Queue[bytes] = Queue()
        self.running = False
        self._receiver_thread: threading.Thread | None = None

    def connect(self, timeout: float = 5.0) -> None:
        """Opens the connection and starts the receiver thread.

        :raises OSError: If the server cannot be reached.
        """
        self.sock = socket.create_connection(self.address, timeout=timeout)
        self.sock.settimeout(None)
        self.running = True
        self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._receiver_thread.start()

    def send(self, message: str | bytes) -> None:
        """Sends ``message`` (adding the end-of-transmission byte).

        :raises OSError: If the connection is closed.
        """
        if self.sock is None:
            raise OSError("not connected")
        self.sock.sendall(frame_message(message))

    def _receive_loop(self) -> None:
        """Receiver thread: reads bytes, splits them into messages and queues them."""
        buffer = b""
        while self.running:
            try:
                chunk = self.sock.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while EOT in buffer:
                message, buffer = buffer.split(EOT, 1)
                self.recv_queue.put(message)
        self.running = False

    def recv(self, timeout: float | None = None) -> Any:
        """Waits for the next message.

        :param timeout: Seconds to wait; ``None`` waits forever.
        :return: The decoded message, or ``None`` on timeout.
        """
        try:
            return parse_response(self.recv_queue.get(timeout=timeout))
        except Empty:
            return None

    def try_recv(self) -> Any:
        """The next message if there is one, without waiting; ``None`` otherwise."""
        try:
            return parse_response(self.recv_queue.get_nowait())
        except Empty:
            return None

    def drain(self) -> list[Any]:
        """Removes and returns every message waiting in the queue."""
        messages = []
        while (message := self.try_recv()) is not None:
            messages.append(message)
        return messages

    def close(self) -> None:
        """Stops the receiver and closes the socket."""
        self.running = False
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
            self.sock = None
