# Chat app: build, test and run every component. `make help` lists the targets.

JAR        = backend-java/target/chat-backend-1.0.0.jar
SERVER_BIN = server-rust/target/release/chat-server
PYTHON    ?= python3

help:
	@echo "make build            build the backend, the server and the C client"
	@echo "make test             unit tests of the four components (no database needed)"
	@echo "make e2e              end-to-end test: MySQL in Docker + backend + server + clients"
	@echo "make up | down        start / stop (and wipe) the MySQL container (host port 3323)"
	@echo "make run-backend      run the Java backend            (terminal 1, after 'make up')"
	@echo "make run-server       run the Rust server             (terminal 2)"
	@echo "make run-client       run the Python client (v2)      (terminal 3)"
	@echo "make run-client-c     run the C client (v1)           (terminal 3)"

# ── build ────────────────────────────────────────────────────────────────────────────────────
build: build-backend build-server build-client-c

build-backend:
	cd backend-java && mvn -q package -DskipTests

build-server:
	cd server-rust && cargo build --release --quiet

build-client-c:
	$(MAKE) -C client-c

# ── tests ────────────────────────────────────────────────────────────────────────────────────
test: test-backend test-server test-client-python test-client-c

test-backend:
	cd backend-java && mvn -q test

test-server:
	cd server-rust && cargo test --quiet

test-client-python:
	cd client-python && $(PYTHON) -m pytest -q

test-client-c:
	$(MAKE) -C client-c test

e2e: build-backend build-server
	$(PYTHON) -m pytest tests/e2e -q

# ── MySQL (docker-compose.yml) ───────────────────────────────────────────────────────────────
up:
	docker compose up -d --wait

down:
	docker compose down -v

# ── run ──────────────────────────────────────────────────────────────────────────────────────
run-backend:
	java -jar $(JAR)

run-server:
	./$(SERVER_BIN)

run-client:
	cd client-python && $(PYTHON) -m chat_client

run-client-c:
	./client-c/chat-client

clean:
	cd backend-java && mvn -q clean
	cd server-rust && cargo clean
	$(MAKE) -C client-c clean

.PHONY: help build build-backend build-server build-client-c test test-backend test-server \
        test-client-python test-client-c e2e up down run-backend run-server run-client \
        run-client-c clean
