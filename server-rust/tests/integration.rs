//! The real server over real sockets, with a small in-memory stand-in for the Java backend.

use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use chat_server::backend::TcpBackend;
use chat_server::protocol::EOT;
use chat_server::server::Server;
use serde_json::{Value, json};

/// Speaks the backend protocol with an in-memory database. Returns the requests it received.
fn spawn_backend() -> (String, JoinHandle<Vec<String>>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap().to_string();
    let handle = thread::spawn(move || {
        let mut users: BTreeMap<String, String> = BTreeMap::new();
        let mut chats: BTreeMap<String, Vec<String>> = BTreeMap::new();
        let mut messages: Vec<Value> = Vec::new();
        let mut log = Vec::new();

        let (mut stream, _) = listener.accept().unwrap();
        let mut pending = Vec::new();
        let mut chunk = [0u8; 4096];
        loop {
            let read = stream.read(&mut chunk).unwrap_or(0);
            if read == 0 {
                return log;
            }
            pending.extend_from_slice(&chunk[..read]);
            while let Some(end) = pending.iter().position(|b| *b == EOT) {
                let request: Vec<u8> = pending.drain(..=end).collect();
                let text = String::from_utf8(request[..request.len() - 1].to_vec()).unwrap();
                log.push(text.clone());
                let brace = text.find('{').unwrap();
                let (header, body) = (&text[..brace], &text[brace..]);
                let body: Value = serde_json::from_str(body).unwrap();
                let reply = match header {
                    "SHUTDOWN" => return log,
                    "AddUserRequest" => {
                        let name = body["username"].as_str().unwrap().to_string();
                        let fresh = !users.contains_key(&name);
                        if fresh {
                            users.insert(name, body["password"].as_str().unwrap().to_string());
                        }
                        json!({"processed": fresh})
                    }
                    "AuthRequest" => {
                        let ok = users
                            .get(body["username"].as_str().unwrap())
                            .map(String::as_str)
                            == body["password"].as_str();
                        json!({"authorized": ok})
                    }
                    "CreateChatRequest" => {
                        let name = body["chatname"].as_str().unwrap().to_string();
                        let members: Vec<String> = body["usernames"]
                            .as_array()
                            .unwrap()
                            .iter()
                            .map(|u| u.as_str().unwrap().to_string())
                            .collect();
                        let fresh = !chats.contains_key(&name);
                        if fresh {
                            chats.insert(name, members);
                        }
                        json!({"processed": fresh})
                    }
                    "SendMessageRequest" => {
                        messages.push(json!({
                            "chatname": body["chatname"], "author": body["username"],
                            "contents": body["message"], "sent": body["date"]
                        }));
                        json!({"processed": true})
                    }
                    "GetChatMembersRequest" => {
                        json!({"members": chats.get(body["chatname"].as_str().unwrap()).cloned().unwrap_or_default()})
                    }
                    "LOADMESSAGEDELTA" => {
                        let user = body["username"].as_str().unwrap();
                        let mut conversations = serde_json::Map::new();
                        for (chat, members) in &chats {
                            if members.iter().any(|m| m == user) {
                                let list: Vec<&Value> = messages
                                    .iter()
                                    .filter(|m| m["chatname"] == json!(chat))
                                    .collect();
                                conversations.insert(chat.clone(), json!(list));
                            }
                        }
                        json!({ "conversations": conversations })
                    }
                    other => json!({"error": format!("unknown {other}")}),
                };
                stream.write_all(reply.to_string().as_bytes()).unwrap();
                stream.write_all(&[EOT]).unwrap();
            }
        }
    });
    (address, handle)
}

struct RunningServer {
    address: String,
    shutdown: Arc<AtomicBool>,
    server: JoinHandle<()>,
    backend: JoinHandle<Vec<String>>,
}

