"""Starts the whole stack for the end-to-end tests: MySQL (Docker), backend and server."""

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client-python"))

JAR = ROOT / "backend-java" / "target" / "chat-backend-1.0.0.jar"
SERVER = ROOT / "server-rust" / "target" / "release" / "chat-server"
DB_PORT = os.environ.get("CHAT_DB_PORT", "3323")
DB_CONTAINER = "chat-app-mysql"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_port(port: int, process: subprocess.Popen, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"process exited early with code {process.returncode}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"nothing listening on port {port}")


def mysql(sql: str, user: str = "chat", password: str = "chat_dev") -> str:
    """Runs ``sql`` inside the MySQL container and returns the raw output."""
    result = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "mysql", f"-u{user}", f"-p{password}", "chat_app", "-N", "-B", "-e", sql],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@dataclass
class Stack:
    server_port: int
    backend_port: int
    server: subprocess.Popen
    backend: subprocess.Popen
    log_dir: Path


@pytest.fixture(scope="session")
def stack(tmp_path_factory):
    missing = [str(p) for p in (JAR, SERVER) if not p.exists()]
    if missing or not shutil.which("docker") or not shutil.which("java"):
        pytest.skip(f"needs docker, java and the build artifacts (run `make build`); missing: {missing}")

    subprocess.run(["docker", "compose", "up", "-d", "--wait"], cwd=ROOT, check=True, capture_output=True)
    mysql("SET FOREIGN_KEY_CHECKS=0; TRUNCATE messages; TRUNCATE chat_members; TRUNCATE chats; TRUNCATE users;"
          " SET FOREIGN_KEY_CHECKS=1;", user="root", password="chat_root_dev")

    log_dir = tmp_path_factory.mktemp("logs")
    backend_port, server_port = free_port(), free_port()
    env = dict(os.environ, CHAT_DB_URL=f"jdbc:mysql://localhost:{DB_PORT}/chat_app",
               CHAT_BACKEND_PORT=str(backend_port), CHAT_SERVER_PORT=str(server_port),
               CHAT_BACKEND_HOST="127.0.0.1")

    backend = subprocess.Popen(["java", "-jar", str(JAR)], env=env, cwd=ROOT,
                               stdout=open(log_dir / "backend.log", "w"), stderr=subprocess.STDOUT)
    server = None
    try:
        wait_for_port(backend_port, backend)
        server = subprocess.Popen([str(SERVER)], env=env, cwd=ROOT,
                                  stdout=open(log_dir / "server.log", "w"), stderr=subprocess.STDOUT)
        wait_for_port(server_port, server, timeout=15)
    except Exception:
        for process in (server, backend):
            if process and process.poll() is None:
                process.kill()
        print((log_dir / "backend.log").read_text()[-3000:])
        raise

    yield Stack(server_port, backend_port, server, backend, log_dir)

    for process in (server, backend):
        if process.poll() is None:  # a test that did not shut the stack down cleanly
            process.send_signal(signal.SIGINT)
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
