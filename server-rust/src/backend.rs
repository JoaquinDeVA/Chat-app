//! The backend interface and its TCP implementation.

use std::collections::BTreeMap;
use std::fmt;
use std::io::{self, Read, Write};
use std::net::TcpStream;

use serde::Serialize;
use serde::de::DeserializeOwned;

use crate::protocol::{
    AuthorizedReply, ChatMessage, ChatNameBody, CreateChatBody, Credentials, DeltaBody, DeltaReply,
    EOT, MembersReply, ProcessedReply, SendMessageBody, encode_backend_request,
};

/// Why a backend call failed.
#[derive(Debug)]
pub enum BackendError {
    /// The connection to the backend failed.
    Io(io::Error),
    /// The backend answered with something that is not the expected JSON.
    Protocol(String),
}

impl fmt::Display for BackendError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            BackendError::Io(error) => write!(f, "backend connection error: {error}"),
            BackendError::Protocol(detail) => write!(f, "unexpected backend reply: {detail}"),
        }
    }
}

impl std::error::Error for BackendError {}

impl From<io::Error> for BackendError {
    fn from(error: io::Error) -> Self {
        BackendError::Io(error)
    }
}

/// Result of a backend call.
pub type BackendResult<T> = Result<T, BackendError>;

/// Everything the server needs from the application layer.
///
/// Sessions are written against this trait so that they can be tested with an in-memory fake.
pub trait Backend {
    /// Registers a user; `false` if the name is taken or invalid.
    fn add_user(&mut self, username: &str, password: &str) -> BackendResult<bool>;
    /// Checks a username/password pair.
    fn authenticate(&mut self, username: &str, password: &str) -> BackendResult<bool>;
    /// Creates a chat with the given members; `false` if it could not be created.
    fn create_chat(&mut self, chat: &str, usernames: &[String]) -> BackendResult<bool>;
    /// Stores a message; `false` if it was rejected (unknown chat, not a member...).
    fn send_message(
        &mut self,
        username: &str,
        chat: &str,
        text: &str,
        sent: &str,
    ) -> BackendResult<bool>;
    /// Usernames of the members of a chat (empty if it does not exist).
    fn chat_members(&mut self, chat: &str) -> BackendResult<Vec<String>>;
    /// Messages of every chat of `username` sent after `since`.
    fn message_delta(
        &mut self,
        username: &str,
        since: &str,
    ) -> BackendResult<BTreeMap<String, Vec<ChatMessage>>>;
    /// Tells the backend to stop.
    fn shutdown(&mut self);
}

/// [`Backend`] over one persistent TCP connection to the Java backend.
///
/// If the connection breaks, the request is retried once on a fresh connection.
pub struct TcpBackend {
    address: String,
    stream: TcpStream,
}

impl TcpBackend {
    /// Connects to the backend at `address` (`host:port`).
    pub fn connect(address: &str) -> io::Result<Self> {
        Ok(TcpBackend {
            address: address.to_owned(),
            stream: TcpStream::connect(address)?,
        })
    }

    fn exchange(&mut self, request: &[u8]) -> io::Result<Vec<u8>> {
        self.stream.write_all(request)?;
        let mut reply = Vec::new();
        let mut chunk = [0u8; 4096];
        loop {
            let read = self.stream.read(&mut chunk)?;
            if read == 0 {
                return Err(io::Error::new(
                    io::ErrorKind::UnexpectedEof,
                    "backend closed the connection",
                ));
            }
            if let Some(end) = chunk[..read].iter().position(|byte| *byte == EOT) {
                reply.extend_from_slice(&chunk[..end]);
                return Ok(reply);
            }
            reply.extend_from_slice(&chunk[..read]);
        }
    }

