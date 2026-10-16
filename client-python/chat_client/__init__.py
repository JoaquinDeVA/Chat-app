"""Terminal chat client (curses).

Layers, from the network up:

* :mod:`~chat_client.protocol` / :mod:`~chat_client.network` - JSON messages ended by ``0x04``
  over TCP, with a background receiver thread;
* :mod:`~chat_client.api` - one method per operation of the server;
* :mod:`~chat_client.controller` - what the application does (log in, sync, send, receive),
  with no screen code, so it is fully testable;
* :mod:`~chat_client.tui` and :mod:`~chat_client.app` - the curses interface.
"""
