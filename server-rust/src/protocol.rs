//! Wire types of both protocols and the framing helpers.
//!
//! * **Client ↔ server**: JSON objects with an `action` field, each followed by the
//!   end-of-transmission byte ([`EOT`]).
//! * **Server ↔ backend**: `RequestName{json}` followed by [`EOT`]; the backend answers with a
//!   JSON object followed by [`EOT`].
//!
//! See `docs/PROTOCOL.md` for the description with examples.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

/// Byte that ends every message in both directions.
pub const EOT: u8 = 0x04;

// ── Client → server ──────────────────────────────────────────────────────────────────────────

/// A request sent by a client. Missing text fields default to the empty string and unknown
/// fields (such as the `username` older clients send with every request) are ignored: the
/// identity of the sender is always the one of the session.
#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(tag = "action", rename_all = "snake_case")]
pub enum ClientRequest {
    /// Register a user (and log it in).
    CreateUser {
        #[serde(default)]
        username: String,
        #[serde(default)]
        password: String,
    },
    /// Log in.
    Login {
        #[serde(default)]
        username: String,
        #[serde(default)]
        password: String,
    },
    /// Messages of every chat of the logged-in user sent after `since` (`yyyy-MM-dd HH:mm:ss`).
    LoadMessageDelta {
        #[serde(default)]
        since: String,
    },
    /// Create a chat; the creator is added automatically.
    CreateChat {
        #[serde(default)]
        chat_name: String,
        #[serde(default)]
        participants: Vec<String>,
    },
    /// Send a message to a chat.
    SendMsg {
        #[serde(default)]
        chat: String,
        #[serde(default)]
        msg: String,
    },
    /// Close the session and the connection.
    Logout,
}

// ── Server → client ──────────────────────────────────────────────────────────────────────────

/// Reply to an operation: `processed` is `1` on success and `0` otherwise.
#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusReply {
    /// `1` if the operation succeeded, `0` if not.
    pub processed: u8,
    /// Human-readable detail.
    pub msg: String,
}

impl StatusReply {
    /// A reply with `processed = 1`.
    pub fn ok(msg: &str) -> Self {
        StatusReply {
            processed: 1,
            msg: msg.to_owned(),
        }
    }

    /// A reply with `processed = 0`.
    pub fn error(msg: &str) -> Self {
        StatusReply {
            processed: 0,
            msg: msg.to_owned(),
        }
    }
}

/// A chat message, as stored by the backend and pushed to clients.
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
pub struct ChatMessage {
    /// Username of the author.
    pub author: String,
    /// Text of the message (images travel inside the text, see the Python client).
    pub contents: String,
    /// Send time, `yyyy-MM-dd HH:mm:ss`.
    pub sent: String,
    /// Name of the chat.
    pub chatname: String,
}

/// Reply to [`ClientRequest::LoadMessageDelta`].
#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConversationsReply {
    /// `1`.
    pub code: u8,
    /// Always empty.
    pub msg: String,
    /// New messages by chat name; chats without new messages map to an empty list.
    pub conversations: BTreeMap<String, Vec<ChatMessage>>,
}

/// Push sent to the members of a chat that was just created.
#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NewChatNotice {
    /// Name of the new chat.
    pub chatname: String,
}

/// Serializes `value` as JSON followed by [`EOT`].
pub fn frame<T: Serialize>(value: &T) -> Vec<u8> {
    let mut bytes = serde_json::to_vec(value).expect("protocol types always serialize");
    bytes.push(EOT);
    bytes
}

/// Splits complete messages (terminated by [`EOT`]) off the front of `buffer`.
///
/// What remains in `buffer` is the beginning of an incomplete message.
pub fn take_messages(buffer: &mut Vec<u8>) -> Vec<Vec<u8>> {
    let mut messages = Vec::new();
    while let Some(end) = buffer.iter().position(|byte| *byte == EOT) {
        let mut message: Vec<u8> = buffer.drain(..=end).collect();
        message.pop(); // the EOT
        messages.push(message);
    }
    messages
}

// ── Server → backend ─────────────────────────────────────────────────────────────────────────

/// Body of `AuthRequest` and `AddUserRequest`.
#[derive(Debug, Serialize)]
pub struct Credentials<'a> {
    /// Username.
    pub username: &'a str,
    /// Plain-text password (the backend hashes it).
    pub password: &'a str,
}

/// Body of `CreateChatRequest`.
#[derive(Debug, Serialize)]
pub struct CreateChatBody<'a> {
    /// Name of the chat.
    pub chatname: &'a str,
    /// Usernames of the members.
    pub usernames: &'a [String],
}

/// Body of `SendMessageRequest`.
#[derive(Debug, Serialize)]
pub struct SendMessageBody<'a> {
    /// Author.
    pub username: &'a str,
    /// Chat name.
    pub chatname: &'a str,
    /// Text.
    pub message: &'a str,
    /// Send time, `yyyy-MM-dd HH:mm:ss`.
    pub date: &'a str,
}

/// Body of `GetChatMembersRequest`.
#[derive(Debug, Serialize)]
pub struct ChatNameBody<'a> {
    /// Chat name.
    pub chatname: &'a str,
}

