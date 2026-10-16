# Roadmap

Ideas for future versions, roughly in the order they would pay off.

## Security
- **End-to-end encryption of messages.** Today passwords are hashed with BCrypt and the database
  never sees them in the clear, but messages are stored and travel as plain text.
- **TLS between the clients and the server** (and between the server and the backend). Until then the
  server listens on the loopback interface only; see `CHAT_SERVER_BIND` in the README.
- **Encrypt the local copy** the Python client keeps in `chats/` (it is plain JSON lines).

## Protocol
- **Protocol v3**, selected through `hello` like the existing versions: sync with a message-id cursor
  instead of a timestamp, and acknowledgements for delivered messages.
- Mark messages as read and show who is online.

## Clients
- Scrolling through the history in the C client, and unread markers.
- Images in the C client (protocol v2 would be required).
- A web client speaking protocol v2 over WebSocket.

## Data and operations
- Review the database: indexes for the history queries, storage engine options, and an audit log.
- Write errors to a log file next to the standard error stream (today they go to the standard error
  stream only).
- Message retention and pagination of the history.
