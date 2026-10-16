# Changelog

## 1.0.0

First public version. It started as a university practical on distributed programming (a chat in
four languages) and was then reworked into a tested, documented project.

### Added
- **Protocol versions.** Every client opens with `{"action":"hello","version":N}`. Version 1 is the
  simple protocol (plain ASCII text, no images, one reply to a registration) and version 2 the full one
  (Unicode, images). The server implements only what differs between them behind a `Protocol` trait.
- Docker Compose for MySQL (host port **3323**), environment-variable configuration for every component,
  a root `Makefile`, an end-to-end test suite and CI.
- Unit tests for the four components (44 Java, 60 Rust, 110 Python, 165 C checks) and 8 end-to-end scenarios.

### Changed
- Java backend rewritten: English domain and schema, shared repositories, one request dispatcher,
  records instead of Lombok, UTF-8 TCP framing, structured logging.
- Rust server rewritten as a library plus a binary; the logic of every request is independent of
  the sockets and is tested with an in-memory backend.
- Python client rewritten as a package with a controller separated from the curses screens; the C client
  rewritten on top of a small JSON toolkit and reduced to the simple (v1) feature set.
- Names (users and chats) are plain ASCII identifiers.
- Messages must be sent by a member of the chat.

### Fixed
- Passwords were "encrypted" with a reversible Caesar cipher: they are now hashed with BCrypt.
- Messages sent in the same second as the last one a client had received were never synchronized;
  timestamps now have microsecond precision.
- The server needed two Ctrl+C to stop; it now stops on the first one and stops the backend too.
- Several malformed-JSON and Unicode problems in the backend, the server and the C client; clients could
  send messages as another user.
