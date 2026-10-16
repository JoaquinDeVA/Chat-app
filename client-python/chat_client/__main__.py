"""``python -m chat_client [--host HOST] [--port PORT]``."""

import curses
import os
import sys

from .app import MessagingApp
from .config import resolve_address


def main() -> int:
    """Starts the curses application.

    :return: Process exit code.
    """
    address = resolve_address()
    os.environ.setdefault("ESCDELAY", "25")  # make the Esc key react at once

    def run(stdscr) -> None:
        app = MessagingApp(stdscr, address)
        try:
            app.run()
        except KeyboardInterrupt:
            pass
        finally:
            app.cleanup()

    curses.wrapper(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