    fn call<B: Serialize, R: DeserializeOwned>(
        &mut self,
        header: &str,
        body: &B,
    ) -> BackendResult<R> {
        let request = encode_backend_request(header, body);
        let reply = match self.exchange(&request) {
            Ok(reply) => reply,
            Err(first) => {
                log::warn!("backend request failed ({first}); reconnecting");
                self.stream = TcpStream::connect(&self.address)?;
                self.exchange(&request)?
            }
        };
        serde_json::from_slice(&reply).map_err(|error| {
            BackendError::Protocol(format!("{error}: {}", String::from_utf8_lossy(&reply)))
        })
    }
}

impl Backend for TcpBackend {
    fn add_user(&mut self, username: &str, password: &str) -> BackendResult<bool> {
        let reply: ProcessedReply =
            self.call("AddUserRequest", &Credentials { username, password })?;
        Ok(reply.processed)
    }

    fn authenticate(&mut self, username: &str, password: &str) -> BackendResult<bool> {
        let reply: AuthorizedReply =
            self.call("AuthRequest", &Credentials { username, password })?;
        Ok(reply.authorized)
    }

    fn create_chat(&mut self, chat: &str, usernames: &[String]) -> BackendResult<bool> {
        let reply: ProcessedReply = self.call(
            "CreateChatRequest",
            &CreateChatBody {
                chatname: chat,
                usernames,
            },
        )?;
        Ok(reply.processed)
    }

    fn send_message(
        &mut self,
        username: &str,
        chat: &str,
        text: &str,
        sent: &str,
    ) -> BackendResult<bool> {
        let body = SendMessageBody {
            username,
            chatname: chat,
            message: text,
            date: sent,
        };
        let reply: ProcessedReply = self.call("SendMessageRequest", &body)?;
        Ok(reply.processed)
    }

    fn chat_members(&mut self, chat: &str) -> BackendResult<Vec<String>> {
        let reply: MembersReply =
            self.call("GetChatMembersRequest", &ChatNameBody { chatname: chat })?;
        Ok(reply.members)
    }

    fn message_delta(
        &mut self,
        username: &str,
        since: &str,
    ) -> BackendResult<BTreeMap<String, Vec<ChatMessage>>> {
        let reply: DeltaReply = self.call("LOADMESSAGEDELTA", &DeltaBody { username, since })?;
        Ok(reply.conversations)
    }

    fn shutdown(&mut self) {
        let request = encode_backend_request("SHUTDOWN", &serde_json::json!({}));
        if let Err(error) = self
            .stream
            .write_all(&request)
            .and_then(|()| self.stream.flush())
        {
            log::warn!("could not tell the backend to shut down: {error}");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;
    use std::thread;

    /// Backend stand-in: answers every request with the next canned reply and records requests.
    fn stub(
        replies: Vec<&'static str>,
        drop_first_connection: bool,
    ) -> (String, thread::JoinHandle<Vec<String>>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap().to_string();
        let handle = thread::spawn(move || {
            let mut requests = Vec::new();
            let mut replies = replies.into_iter();
            let mut first = true;
            'accept: for stream in listener.incoming() {
                let mut stream = stream.unwrap();
                let mut pending = Vec::new();
                let mut chunk = [0u8; 4096];
                'connection: loop {
                    let read = stream.read(&mut chunk).unwrap_or(0);
                    if read == 0 {
                        break;
                    }
                    pending.extend_from_slice(&chunk[..read]);
                    while let Some(end) = pending.iter().position(|b| *b == EOT) {
                        let request: Vec<u8> = pending.drain(..=end).collect();
                        let text =
                            String::from_utf8_lossy(&request[..request.len() - 1]).into_owned();
                        let is_shutdown = text.starts_with("SHUTDOWN");
                        requests.push(text);
                        if is_shutdown {
                            break 'accept;
                        }
                        if first && drop_first_connection {
                            first = false;
                            break 'connection; // close without answering: a broken connection
                        }
                        let Some(reply) = replies.next() else {
                            break 'accept;
                        };
                        stream.write_all(reply.as_bytes()).unwrap();
                        stream.write_all(&[EOT]).unwrap();
                    }
                }
            }
            requests
        });
        (address, handle)
    }

