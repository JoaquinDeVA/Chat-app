"""Where the server is: command line, then environment variables, then defaults."""

import argparse
import os
from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6969


@dataclass(frozen=True)
class ServerAddress:
    """Host and port of the Rust server."""

    host: str
    port: int


def resolve_address(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> ServerAddress:
    """Works out the server address.

    Precedence: ``--host`` / ``--port``, then ``CHAT_SERVER_HOST`` / ``CHAT_SERVER_PORT``,
    then ``127.0.0.1:6969``.

    :param argv: Command-line arguments (default: ``sys.argv[1:]``).
    :param environ: Environment (default: ``os.environ``).
    :raises SystemExit: If the port is not a valid number (argparse reports it).
    """
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(prog="chat-client", description="Terminal chat client")
    parser.add_argument("--host", default=environ.get("CHAT_SERVER_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(environ.get("CHAT_SERVER_PORT", DEFAULT_PORT)))
    args = parser.parse_args(argv)
    if not 0 < args.port < 65536:
        parser.error(f"port {args.port} is out of range (1-65535)")
    return ServerAddress(args.host, args.port)
