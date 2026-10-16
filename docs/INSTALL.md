# Installation

## Requirements

| Tool | Version | For |
|---|---|---|
| Docker (with Compose v2) | any recent | MySQL |
| Java JDK | 17 or newer | backend |
| Maven | 3.8+ | backend |
| Rust | stable (edition 2024: 1.85+) | server |
| Python | 3.11+ | Python client, end-to-end tests |
| GCC and `libncurses-dev` | | C client |

## 1. Build

```bash
make build
```

This builds `backend-java/target/chat-backend-1.0.0.jar`, `server-rust/target/release/chat-server` and
`client-c/chat-client`. The Python client needs no build.

## 2. The database

```bash
make up      # docker compose up -d --wait
make down    # stop it and delete its data
```

> **The MySQL container is published on host port 3323** (3306 + 17), not on the default 3306, so that it does
> not clash with a MySQL you may already run. To change it: `CHAT_DB_PORT=3400 make up`, and give the backend
> the same port with `CHAT_DB_URL=jdbc:mysql://localhost:3400/chat_app`.

The schema in `shared/database.sql` is loaded the first time the container starts. To use your own MySQL
instead, create the database with that script and set `CHAT_DB_URL`, `CHAT_DB_USER` and `CHAT_DB_PASSWORD`.
`shared/reset_data.sql` empties the tables (`docker exec -i chat-app-mysql mysql -uroot -pchat_root_dev < shared/reset_data.sql`).

## 3. Run

Start the components in this order, each in its own terminal (the backend must be up before the server):

```bash
make run-backend    # Java backend, listens on 9090
make run-server     # Rust server, listens on 127.0.0.1:6969
make run-client     # Python client (full, protocol v2)
make run-client-c   # C client (simple, protocol v1)
```

Stop the server with one Ctrl+C: it tells the backend to stop as well.

All the ports, hosts and credentials are environment variables; the full list is in the
[README](../README.md#ports-and-configuration). A client connects to another host with
`python -m chat_client --host HOST --port PORT` (from `client-python/`) or `./client-c/chat-client --host HOST --port PORT`.

## Private database credentials

Put them in `backend-java/src/main/resources/application-dev.properties` (ignored by git) and start the
backend with `--spring.profiles.active=dev`:

```properties
spring.datasource.url=jdbc:mysql://localhost:3323/chat_app
spring.datasource.username=chat
spring.datasource.password=your_password
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Communications link failure` when starting the backend | MySQL is not up or the port does not match `CHAT_DB_URL` (`make up`, port 3323) |
| The server says `cannot reach the backend` | start the backend first |
| A client says `No connection` | the server is not running or the client points to another host or port |
| `Unsupported protocol version` | a client newer than the server; the reply lists the versions the server speaks |
| Registration says `Names may only contain...` | usernames and chat names are plain ASCII identifiers |