/// Body of `LOADMESSAGEDELTA`.
#[derive(Debug, Serialize)]
pub struct DeltaBody<'a> {
    /// Whose chats to read.
    pub username: &'a str,
    /// Only messages after this time (`yyyy-MM-dd HH:mm:ss`).
    pub since: &'a str,
}

/// Backend reply to `AuthRequest`.
#[derive(Debug, Deserialize)]
pub struct AuthorizedReply {
    /// Whether the credentials are valid.
    pub authorized: bool,
}

/// Backend reply to requests that change data.
#[derive(Debug, Deserialize)]
pub struct ProcessedReply {
    /// Whether the operation was carried out.
    pub processed: bool,
}

/// Backend reply to `GetChatMembersRequest`.
#[derive(Debug, Deserialize)]
pub struct MembersReply {
    /// Usernames of the members.
    pub members: Vec<String>,
}

/// Backend reply to `LOADMESSAGEDELTA`.
#[derive(Debug, Deserialize)]
pub struct DeltaReply {
    /// New messages by chat name.
    pub conversations: BTreeMap<String, Vec<ChatMessage>>,
}

/// Encodes a backend request: `header`, the JSON body and [`EOT`].
pub fn encode_backend_request<T: Serialize>(header: &str, body: &T) -> Vec<u8> {
    let mut bytes = header.as_bytes().to_vec();
    bytes.extend(serde_json::to_vec(body).expect("protocol types always serialize"));
    bytes.push(EOT);
    bytes
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(json: &str) -> Result<ClientRequest, serde_json::Error> {
        serde_json::from_str(json)
    }

    #[test]
    fn every_client_action_is_parsed() {
        assert_eq!(
            parse(r#"{"action":"create_user","username":"ana","password":"pw"}"#).unwrap(),
            ClientRequest::CreateUser {
                username: "ana".into(),
                password: "pw".into()
            }
        );
        assert_eq!(
            parse(r#"{"action":"login","username":"ana","password":"pw"}"#).unwrap(),
            ClientRequest::Login {
                username: "ana".into(),
                password: "pw".into()
            }
        );
        assert_eq!(
            parse(
                r#"{"action":"load_message_delta","username":"ana","since":"2026-01-01 00:00:00"}"#
            )
            .unwrap(),
            ClientRequest::LoadMessageDelta {
                since: "2026-01-01 00:00:00".into()
            }
        );
        assert_eq!(
            parse(r#"{"action":"create_chat","chat_name":"team","participants":["ana","ben"]}"#)
                .unwrap(),
            ClientRequest::CreateChat {
                chat_name: "team".into(),
                participants: vec!["ana".into(), "ben".into()]
            }
        );
        assert_eq!(
            parse(r#"{"action":"send_msg","username":"someone else","chat":"team","msg":"hi"}"#)
                .unwrap(),
            ClientRequest::SendMsg {
                chat: "team".into(),
                msg: "hi".into()
            }
        );
        assert_eq!(
            parse(r#"{"action":"logout"}"#).unwrap(),
            ClientRequest::Logout
        );
    }

    #[test]
    fn missing_fields_default_to_empty() {
        assert_eq!(
            parse(r#"{"action":"login"}"#).unwrap(),
            ClientRequest::Login {
                username: String::new(),
                password: String::new()
            }
        );
    }

    #[test]
    fn pretty_printed_json_with_unicode_is_accepted() {
        let json = "{\n    \"action\": \"send_msg\",\n    \"chat\": \"équipe\",\n    \"msg\": \"hola ñ 😀\"\n}";
        assert_eq!(
            parse(json).unwrap(),
            ClientRequest::SendMsg {
                chat: "équipe".into(),
                msg: "hola ñ 😀".into()
            }
        );
    }

    #[test]
    fn unknown_actions_and_garbage_are_errors() {
        assert!(parse(r#"{"action":"explode"}"#).is_err());
        assert!(parse(r#"{"no":"action"}"#).is_err());
        assert!(parse("not json").is_err());
    }

    #[test]
    fn frames_end_with_eot_and_escape_special_characters() {
        let bytes = frame(&NewChatNotice {
            chatname: "a\"b\\c\n".into(),
        });
        assert_eq!(*bytes.last().unwrap(), EOT);
        let back: NewChatNotice = serde_json::from_slice(&bytes[..bytes.len() - 1]).unwrap();
        assert_eq!(back.chatname, "a\"b\\c\n");
    }

    #[test]
    fn take_messages_splits_complete_messages_and_keeps_the_rest() {
        let mut buffer = b"one\x04two\x04thr".to_vec();
        assert_eq!(
            take_messages(&mut buffer),
            vec![b"one".to_vec(), b"two".to_vec()]
        );
        assert_eq!(buffer, b"thr");
        buffer.extend_from_slice(b"ee\x04");
        assert_eq!(take_messages(&mut buffer), vec![b"three".to_vec()]);
        assert!(buffer.is_empty());
        assert!(take_messages(&mut buffer).is_empty());
    }

    #[test]
    fn backend_requests_are_header_json_eot() {
        let bytes = encode_backend_request(
            "AuthRequest",
            &Credentials {
                username: "ana",
                password: "p\"w",
            },
        );
        assert_eq!(
            bytes,
            b"AuthRequest{\"username\":\"ana\",\"password\":\"p\\\"w\"}\x04".to_vec()
        );
    }
}