fn start() -> RunningServer {
    let (backend_address, backend) = spawn_backend();
    let mut server = Server::bind(
        "127.0.0.1:0",
        TcpBackend::connect(&backend_address).unwrap(),
    )
    .unwrap();
    let address = server.local_addr().unwrap().to_string();
    let shutdown = Arc::new(AtomicBool::new(false));
    let flag = Arc::clone(&shutdown);
    let server = thread::spawn(move || server.serve(&flag));
    RunningServer {
        address,
        shutdown,
        server,
        backend,
    }
}

impl RunningServer {
    /// A client that speaks protocol `version`, already introduced with `hello`.
    fn client_v(&self, version: u32) -> Client {
        let mut client = self.raw_client();
        client.send(json!({"action":"hello","version":version}));
        assert_eq!(client.recv().unwrap()["version"], version);
        client
    }

    /// A full (version 2) client.
    fn client(&self) -> Client {
        self.client_v(2)
    }

    /// A connection that has not said hello yet.
    fn raw_client(&self) -> Client {
        let stream = TcpStream::connect(&self.address).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(5)))
            .unwrap();
        Client {
            stream,
            pending: Vec::new(),
        }
    }

    /// Stops the server and returns what the backend received, checking both stop in time.
    fn stop(self) -> Vec<String> {
        let started = Instant::now();
        self.shutdown.store(true, Ordering::SeqCst);
        self.server.join().unwrap();
        assert!(
            started.elapsed() < Duration::from_secs(2),
            "the server must stop promptly"
        );
        self.backend.join().unwrap()
    }
}

struct Client {
    stream: TcpStream,
    pending: Vec<u8>,
}

impl Client {
    fn send(&mut self, request: Value) {
        let mut bytes = serde_json::to_vec_pretty(&request).unwrap();
        bytes.push(EOT);
        self.stream.write_all(&bytes).unwrap();
    }

    /// Next message from the server, or None if the connection was closed.
    fn recv(&mut self) -> Option<Value> {
        loop {
            if let Some(end) = self.pending.iter().position(|b| *b == EOT) {
                let message: Vec<u8> = self.pending.drain(..=end).collect();
                return Some(serde_json::from_slice(&message[..message.len() - 1]).unwrap());
            }
            let mut chunk = [0u8; 4096];
            match self.stream.read(&mut chunk) {
                Ok(0) => return None,
                Ok(read) => self.pending.extend_from_slice(&chunk[..read]),
                Err(error) => panic!("no message from the server: {error}"),
            }
        }
    }

    fn register(&mut self, name: &str) {
        self.send(json!({"action":"create_user","username":name,"password":"pw"}));
        assert_eq!(self.recv().unwrap()["msg"], "User added");
        assert_eq!(self.recv().unwrap()["msg"], "ok");
    }
}

#[test]
fn a_conversation_between_two_clients() {
    let running = start();
    let (mut ana, mut ben) = (running.client(), running.client());
    ana.register("ana");
    ben.register("ben");

    ana.send(json!({"action":"create_chat","chat_name":"equipe","participants":["ben"]}));
    assert_eq!(ana.recv().unwrap()["msg"], "Chat created");
    assert_eq!(ben.recv().unwrap(), json!({"chatname":"equipe"}));

    ana.send(json!({"action":"send_msg","username":"ana","chat":"equipe","msg":"hola ñ 😀"}));
    assert_eq!(ana.recv().unwrap()["msg"], "Message sent");
    let pushed = ben.recv().unwrap();
    assert_eq!(pushed["author"], "ana");
    assert_eq!(pushed["contents"], "hola ñ 😀");
    assert_eq!(pushed["chatname"], "equipe");

    ben.send(json!({"action":"load_message_delta","username":"ben","since":"2000-01-01 00:00:00"}));
    let delta = ben.recv().unwrap();
    assert_eq!(delta["code"], 1);
    assert_eq!(delta["conversations"]["equipe"][0]["contents"], "hola ñ 😀");

    ana.send(json!({"action":"logout"}));
    assert!(ana.recv().is_none(), "logout closes the connection");

    let requests = running.stop();
    assert!(
        requests.last().unwrap().starts_with("SHUTDOWN"),
        "the backend is told to stop"
    );
}

