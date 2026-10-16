# Architecture

## Components

```mermaid
flowchart LR
    subgraph Clients
        PY["Python client<br/>chat_client/"]
        C["C client<br/>client-c/"]
    end
    subgraph Server["Rust server (server-rust/)"]
        SRV["server.rs<br/>poll loop, sockets"]
        SES["sessions.rs<br/>what every request does"]
        VER["versions.rs<br/>v1 / v2 differences"]
        BE["backend.rs<br/>Backend trait + TCP client"]
        SRV --> SES --> VER
        SES --> BE
    end
    subgraph Java["Java backend (backend-java/)"]
        TCP["tcp/TcpServer"] --> DIS["protocol/RequestDispatcher"]
        DIS --> SVC["service/<br/>User, Chat, Message"]
        SVC --> REP["repository/ (Spring Data)"]
    end
    PY & C -- "JSON, TCP 6969" --> SRV
    BE -- "Name{json}, TCP 9090" --> TCP
    REP -- JDBC --> DB[("MySQL")]
```

| Component | Responsibility | Why it is separate |
|---|---|---|
| Clients | Show the conversations and read what the user types | Two clients with different capabilities share one server |
| Rust server | Connections, login state, **push** to online users, protocol versions | Keeps long-lived connections; the backend can be request/response |
| Java backend | Business rules (who may write where), password hashing, persistence | The only part that knows the database |
| MySQL | Durable data | |

## The server is written for testing

`sessions.rs` contains the behaviour of every request and knows nothing about sockets or Java: it is
generic over a `Backend` trait and over a `Write`. The tests run the whole protocol against an in-memory
backend and in-memory connections; `server.rs` is a thin `poll(2)` loop that moves bytes in and out, and
wakes up every 100 ms so that a shutdown request is noticed at once.

## Protocol versions

```mermaid
flowchart TD
    A["client connects"] --> B["hello {version}"]
    B -- "1 or 2" --> C["session gets a Protocol implementation"]
    B -- "anything else" --> X["error with the supported versions, connection closed"]
    C --> D["registration, login, chats, history: shared code"]
    C --> E["differences, one method each:<br/>check_message · present · registration_sends_login_reply"]
```

`Protocol` is a trait whose default methods are the behaviour of the full version; `V1` overrides only what
differs. Adding a version is writing one `impl` and one line in `for_version`.

## A message from a full client to a simple one

```mermaid
sequenceDiagram
    participant A as Ana (v2)
    participant S as Rust server
    participant J as Java backend
    participant B as Bob (v1)
    A->>S: {"action":"send_msg","chat":"duo","msg":"café 😀"}
    S->>S: v2.check_message → accepted
    S->>J: SendMessageRequest{...}
    J-->>S: {"processed":true}
    S->>J: GetChatMembersRequest{"chatname":"duo"}
    J-->>S: {"members":["ana","bob"]}
    S-->>B: push {"contents":"caf? ?",...}   (v1.present)
    S-->>A: {"processed":1,"msg":"Message sent","sent":"2026-05-04 10:30:00.123456"}
```

The database keeps the original text; each recipient receives it as its protocol version presents it.

## Signing in and catching up

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant J as Backend
    C->>S: hello {version}
    S-->>C: ok
    C->>S: login {username, password}
    S->>J: AuthRequest{...}
    J-->>S: {"authorized":true}
    S-->>C: {"processed":1,"msg":"ok"}
    Note over C: asks for what it does not have yet:<br/>since = newest timestamp it stored
    C->>S: load_message_delta {since}
    S->>J: LOADMESSAGEDELTA{username, since}
    J-->>S: {"conversations":{"chat":[...]}}
    S-->>C: {"code":1,"conversations":{...}}
```

The cursor is a timestamp with **microsecond** precision: with whole seconds, a message sent in the same
second as the newest one a client already had would be lost.

## Client structure

```mermaid
stateDiagram-v2
    [*] --> AUTH
    AUTH --> LIVE: login or registration ok
    LIVE --> EXIT: q
    AUTH --> EXIT: q
    state LIVE {
        [*] --> NAVIGATION
        NAVIGATION --> INPUT: Enter
        NAVIGATION --> NEW_CHAT: n
        INPUT --> NAVIGATION: Enter or Esc
        NEW_CHAT --> NAVIGATION: Enter or Esc
    }
```

The Python client keeps what happens (`controller.py`: sign in, synchronize, receive pushes, send, create
chats) apart from what is shown (`tui.py`, `app.py`), so the first is tested without a terminal.

## Backend layers

`tcp/TcpServer` frames UTF-8 messages and answers one at a time; `protocol/RequestDispatcher` routes
`RequestName{json}` to a handler and turns every failure into a valid JSON error; handlers call the
services (`UserService`, `ChatService`, `MessageService`), which use four Spring Data repositories. Handlers
are declared in one place (`ProtocolConfig`).

## Data model

```mermaid
erDiagram
    users ||--o{ chat_members : "belongs to"
    chats ||--o{ chat_members : "has"
    chats ||--o{ messages : contains
    users ||--o{ messages : writes
    users {
        bigint id PK
        varchar username UK
        varchar password_hash "BCrypt"
    }
    chats {
        bigint id PK
        varchar name UK
    }
    chat_members {
        bigint user_id PK,FK
        bigint chat_id PK,FK
        datetime joined_at
    }
    messages {
        bigint id PK
        bigint chat_id FK
        bigint author_id FK
        mediumtext content "up to 16 MB (images)"
        datetime6 sent_at "microseconds, indexed with chat_id"
    }
```
