JAVA_JAR   = backend-java/target/chat-0.0.1-SNAPSHOT.jar
RUST_BIN   = server-rust/target/release/serv7

# ── Build ────────────────────────────────────────────────────────────────────

build: build-backend build-server build-client-c

build-backend:
	cd backend-java && mvn package -DskipTests -q

build-server:
	cd server-rust && cargo build --release --quiet

build-client-c:
	$(MAKE) -C client-c

# ── Run (open each in its own terminal) ──────────────────────────────────────

run-backend:
	java -jar $(JAVA_JAR) --spring.profiles.active=dev

run-server:
	./$(RUST_BIN)

run-client-python:
	cd client-python && python3 main.py

run-client-c:
	cd client-c && ./cli7

# ── Clean ────────────────────────────────────────────────────────────────────

clean: clean-backend clean-server clean-client-c

clean-backend:
	cd backend-java && mvn clean -q

clean-server:
	rm -rf server-rust/target server-rust/Cargo.lock

clean-client-c:
	$(MAKE) -C client-c clean

.PHONY: build build-backend build-server build-client-c \
        run-backend run-server run-client-python run-client-c \
        clean clean-backend clean-server clean-client-c
