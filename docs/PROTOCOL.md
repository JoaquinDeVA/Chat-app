# Protocol

There are two protocols: **client ↔ server** (JSON, with versions) and **server ↔ backend** (a request name
followed by JSON). Both frame messages the same way.

## Framing

Every message, in both directions, is UTF-8 text followed by one **end-of-transmission byte (`0x04`)**.
A message may be split over several TCP segments or glued to others; receivers accumulate bytes until they
find `0x04`. The server closes a connection that sends more than 32 MiB without one.

## Client ↔ server

### Opening: `hello`

The first message selects the protocol version. Nothing else is accepted before it.

```json
{"action": "hello", "version": 2}
```

| Reply | Meaning |
|---|---|
| `{"processed":1,"msg":"ok","version":2}` | accepted |
| `{"processed":0,"msg":"Unsupported protocol version","supported":[1,2]}` | refused; the server then closes the connection |
| `{"processed":0,"msg":"Already said hello"}` | `hello` can be sent only once |

### Versions

| | v1 | v2 |
|---|---|---|
| Intended for | simple clients (the C client) | full clients (the Python client) |
| Text a client may send | printable ASCII, 1 to 1000 characters; no images | any text; images allowed |
| Text a client receives | non-ASCII characters replaced by `?`, line breaks by spaces; images replaced by `[image]` | unchanged |
| Reply to `create_user` | one: `"User added and logged in"` | two: `"User added"`, then `"ok"` (the automatic login) |

### Requests

After `hello`, requests are JSON objects with an `action`. The author of anything a client does is the
logged-in user of the connection: a `username` field sent by the client is ignored.

| Action | Fields | Needs login | Reply |
|---|---|---|---|
| `create_user` | `username`, `password` | no | see versions above; errors: name taken or invalid |
| `login` | `username`, `password` | no | `{"processed":1,"msg":"ok"}` or `{"processed":0,"msg":"Authentication failed"}` |
| `load_message_delta` | `since` | yes | `{"code":1,"msg":"","conversations":{"chat":[message, ...]}}` |
| `create_chat` | `chat_name`, `participants` | yes | `{"processed":1,"msg":"Chat created"}` |
| `send_msg` | `chat`, `msg` | yes | `{"processed":1,"msg":"Message sent","sent":"<timestamp>"}` |
| `logout` | | yes | the server closes the connection |

Every failure is `{"processed":0,"msg":"<reason>"}`; the connection stays open. Typical reasons: `You are not
logged in`, `Already logged in`, `Invalid request`, `Server error`, `Could not send message`.

`create_chat` adds the creator to the participants. Chat and user names are 1–100 / 1–50 characters among
ASCII letters, digits, `_`, `-` and `.`.

### Pushes

The server sends these without being asked, to every connection of a member that is logged in (never back
to the connection that caused them):

```json
{"chatname": "team"}
```
when the user was added to a chat, and

```json
{"chatname": "team", "author": "ana", "contents": "hi", "sent": "2026-05-04 10:30:00.123456"}
```
for a new message. A client tells them apart by the presence of `author`.

### Timestamps

`yyyy-MM-dd HH:mm:ss.ffffff` (microseconds), stamped by the server. Clients treat them as opaque text:
they sort correctly as strings and the newest one seen is the `since` of the next `load_message_delta`. The
first synchronization of a device uses `1970-01-01 00:00:00`; the server also accepts timestamps with fewer
fraction digits.

### Images (v2)

An image travels as the text of a message, `[[img]]|.png|<base64>`, with a maximum of 8 MiB per file. The
Python client saves it and keeps `[[img]]|<uuid>.png` as the contents of the message locally. Messages are
stored in a `MEDIUMTEXT` column (16 MB). Simple clients receive `[image]`.

## Server ↔ backend

A request is `RequestName` immediately followed by a JSON object and `0x04`; the reply is a JSON object and
`0x04`. Names are case-insensitive.

| Request | Body | Reply |
|---|---|---|
| `AuthRequest` | `username`, `password` | `{"authorized": bool}` |
| `AddUserRequest` | `username`, `password` | `{"processed": bool}` |
| `CreateChatRequest` | `chatname`, `usernames` | `{"processed": bool}` |
| `SendMessageRequest` | `username`, `chatname`, `message`, `date` | `{"processed": bool}` |
| `GetChatMembersRequest` | `chatname` | `{"members": [...]}` |
| `LOADMESSAGEDELTA` | `username`, `since` | `{"conversations": {"chat": [message, ...]}}` |
| `SHUTDOWN` | `{}` | none: the backend stops |

Errors (malformed request, unknown request, internal failure) are `{"error": "<text>"}`. Passwords travel in
the clear on this local connection and are hashed with BCrypt by the backend.
