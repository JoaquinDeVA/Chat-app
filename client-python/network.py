"""Capa de transporte TCP con recepción en hilo de fondo.

El hilo receptor acumula bytes hasta encontrar el delimitador EOT (0x04) y
encola cada mensaje completo en `recv_queue`. Las llamadas a `recv` y
`try_recv` consumen de esa cola sin bloquear el hilo principal.
"""

import socket
import threading
from queue import Queue, Empty
from protocol import EOT, frame_message, parse_response


class NetworkClient:
    """Cliente TCP que desacopla envío y recepción mediante una cola interna."""

    def __init__(self, ip, port):
        """Prepara el cliente; la conexión no se abre hasta llamar a `connect`."""
        self.addr = (ip, port)
        self.sock = None
        self.recv_queue = Queue()
        self.running = False
        self._recv_thread = None

    def connect(self):
        """Abre la conexión TCP e inicia el hilo receptor en segundo plano."""
        self.sock = socket.create_connection(self.addr)
        self.running = True
        self._recv_thread = threading.Thread(target=self._receiver, daemon=True)
        self._recv_thread.start()

    def send(self, msg):
        """Envía `msg` (str o bytes) al servidor añadiendo el framing EOT."""
        data = frame_message(msg)
        self.sock.sendall(data)

    def _receiver(self):
        """Hilo interno: lee bytes del socket, separa mensajes por EOT y los encola."""
        buf = b''
        while self.running:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.running = False
                    break
                buf += chunk
                while EOT in buf:
                    msg, buf = buf.split(EOT, 1)
                    self.recv_queue.put(msg)
            except Exception:
                self.running = False
                break

    def recv(self, timeout=None):
        """Espera (bloqueante con timeout) el próximo mensaje y lo devuelve parseado.

        Devuelve None si se agota el timeout sin recibir nada.
        """
        try:
            msg = self.recv_queue.get(timeout=timeout)
            return parse_response(msg)
        except Empty:
            return None

    def try_recv(self):
        """Intenta leer un mensaje sin bloquear; devuelve None si la cola está vacía."""
        try:
            msg = self.recv_queue.get_nowait()
            return parse_response(msg)
        except Empty:
            return None

    def close(self):
        """Detiene el hilo receptor y cierra el socket."""
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.sock.close()