    #[test]
    fn requests_use_the_header_json_eot_format_and_replies_are_parsed() {
        let (address, handle) = stub(
            vec![
                r#"{"processed":true}"#,
                r#"{"authorized":false}"#,
                r#"{"members":["ana","ben"]}"#,
                r#"{"conversations":{"team":[{"chatname":"team","author":"ana","contents":"hi","sent":"2026-05-04 10:30:05"}],"quiet":[]}}"#,
            ],
            false,
        );
        let mut backend = TcpBackend::connect(&address).unwrap();

        assert!(backend.add_user("ana", "pw").unwrap());
        assert!(!backend.authenticate("ana", "bad").unwrap());
        assert_eq!(backend.chat_members("team").unwrap(), vec!["ana", "ben"]);
        let delta = backend.message_delta("ana", "2000-01-01 00:00:00").unwrap();
        assert_eq!(delta["team"][0].contents, "hi");
        assert!(delta["quiet"].is_empty());
        backend.shutdown();

        let requests = handle.join().unwrap();
        assert_eq!(
            requests[0],
            r#"AddUserRequest{"username":"ana","password":"pw"}"#
        );
        assert_eq!(
            requests[1],
            r#"AuthRequest{"username":"ana","password":"bad"}"#
        );
        assert_eq!(requests[2], r#"GetChatMembersRequest{"chatname":"team"}"#);
        assert_eq!(
            requests[3],
            r#"LOADMESSAGEDELTA{"username":"ana","since":"2000-01-01 00:00:00"}"#
        );
        assert_eq!(requests[4], "SHUTDOWN{}");
    }

    #[test]
    fn create_chat_and_send_message_bodies() {
        let (address, handle) = stub(
            vec![r#"{"processed":true}"#, r#"{"processed":false}"#],
            false,
        );
        let mut backend = TcpBackend::connect(&address).unwrap();
        assert!(
            backend
                .create_chat("équipe", &["ana".to_string(), "ben".to_string()])
                .unwrap()
        );
        assert!(
            !backend
                .send_message("ana", "équipe", "hola ñ", "2026-05-04 10:30:00")
                .unwrap()
        );
        backend.shutdown();
        let requests = handle.join().unwrap();
        assert_eq!(
            requests[0],
            r#"CreateChatRequest{"chatname":"équipe","usernames":["ana","ben"]}"#
        );
        assert_eq!(
            requests[1],
            r#"SendMessageRequest{"username":"ana","chatname":"équipe","message":"hola ñ","date":"2026-05-04 10:30:00"}"#
        );
    }

    #[test]
    fn a_broken_connection_is_retried_once_on_a_new_one() {
        let (address, handle) = stub(vec![r#"{"authorized":true}"#], true);
        let mut backend = TcpBackend::connect(&address).unwrap();
        assert!(backend.authenticate("ana", "pw").unwrap());
        backend.shutdown();
        let requests = handle.join().unwrap();
        assert_eq!(
            requests
                .iter()
                .filter(|r| r.starts_with("AuthRequest"))
                .count(),
            2
        );
    }

    #[test]
    fn a_reply_that_is_not_json_is_a_protocol_error() {
        let (address, handle) = stub(vec![r#"{"error":"Internal error"}"#], false);
        let mut backend = TcpBackend::connect(&address).unwrap();
        let error = backend.add_user("ana", "pw").unwrap_err();
        assert!(matches!(error, BackendError::Protocol(_)), "{error}");
        assert!(error.to_string().contains("Internal error"));
        backend.shutdown();
        handle.join().unwrap();
    }

    #[test]
    fn connecting_to_nothing_fails() {
        let free_port = TcpListener::bind("127.0.0.1:0")
            .unwrap()
            .local_addr()
            .unwrap()
            .port();
        assert!(TcpBackend::connect(&format!("127.0.0.1:{free_port}")).is_err());
    }
}