#[test]
fn a_bad_login_does_not_open_a_session() {
    let running = start();
    let mut client = running.client();
    client.send(json!({"action":"login","username":"ghost","password":"x"}));
    assert_eq!(client.recv().unwrap()["msg"], "Authentication failed");
    client.send(json!({"action":"send_msg","chat":"c","msg":"hi"}));
    assert_eq!(client.recv().unwrap()["msg"], "You are not logged in");
    running.stop();
}

#[test]
fn shutdown_is_noticed_promptly_with_idle_clients_connected() {
    // Regression: select() blocked without a timeout, so Ctrl+C was only noticed when some
    // client sent something (hence "it needs two interrupts").
    let running = start();
    let _idle_a = running.client();
    let _idle_b = running.client();
    thread::sleep(Duration::from_millis(200));
    running.stop();
}

#[test]
fn a_client_that_disconnects_does_not_affect_the_others() {
    let running = start();
    let mut ana = running.client();
    ana.register("ana");
    {
        let mut ben = running.client();
        ben.register("ben");
        ana.send(json!({"action":"create_chat","chat_name":"c","participants":["ben"]}));
        assert_eq!(ana.recv().unwrap()["msg"], "Chat created");
    } // ben disconnects abruptly
    thread::sleep(Duration::from_millis(200));
    ana.send(json!({"action":"send_msg","chat":"c","msg":"anyone?"}));
    assert_eq!(ana.recv().unwrap()["msg"], "Message sent");
    running.stop();
}

#[test]
fn a_message_sent_in_pieces_is_assembled() {
    let running = start();
    let mut client = running.client();
    let request = br#"{"action":"login","username":"ghost","password":"x"}"#;
    client.stream.write_all(&request[..15]).unwrap();
    thread::sleep(Duration::from_millis(150));
    client.stream.write_all(&request[15..]).unwrap();
    client.stream.write_all(&[EOT]).unwrap();
    assert_eq!(client.recv().unwrap()["msg"], "Authentication failed");
    running.stop();
}

#[test]
fn a_simple_and_a_full_client_share_a_chat() {
    let running = start();
    let mut full = running.client_v(2);
    let mut simple = running.client_v(1);
    full.register("ana");
    simple.send(json!({"action":"create_user","username":"bob","password":"pw"}));
    assert_eq!(
        simple.recv().unwrap()["msg"],
        "User added and logged in",
        "a version 1 registration is a single reply"
    );

    full.send(json!({"action":"create_chat","chat_name":"duo","participants":["bob"]}));
    assert_eq!(full.recv().unwrap()["msg"], "Chat created");
    assert_eq!(simple.recv().unwrap(), json!({"chatname":"duo"}));

    full.send(json!({"action":"send_msg","chat":"duo","msg":"café 😀"}));
    assert_eq!(full.recv().unwrap()["msg"], "Message sent");
    assert_eq!(simple.recv().unwrap()["contents"], "caf? ?");

    simple.send(json!({"action":"send_msg","chat":"duo","msg":"plain ascii"}));
    assert_eq!(simple.recv().unwrap()["msg"], "Message sent");
    assert_eq!(full.recv().unwrap()["contents"], "plain ascii");

    simple.send(json!({"action":"send_msg","chat":"duo","msg":"niño"}));
    assert_eq!(
        simple.recv().unwrap()["processed"],
        0,
        "a simple client cannot send non-ASCII text"
    );
    running.stop();
}

#[test]
fn a_connection_must_say_hello_and_an_unknown_version_is_dropped() {
    let running = start();
    let mut silent = running.raw_client();
    silent.send(json!({"action":"login","username":"ana","password":"pw"}));
    assert_eq!(
        silent.recv().unwrap()["msg"],
        "Say hello with your protocol version first"
    );

    let mut future = running.raw_client();
    future.send(json!({"action":"hello","version":9}));
    let reply = future.recv().unwrap();
    assert_eq!(reply["supported"], json!([1, 2]));
    assert!(future.recv().is_none(), "the server closes the connection");
    running.stop();
}
