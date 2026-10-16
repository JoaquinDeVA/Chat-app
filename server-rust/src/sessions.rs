//! The behaviour of the server: one session per client connection, and what every request does.
//!
//! [`Sessions`] knows nothing about sockets: it is generic over the [`Backend`] it forwards to
//! and over the [`Write`] it answers through, so the whole protocol is tested with in-memory
//! fakes (see the tests below).

use std::collections::HashMap;
use std::io::Write;

use crate::backend::{Backend, BackendError};
use crate::protocol::{
    ChatMessage, ClientRequest, ConversationsReply, HelloReply, NewChatNotice, StatusReply, frame,
    take_messages,
};
use crate::versions::{self, Protocol, SUPPORTED_VERSIONS, is_valid_name};

/// Longest username (the backend column holds 50 characters).
const MAX_USERNAME: usize = 50;
/// Longest chat name (the backend column holds 100 characters).
const MAX_CHAT_NAME: usize = 100;
const INVALID_NAME: &str = "Names may only contain letters, digits, '_', '-' and '.'";

/// Identifier of a connection, chosen by the caller of [`Sessions::connect`].
pub type ClientId = u64;

/// Largest message a client may send (images travel inside messages).
pub const MAX_MESSAGE_BYTES: usize = 32 * 1024 * 1024;

const TIMESTAMP_FORMAT: &str = "%Y-%m-%d %H:%M:%S";

struct Session<W> {
    writer: W,
    /// `None` until the client says hello; selects what differs between protocol versions.
    protocol: Option<Box<dyn Protocol>>,
    /// `None` until the client logs in.
    username: Option<String>,
    /// Bytes received that do not form a complete message yet.
    buffer: Vec<u8>,
}

/// All the connected clients and the backend they talk to.
pub struct Sessions<B, W> {
    clients: HashMap<ClientId, Session<W>>,
    backend: B,
    clock: Box<dyn Fn() -> String + Send>,
}

impl<B: Backend, W: Write> Sessions<B, W> {
    /// Creates the server state; messages are stamped with the local time.
    pub fn new(backend: B) -> Self {
        Self::with_clock(backend, || {
            chrono::Local::now().format(TIMESTAMP_FORMAT).to_string()
        })
    }

    /// Like [`Sessions::new`] with a custom source of timestamps (for tests).
    pub fn with_clock(backend: B, clock: impl Fn() -> String + Send + 'static) -> Self {
        Sessions {
            clients: HashMap::new(),
            backend,
            clock: Box::new(clock),
        }
    }

    /// Registers a new connection, answered through `writer`.
    pub fn connect(&mut self, id: ClientId, writer: W) {
        self.clients.insert(
            id,
            Session {
                writer,
                protocol: None,
                username: None,
                buffer: Vec::new(),
            },
        );
    }

    /// Forgets a connection (dropping its writer closes the socket).
    pub fn disconnect(&mut self, id: ClientId) {
        if let Some(session) = self.clients.remove(&id) {
            log::info!(
                "client {id} disconnected ({})",
                session.username.as_deref().unwrap_or("not logged in")
            );
        }
    }

    /// Number of connected clients.
    pub fn len(&self) -> usize {
        self.clients.len()
    }

    /// True if nobody is connected.
    pub fn is_empty(&self) -> bool {
        self.clients.is_empty()
    }

    /// True if `id` is a connected client.
    pub fn contains(&self, id: ClientId) -> bool {
        self.clients.contains_key(&id)
    }

    /// Protocol version a connection announced with `hello`.
    pub fn protocol_version(&self, id: ClientId) -> Option<u32> {
        self.clients
            .get(&id)?
            .protocol
            .as_ref()
            .map(|p| p.version())
    }

    /// Username a connection is logged in as.
    pub fn username(&self, id: ClientId) -> Option<&str> {
        self.clients.get(&id)?.username.as_deref()
    }

    /// Tells the backend to stop (called when the server shuts down).
    pub fn shutdown_backend(&mut self) {
        self.backend.shutdown();
    }

    /// Processes bytes received from a client.
    ///
    /// Complete messages are executed in order; an incomplete tail is kept for the next call.
    /// Returns `false` if the connection must be closed (logout, oversized message, write error).
    pub fn receive(&mut self, id: ClientId, data: &[u8]) -> bool {
        let messages = match self.clients.get_mut(&id) {
            None => return false,
            Some(session) => {
                session.buffer.extend_from_slice(data);
                let messages = take_messages(&mut session.buffer);
                if session.buffer.len() > MAX_MESSAGE_BYTES {
                    log::warn!("client {id} sent a message over {MAX_MESSAGE_BYTES} bytes");
                    return false;
                }
                messages
            }
        };

        for raw in messages {
            if !self.handle_raw(id, &raw) {
                return false;
            }
        }
        true
    }

    fn handle_raw(&mut self, id: ClientId, raw: &[u8]) -> bool {
        let request = match std::str::from_utf8(raw)
            .map_err(|error| error.to_string())
            .and_then(|text| {
                serde_json::from_str::<ClientRequest>(text).map_err(|error| error.to_string())
            }) {
            Ok(request) => request,
            Err(error) => {
                // The body is deliberately not logged: it may contain a password.
                log::warn!("invalid request from client {id}: {error}");
                return self.reply(id, &StatusReply::error("Invalid request"));
            }
        };
        self.handle(id, request)
    }

    fn handle(&mut self, id: ClientId, request: ClientRequest) -> bool {
        let Some(session) = self.clients.get(&id) else {
            return false;
        };
        if let ClientRequest::Hello { version } = request {
            return self.hello(id, version);
        }
        if session.protocol.is_none() {
            return self.reply(
                id,
                &StatusReply::error("Say hello with your protocol version first"),
            );
        }
        let username = session.username.clone();

        match (request, username) {
            (ClientRequest::Hello { .. }, _) => true, // handled above
            (ClientRequest::CreateUser { username, password }, None) => {
                self.create_user(id, &username, &password)
            }
            (ClientRequest::Login { username, password }, None) => {
                self.login(id, &username, &password)
            }
            (ClientRequest::CreateUser { .. } | ClientRequest::Login { .. }, Some(_)) => {
                self.reply(id, &StatusReply::error("Already logged in"))
            }
            (_, None) => self.reply(id, &StatusReply::error("You are not logged in")),
            (ClientRequest::LoadMessageDelta { since }, Some(user)) => {
                self.load_delta(id, &user, &since)
            }
            (
                ClientRequest::CreateChat {
                    chat_name,
                    participants,
                },
                Some(user),
            ) => self.create_chat(id, &user, &chat_name, participants),
            (ClientRequest::SendMsg { chat, msg }, Some(user)) => {
                self.send_message(id, &user, &chat, &msg)
            }
            (ClientRequest::Logout, Some(user)) => {
                log::info!("{user} logged out");
                false
            }
        }
    }

    // ── handlers ─────────────────────────────────────────────────────────────────────────────

    /// Selects the protocol version of the connection. An unsupported version closes it.
    fn hello(&mut self, id: ClientId, version: u32) -> bool {
        if self.protocol_version(id).is_some() {
            return self.reply(id, &StatusReply::error("Already said hello"));
        }
        match versions::for_version(version) {
            Some(protocol) => {
                if let Some(session) = self.clients.get_mut(&id) {
                    session.protocol = Some(protocol);
                }
                log::info!("client {id} speaks protocol v{version}");
                self.reply(
                    id,
                    &HelloReply {
                        processed: 1,
                        msg: "ok".to_owned(),
                        version: Some(version),
                        supported: None,
                    },
                )
            }
            None => {
                self.reply(
                    id,
                    &HelloReply {
                        processed: 0,
                        msg: "Unsupported protocol version".to_owned(),
                        version: None,
                        supported: Some(SUPPORTED_VERSIONS.to_vec()),
                    },
                );
                false
            }
        }
    }

    /// Registers the user and logs it in. Version 1 clients get one reply that already means
    /// "registered and logged in"; later versions get two: the registration result, then the
    /// result of the automatic login.
    fn create_user(&mut self, id: ClientId, username: &str, password: &str) -> bool {
        if username.trim().is_empty() || password.is_empty() {
            return self.reply(
                id,
                &StatusReply::error("Username and password are required"),
            );
        }
        if !is_valid_name(username, MAX_USERNAME) {
            return self.reply(id, &StatusReply::error(INVALID_NAME));
        }
        match self.backend.add_user(username, password) {
            Ok(true) => {
                let two_replies = self
                    .clients
                    .get(&id)
                    .and_then(|session| session.protocol.as_ref())
                    .is_some_and(|protocol| protocol.registration_sends_login_reply());
                if two_replies {
                    if !self.reply(id, &StatusReply::ok("User added")) {
                        return false;
                    }
                    self.login(id, username, password)
                } else {
                    self.open_session(id, username, password, "User added and logged in")
                }
            }
            Ok(false) => self.reply(id, &StatusReply::error("Could not add user")),
            Err(error) => self.backend_failed(id, &error),
        }
    }

    fn login(&mut self, id: ClientId, username: &str, password: &str) -> bool {
        self.open_session(id, username, password, "ok")
    }

    /// Checks the password and, if it is right, logs the connection in.
    fn open_session(
        &mut self,
        id: ClientId,
        username: &str,
        password: &str,
        success: &str,
    ) -> bool {
        match self.backend.authenticate(username, password) {
            Ok(true) => {
                if let Some(session) = self.clients.get_mut(&id) {
                    session.username = Some(username.to_owned());
                }
                log::info!("{username} logged in (client {id})");
                self.reply(id, &StatusReply::ok(success))
            }
            Ok(false) => self.reply(id, &StatusReply::error("Authentication failed")),
            Err(error) => self.backend_failed(id, &error),
        }
    }

    fn load_delta(&mut self, id: ClientId, user: &str, since: &str) -> bool {
        match self.backend.message_delta(user, since) {
            Ok(mut conversations) => {
                if let Some(protocol) = self.clients.get(&id).and_then(|s| s.protocol.as_ref()) {
                    for messages in conversations.values_mut() {
                        for message in messages.iter_mut() {
                            *message = protocol.present(message);
                        }
                    }
                }
                self.reply(
                    id,
                    &ConversationsReply {
                        code: 1,
                        msg: String::new(),
                        conversations,
                    },
                )
            }
            Err(error) => self.backend_failed(id, &error),
        }
    }

    fn create_chat(
        &mut self,
        id: ClientId,
        creator: &str,
        chat: &str,
        participants: Vec<String>,
    ) -> bool {
        let mut members: Vec<String> = vec![creator.to_owned()];
        for participant in participants {
            if !participant.trim().is_empty() && !members.contains(&participant) {
                members.push(participant);
            }
        }
        if !is_valid_name(chat, MAX_CHAT_NAME)
            || members
                .iter()
                .any(|name| !is_valid_name(name, MAX_USERNAME))
        {
            return self.reply(id, &StatusReply::error(INVALID_NAME));
        }

        match self.backend.create_chat(chat, &members) {
            Ok(true) => {
                if !self.reply(id, &StatusReply::ok("Chat created")) {
                    return false;
                }
                let notice = frame(&NewChatNotice {
                    chatname: chat.to_owned(),
                });
                self.push_to_users(&members, Some(id), &notice);
                true
            }
            Ok(false) => self.reply(id, &StatusReply::error("Could not create chat")),
            Err(error) => self.backend_failed(id, &error),
        }
    }

    fn send_message(&mut self, id: ClientId, user: &str, chat: &str, text: &str) -> bool {
        let checked = match self.clients.get(&id).and_then(|s| s.protocol.as_ref()) {
            Some(protocol) => protocol.check_message(text),
            None => return false,
        };
        let text = match checked {
            Ok(text) => text,
            Err(reason) => return self.reply(id, &StatusReply::error(reason)),
        };
        let sent = (self.clock)();
        match self.backend.send_message(user, chat, &text, &sent) {
            Ok(true) => {
                let message = ChatMessage {
                    author: user.to_owned(),
                    contents: text.to_owned(),
                    sent: sent.clone(),
                    chatname: chat.to_owned(),
                };
                match self.backend.chat_members(chat) {
                    Ok(members) => self.push_message(&members, Some(id), &message),
                    Err(error) => {
                        log::warn!("message stored but members of '{chat}' unknown: {error}")
                    }
                }
                self.reply(id, &StatusReply::ok("Message sent").with_sent(&sent))
            }
            Ok(false) => self.reply(id, &StatusReply::error("Could not send message")),
            Err(error) => self.backend_failed(id, &error),
        }
    }

    // ── helpers ──────────────────────────────────────────────────────────────────────────────

    fn backend_failed(&mut self, id: ClientId, error: &BackendError) -> bool {
        log::error!("{error}");
        self.reply(id, &StatusReply::error("Server error"))
    }

    /// Writes a reply to one client; false if the client is gone.
    fn reply<T: serde::Serialize>(&mut self, id: ClientId, value: &T) -> bool {
        self.write_to(id, &frame(value))
    }

    fn write_to(&mut self, id: ClientId, bytes: &[u8]) -> bool {
        match self.clients.get_mut(&id) {
            Some(session) => session
                .writer
                .write_all(bytes)
                .and_then(|()| session.writer.flush())
                .is_ok(),
            None => false,
        }
    }

    /// Pushes a message to every connection logged in as one of `users`, except `skip`, each
    /// receiving it as its protocol version presents it.
    fn push_message(&mut self, users: &[String], skip: Option<ClientId>, message: &ChatMessage) {
        let mut deliveries: Vec<(ClientId, Vec<u8>)> = Vec::new();
        for (id, session) in &self.clients {
            let member = session
                .username
                .as_ref()
                .is_some_and(|name| users.contains(name));
            if Some(*id) != skip && member {
                let shown = match session.protocol.as_ref() {
                    Some(protocol) => protocol.present(message),
                    None => message.clone(),
                };
                deliveries.push((*id, frame(&shown)));
            }
        }
        for (id, bytes) in deliveries {
            if !self.write_to(id, &bytes) {
                self.disconnect(id);
            }
        }
    }

    /// Writes `bytes` to every connection logged in as one of `users`, except `skip`.
    /// Connections that cannot be written to are dropped.
    fn push_to_users(&mut self, users: &[String], skip: Option<ClientId>, bytes: &[u8]) {
        let targets: Vec<ClientId> = self
            .clients
            .iter()
            .filter(|(id, session)| {
                Some(**id) != skip
                    && session
                        .username
                        .as_ref()
                        .is_some_and(|name| users.contains(name))
            })
            .map(|(id, _)| *id)
            .collect();
        for target in targets {
            if !self.write_to(target, bytes) {
                self.disconnect(target);
            }
        }
    }
}

/// An in-memory backend used by the tests of this crate.
#[cfg(test)]
pub mod fake {
    use super::*;
    use crate::backend::BackendResult;
    use std::cell::RefCell;
    use std::collections::BTreeMap;
    use std::rc::Rc;

    /// State shared between the fake and the test that inspects it.
    #[derive(Default)]
    pub struct World {
        pub users: BTreeMap<String, String>,
        pub chats: BTreeMap<String, Vec<String>>,
        pub messages: Vec<ChatMessage>,
        pub fail: bool,
        pub shut_down: bool,
        pub calls: Vec<String>,
    }

    #[derive(Clone, Default)]
    pub struct FakeBackend(pub Rc<RefCell<World>>);

    impl FakeBackend {
        fn check(&self) -> BackendResult<()> {
            if self.0.borrow().fail {
                Err(BackendError::Protocol("fake failure".into()))
            } else {
                Ok(())
            }
        }
    }

    impl Backend for FakeBackend {
        fn add_user(&mut self, username: &str, password: &str) -> BackendResult<bool> {
            self.check()?;
            let mut world = self.0.borrow_mut();
            world.calls.push(format!("add_user {username}"));
            if world.users.contains_key(username) {
                return Ok(false);
            }
            world.users.insert(username.to_owned(), password.to_owned());
            Ok(true)
        }

        fn authenticate(&mut self, username: &str, password: &str) -> BackendResult<bool> {
            self.check()?;
            Ok(self
                .0
                .borrow()
                .users
                .get(username)
                .is_some_and(|stored| stored == password))
        }

        fn create_chat(&mut self, chat: &str, usernames: &[String]) -> BackendResult<bool> {
            self.check()?;
            let mut world = self.0.borrow_mut();
            world
                .calls
                .push(format!("create_chat {chat} {usernames:?}"));
            if world.chats.contains_key(chat)
                || usernames.iter().any(|u| !world.users.contains_key(u))
            {
                return Ok(false);
            }
            world.chats.insert(chat.to_owned(), usernames.to_vec());
            Ok(true)
        }

        fn send_message(
            &mut self,
            username: &str,
            chat: &str,
            text: &str,
            sent: &str,
        ) -> BackendResult<bool> {
            self.check()?;
            let mut world = self.0.borrow_mut();
            world.calls.push(format!("send_message {username} {chat}"));
            if !world
                .chats
                .get(chat)
                .is_some_and(|members| members.iter().any(|m| m == username))
            {
                return Ok(false);
            }
            world.messages.push(ChatMessage {
                author: username.to_owned(),
                contents: text.to_owned(),
                sent: sent.to_owned(),
                chatname: chat.to_owned(),
            });
            Ok(true)
        }

        fn chat_members(&mut self, chat: &str) -> BackendResult<Vec<String>> {
            self.check()?;
            Ok(self.0.borrow().chats.get(chat).cloned().unwrap_or_default())
        }

        fn message_delta(
            &mut self,
            username: &str,
            since: &str,
        ) -> BackendResult<BTreeMap<String, Vec<ChatMessage>>> {
            self.check()?;
            let world = self.0.borrow();
            let mut result = BTreeMap::new();
            for (chat, members) in &world.chats {
                if members.iter().any(|m| m == username) {
                    let messages = world
                        .messages
                        .iter()
                        .filter(|m| &m.chatname == chat && m.sent.as_str() > since)
                        .cloned()
                        .collect();
                    result.insert(chat.clone(), messages);
                }
            }
            Ok(result)
        }

        fn shutdown(&mut self) {
            self.0.borrow_mut().shut_down = true;
        }
    }

    /// A writer whose content the test can read, and which can be made to fail.
    #[derive(Clone, Default)]
    pub struct Wire(pub Rc<RefCell<(Vec<u8>, bool)>>);

    impl Wire {
        /// Every complete message written so far, parsed as JSON.
        pub fn messages(&self) -> Vec<serde_json::Value> {
            let mut buffer = self.0.borrow().0.clone();
            take_messages(&mut buffer)
                .iter()
                .map(|m| serde_json::from_slice(m).expect("the server only writes JSON"))
                .collect()
        }

        pub fn clear(&self) {
            self.0.borrow_mut().0.clear();
        }

        pub fn break_it(&self) {
            self.0.borrow_mut().1 = true;
        }
    }

    impl Write for Wire {
        fn write(&mut self, data: &[u8]) -> std::io::Result<usize> {
            let mut inner = self.0.borrow_mut();
            if inner.1 {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::BrokenPipe,
                    "closed",
                ));
            }
            inner.0.extend_from_slice(data);
            Ok(data.len())
        }

        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::fake::*;
    use super::*;
    use serde_json::{Value, json};

    type Server = Sessions<FakeBackend, Wire>;

    struct Rig {
        server: Server,
        world: FakeBackend,
    }

    impl Rig {
        fn new() -> Self {
            let world = FakeBackend::default();
            let server = Sessions::with_clock(world.clone(), || "2026-05-04 10:30:00".to_string());
            Rig { server, world }
        }

        /// Connects a client without saying hello.
        fn raw_client(&mut self, id: ClientId) -> Wire {
            let wire = Wire::default();
            self.server.connect(id, wire.clone());
            wire
        }

        /// Connects a client that speaks protocol `version` and returns its wire.
        fn client_v(&mut self, id: ClientId, version: u32) -> Wire {
            let wire = self.raw_client(id);
            self.send(id, json!({"action":"hello","version":version}));
            assert_eq!(status(&wire.messages()[0]).0, 1, "hello accepted");
            wire.clear();
            wire
        }

        /// A version 2 (full) client.
        fn client(&mut self, id: ClientId) -> Wire {
            self.client_v(id, 2)
        }

        /// A version 1 (simple) client.
        fn client_v1(&mut self, id: ClientId) -> Wire {
            self.client_v(id, 1)
        }

        fn send(&mut self, id: ClientId, request: Value) -> bool {
            let mut bytes = request.to_string().into_bytes();
            bytes.push(crate::protocol::EOT);
            self.server.receive(id, &bytes)
        }

        /// Registers and logs in `name` on a new version 2 connection.
        fn user(&mut self, id: ClientId, name: &str) -> Wire {
            let wire = self.client(id);
            self.send(
                id,
                json!({"action":"create_user","username":name,"password":"pw"}),
            );
            wire.clear();
            wire
        }

        /// Registers and logs in `name` on a new version 1 connection.
        fn user_v1(&mut self, id: ClientId, name: &str) -> Wire {
            let wire = self.client_v1(id);
            self.send(
                id,
                json!({"action":"create_user","username":name,"password":"pw"}),
            );
            wire.clear();
            wire
        }
    }

    fn status(value: &Value) -> (i64, &str) {
        (
            value["processed"].as_i64().unwrap(),
            value["msg"].as_str().unwrap(),
        )
    }

    #[test]
    fn registering_answers_twice_and_logs_the_user_in() {
        let mut rig = Rig::new();
        let wire = rig.client(1);
        assert!(rig.send(
            1,
            json!({"action":"create_user","username":"ana","password":"pw"})
        ));

        let replies = wire.messages();
        assert_eq!(
            replies.len(),
            2,
            "registration confirmation, then the automatic login"
        );
        assert_eq!(status(&replies[0]), (1, "User added"));
        assert_eq!(status(&replies[1]), (1, "ok"));
        assert_eq!(rig.server.username(1), Some("ana"));
    }

    #[test]
    fn a_rejected_registration_answers_once_and_does_not_log_in() {
        let mut rig = Rig::new();
        rig.user(1, "ana");
        let wire = rig.client(2);
        rig.send(
            2,
            json!({"action":"create_user","username":"ana","password":"other"}),
        );

        let replies = wire.messages();
        assert_eq!(replies.len(), 1);
        assert_eq!(status(&replies[0]), (0, "Could not add user"));
        assert_eq!(rig.server.username(2), None);
    }

    #[test]
    fn registration_requires_a_username_and_a_password() {
        let mut rig = Rig::new();
        let wire = rig.client(1);
        rig.send(
            1,
            json!({"action":"create_user","username":"  ","password":"pw"}),
        );
        rig.send(
            1,
            json!({"action":"create_user","username":"ana","password":""}),
        );
        assert!(wire.messages().iter().all(|r| status(r).0 == 0));
        assert!(rig.world.0.borrow().users.is_empty());
    }

    #[test]
    fn login_checks_the_password() {
        let mut rig = Rig::new();
        rig.user(1, "ana");
        let wire = rig.client(2);
        rig.send(
            2,
            json!({"action":"login","username":"ana","password":"wrong"}),
        );
        assert_eq!(status(&wire.messages()[0]), (0, "Authentication failed"));
        assert_eq!(rig.server.username(2), None);

        wire.clear();
        rig.send(
            2,
            json!({"action":"login","username":"ana","password":"pw"}),
        );
        assert_eq!(status(&wire.messages()[0]), (1, "ok"));
        assert_eq!(rig.server.username(2), Some("ana"));
    }

    #[test]
    fn logging_in_twice_is_refused() {
        let mut rig = Rig::new();
        let wire = rig.user(1, "ana");
        rig.send(
            1,
            json!({"action":"login","username":"ana","password":"pw"}),
        );
        rig.send(
            1,
            json!({"action":"create_user","username":"bob","password":"pw"}),
        );
        let replies = wire.messages();
        assert_eq!(status(&replies[0]), (0, "Already logged in"));
        assert_eq!(status(&replies[1]), (0, "Already logged in"));
    }

    #[test]
    fn operations_need_a_login() {
        let mut rig = Rig::new();
        let wire = rig.client(1);
        for request in [
            json!({"action":"load_message_delta","since":"2000-01-01 00:00:00"}),
            json!({"action":"create_chat","chat_name":"c","participants":["ana"]}),
            json!({"action":"send_msg","chat":"c","msg":"hi"}),
            json!({"action":"logout"}),
        ] {
            assert!(rig.send(1, request), "an anonymous client stays connected");
        }
        assert!(
            wire.messages()
                .iter()
                .all(|r| status(r) == (0, "You are not logged in"))
        );
        assert!(
            rig.world.0.borrow().calls.is_empty(),
            "nothing reached the backend"
        );
    }

    #[test]
    fn creating_a_chat_adds_the_creator_and_notifies_the_other_members_online() {
        let mut rig = Rig::new();
        let ana = rig.user(1, "ana");
        let ben = rig.user(2, "ben");
        let cat = rig.user(3, "cat");

        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":["ben", "ben", ""]}),
        );

        assert_eq!(status(&ana.messages()[0]), (1, "Chat created"));
        assert_eq!(ana.messages().len(), 1, "the creator gets no push");
        assert_eq!(ben.messages(), vec![json!({"chatname":"team"})]);
        assert!(cat.messages().is_empty(), "non-members are not notified");
        assert_eq!(rig.world.0.borrow().chats["team"], vec!["ana", "ben"]);
    }

    #[test]
    fn a_failed_chat_creation_notifies_nobody() {
        let mut rig = Rig::new();
        let ana = rig.user(1, "ana");
        let ben = rig.user(2, "ben");
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":["ghost"]}),
        );
        assert_eq!(status(&ana.messages()[0]), (0, "Could not create chat"));
        assert!(ben.messages().is_empty());
    }

    #[test]
    fn messages_are_pushed_to_the_other_online_members_only() {
        let mut rig = Rig::new();
        let ana = rig.user(1, "ana");
        let ben = rig.user(2, "ben");
        let cat = rig.user(3, "cat");
        let ben_phone = rig.client(4);
        rig.send(
            4,
            json!({"action":"login","username":"ben","password":"pw"}),
        );
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":["ben"]}),
        );
        for wire in [&ana, &ben, &cat, &ben_phone] {
            wire.clear();
        }

        rig.send(
            1,
            json!({"action":"send_msg","chat":"team","msg":"hola ñ 😀"}),
        );

        let pushed = json!({"author":"ana","contents":"hola ñ 😀","sent":"2026-05-04 10:30:00","chatname":"team"});
        assert_eq!(status(&ana.messages()[0]), (1, "Message sent"));
        assert_eq!(
            ana.messages()[0]["sent"],
            "2026-05-04 10:30:00",
            "the sender learns the timestamp"
        );
        assert_eq!(ben.messages(), vec![pushed.clone()]);
        assert_eq!(
            ben_phone.messages(),
            vec![pushed],
            "every connection of a member gets it"
        );
        assert!(cat.messages().is_empty());
    }

    #[test]
    fn the_author_is_the_session_never_a_name_sent_by_the_client() {
        let mut rig = Rig::new();
        let ana = rig.user(1, "ana");
        rig.user(2, "mallory");
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":[]}),
        );
        ana.clear();

        rig.send(
            2,
            json!({"action":"send_msg","username":"ana","chat":"team","msg":"forged"}),
        );

        assert!(
            rig.world.0.borrow().messages.is_empty(),
            "mallory is not a member"
        );
        rig.send(
            1,
            json!({"action":"send_msg","username":"mallory","chat":"team","msg":"mine"}),
        );
        assert_eq!(rig.world.0.borrow().messages[0].author, "ana");
    }

    #[test]
    fn a_rejected_message_is_reported_and_pushed_to_nobody() {
        let mut rig = Rig::new();
        rig.user(1, "ana");
        let ben = rig.user(2, "ben");
        let wire = rig.client(3);
        rig.send(
            3,
            json!({"action":"login","username":"ana","password":"pw"}),
        );
        wire.clear();
        rig.send(3, json!({"action":"send_msg","chat":"nope","msg":"hi"}));
        assert_eq!(status(&wire.messages()[0]), (0, "Could not send message"));
        assert!(ben.messages().is_empty());
    }

    #[test]
    fn the_delta_lists_every_chat_of_the_user() {
        let mut rig = Rig::new();
        let ana = rig.user(1, "ana");
        rig.user(2, "ben");
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":["ben"]}),
        );
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"solo","participants":[]}),
        );
        rig.send(1, json!({"action":"send_msg","chat":"team","msg":"hi"}));
        ana.clear();

        rig.send(
            1,
            json!({"action":"load_message_delta","username":"ben","since":"2000-01-01 00:00:00"}),
        );

        let reply = &ana.messages()[0];
        assert_eq!(reply["code"], 1);
        assert_eq!(reply["conversations"]["team"][0]["contents"], "hi");
        assert_eq!(reply["conversations"]["solo"], json!([]));
        rig.send(
            1,
            json!({"action":"load_message_delta","since":"2030-01-01 00:00:00"}),
        );
        assert_eq!(ana.messages()[1]["conversations"]["team"], json!([]));
    }

    #[test]
    fn logout_closes_the_connection() {
        let mut rig = Rig::new();
        rig.user(1, "ana");
        assert!(!rig.send(1, json!({"action":"logout"})));
    }

    #[test]
    fn garbage_gets_an_error_reply_and_the_connection_survives() {
        let mut rig = Rig::new();
        let wire = rig.client(1);
        assert!(
            rig.server
                .receive(1, b"not json\x04{\"action\":\"explode\"}\x04\xff\xfe\x04")
        );
        let replies = wire.messages();
        assert_eq!(replies.len(), 3);
        assert!(replies.iter().all(|r| status(r) == (0, "Invalid request")));
    }

    #[test]
    fn messages_split_across_reads_or_glued_together_are_handled() {
        let mut rig = Rig::new();
        let wire = rig.client(1);
        let login = br#"{"action":"login","username":"ghost","password":"x"}"#;
        assert!(rig.server.receive(1, &login[..10]));
        assert!(
            wire.messages().is_empty(),
            "incomplete message: nothing happens yet"
        );
        let mut rest = login[10..].to_vec();
        rest.push(crate::protocol::EOT);
        rest.extend_from_slice(login);
        rest.push(crate::protocol::EOT);
        assert!(rig.server.receive(1, &rest));
        assert_eq!(wire.messages().len(), 2);
    }

    #[test]
    fn an_oversized_message_closes_the_connection() {
        let mut rig = Rig::new();
        rig.client(1);
        let chunk = vec![b'a'; 1024 * 1024];
        let mut open = true;
        for _ in 0..40 {
            open = rig.server.receive(1, &chunk);
            if !open {
                break;
            }
        }
        assert!(!open);
    }

    #[test]
    fn a_backend_failure_is_reported_instead_of_crashing() {
        let mut rig = Rig::new();
        let wire = rig.client(1);
        rig.world.0.borrow_mut().fail = true;
        assert!(rig.send(
            1,
            json!({"action":"login","username":"ana","password":"pw"})
        ));
        assert!(rig.send(
            1,
            json!({"action":"create_user","username":"ana","password":"pw"})
        ));
        assert!(
            wire.messages()
                .iter()
                .all(|r| status(r) == (0, "Server error"))
        );
    }

    #[test]
    fn a_dead_member_does_not_stop_the_push_to_the_others() {
        let mut rig = Rig::new();
        rig.user(1, "ana");
        let ben = rig.user(2, "ben");
        let cat = rig.user(3, "cat");
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":["ben","cat"]}),
        );
        ben.clear();
        cat.clear();
        ben.break_it();

        rig.send(1, json!({"action":"send_msg","chat":"team","msg":"hi"}));

        assert_eq!(cat.messages().len(), 1);
        assert_eq!(rig.server.len(), 2, "the broken connection was dropped");
    }

    #[test]
    fn unknown_clients_and_disconnected_clients_are_ignored() {
        let mut rig = Rig::new();
        assert!(!rig.send(99, json!({"action":"logout"})));
        rig.client(1);
        rig.server.disconnect(1);
        assert!(rig.server.is_empty());
        assert!(!rig.send(1, json!({"action":"login"})));
    }

    #[test]
    fn shutting_down_tells_the_backend() {
        let mut rig = Rig::new();
        rig.server.shutdown_backend();
        assert!(rig.world.0.borrow().shut_down);
    }

    // ── protocol versions ────────────────────────────────────────────────────────────────────

    #[test]
    fn nothing_works_before_hello() {
        let mut rig = Rig::new();
        let wire = rig.raw_client(1);
        for request in [
            json!({"action":"login","username":"ana","password":"pw"}),
            json!({"action":"create_user","username":"ana","password":"pw"}),
            json!({"action":"send_msg","chat":"c","msg":"hi"}),
        ] {
            assert!(rig.send(1, request), "the connection stays open");
        }
        assert!(
            wire.messages()
                .iter()
                .all(|r| status(r) == (0, "Say hello with your protocol version first"))
        );
        assert!(rig.world.0.borrow().calls.is_empty());
        assert_eq!(rig.server.protocol_version(1), None);
    }

    #[test]
    fn hello_selects_the_version_and_answers_with_it() {
        let mut rig = Rig::new();
        let wire = rig.raw_client(1);
        rig.send(1, json!({"action":"hello","version":1}));
        assert_eq!(
            wire.messages()[0],
            json!({"processed":1,"msg":"ok","version":1})
        );
        assert_eq!(rig.server.protocol_version(1), Some(1));
        let wire = rig.raw_client(2);
        rig.send(2, json!({"action":"hello","version":2}));
        assert_eq!(wire.messages()[0]["version"], 2);
        assert_eq!(rig.server.protocol_version(2), Some(2));
    }

    #[test]
    fn an_unsupported_version_is_refused_with_the_supported_ones_and_the_connection_closes() {
        let mut rig = Rig::new();
        for version in [0, 3, 99] {
            let wire = rig.raw_client(1);
            assert!(!rig.send(1, json!({"action":"hello","version":version})));
            let reply = &wire.messages()[0];
            assert_eq!(status(reply), (0, "Unsupported protocol version"));
            assert_eq!(reply["supported"], json!([1, 2]));
        }
        let wire = rig.raw_client(2);
        assert!(
            !rig.send(2, json!({"action":"hello"})),
            "a missing version is version 0"
        );
        assert_eq!(wire.messages()[0]["supported"], json!([1, 2]));
    }

    #[test]
    fn hello_cannot_be_repeated() {
        let mut rig = Rig::new();
        let wire = rig.client_v1(1);
        rig.send(1, json!({"action":"hello","version":2}));
        assert_eq!(status(&wire.messages()[0]), (0, "Already said hello"));
        assert_eq!(
            rig.server.protocol_version(1),
            Some(1),
            "the version does not change"
        );
    }

    #[test]
    fn version_1_registration_is_a_single_reply_that_already_logs_in() {
        let mut rig = Rig::new();
        let wire = rig.client_v1(1);
        rig.send(
            1,
            json!({"action":"create_user","username":"ana","password":"pw"}),
        );
        let replies = wire.messages();
        assert_eq!(replies.len(), 1);
        assert_eq!(status(&replies[0]), (1, "User added and logged in"));
        assert_eq!(rig.server.username(1), Some("ana"));
    }

    #[test]
    fn version_1_failed_registration_is_still_a_single_reply() {
        let mut rig = Rig::new();
        rig.user(1, "ana");
        let wire = rig.client_v1(2);
        rig.send(
            2,
            json!({"action":"create_user","username":"ana","password":"x"}),
        );
        assert_eq!(wire.messages().len(), 1);
        assert_eq!(rig.server.username(2), None);
    }

    #[test]
    fn names_must_be_plain_ascii_identifiers() {
        let mut rig = Rig::new();
        let wire = rig.client(1);
        for bad in ["équipe", "with space", "a/b", "", "x".repeat(51).as_str()] {
            rig.send(
                1,
                json!({"action":"create_user","username":bad,"password":"pw"}),
            );
        }
        assert!(wire.messages().iter().all(|r| status(r).0 == 0));
        assert!(rig.world.0.borrow().users.is_empty());

        rig.user(2, "ana");
        rig.user(3, "ben");
        let ana = rig.client(4);
        rig.send(
            4,
            json!({"action":"login","username":"ana","password":"pw"}),
        );
        ana.clear();
        for chat in ["équipe", "with space", ""] {
            rig.send(
                4,
                json!({"action":"create_chat","chat_name":chat,"participants":["ben"]}),
            );
        }
        rig.send(
            4,
            json!({"action":"create_chat","chat_name":"team","participants":["bén"]}),
        );
        assert!(
            ana.messages()
                .iter()
                .all(|r| status(r) == (0, INVALID_NAME)),
            "{:?}",
            ana.messages()
        );
        assert!(rig.world.0.borrow().chats.is_empty());
    }

    /// Two users in a chat: `ana` on version 2 and `bob` on version 1.
    fn mixed_chat() -> (Rig, Wire, Wire) {
        let mut rig = Rig::new();
        let ana = rig.user(1, "ana");
        let bob = rig.user_v1(2, "bob");
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":["bob"]}),
        );
        ana.clear();
        bob.clear();
        (rig, ana, bob)
    }

    #[test]
    fn version_1_refuses_text_it_cannot_handle_and_stores_nothing() {
        let (mut rig, ana, bob) = mixed_chat();
        for text in ["hola ñ", "smile 😀", "two\nlines", "[[img]]|.png|AAAA", ""] {
            rig.send(2, json!({"action":"send_msg","chat":"team","msg":text}));
        }
        rig.send(
            2,
            json!({"action":"send_msg","chat":"team","msg":"a".repeat(1001)}),
        );
        assert!(
            bob.messages().iter().all(|r| status(r).0 == 0),
            "{:?}",
            bob.messages()
        );
        assert_eq!(bob.messages().len(), 6);
        assert!(rig.world.0.borrow().messages.is_empty());
        assert!(ana.messages().is_empty(), "nothing was pushed");

        rig.send(
            2,
            json!({"action":"send_msg","chat":"team","msg":"plain text 123!"}),
        );
        assert_eq!(rig.world.0.borrow().messages.len(), 1);
    }

    #[test]
    fn version_2_text_reaches_a_version_1_client_in_a_degraded_form() {
        let (mut rig, _ana, bob) = mixed_chat();

        rig.send(
            1,
            json!({"action":"send_msg","chat":"team","msg":"hola ñ 😀"}),
        );
        rig.send(
            1,
            json!({"action":"send_msg","chat":"team","msg":"[[img]]|.png|AAAA"}),
        );

        assert_eq!(bob.messages()[0]["contents"], "hola ? ?");
        assert_eq!(bob.messages()[1]["contents"], "[image]");
        assert_eq!(
            rig.world.0.borrow().messages[0].contents,
            "hola ñ 😀",
            "storage keeps the original"
        );
    }

    #[test]
    fn the_same_message_is_presented_per_recipient_version() {
        let mut rig = Rig::new();
        let ana = rig.user(1, "ana");
        let bob_simple = rig.user_v1(2, "bob");
        let cat_full = rig.user(3, "cat");
        rig.send(
            1,
            json!({"action":"create_chat","chat_name":"team","participants":["bob","cat"]}),
        );
        for wire in [&ana, &bob_simple, &cat_full] {
            wire.clear();
        }

        rig.send(
            1,
            json!({"action":"send_msg","chat":"team","msg":"café ☕"}),
        );

        assert_eq!(bob_simple.messages()[0]["contents"], "caf? ?");
        assert_eq!(cat_full.messages()[0]["contents"], "café ☕");
    }

    #[test]
    fn the_history_is_presented_per_version_too() {
        let (mut rig, ana, bob) = mixed_chat();
        rig.send(1, json!({"action":"send_msg","chat":"team","msg":"ñandú"}));
        rig.send(
            1,
            json!({"action":"send_msg","chat":"team","msg":"[[img]]|.png|AAAA"}),
        );
        ana.clear();
        bob.clear();

        rig.send(
            1,
            json!({"action":"load_message_delta","since":"2000-01-01 00:00:00"}),
        );
        rig.send(
            2,
            json!({"action":"load_message_delta","since":"2000-01-01 00:00:00"}),
        );

        let full = &ana.messages()[0]["conversations"]["team"];
        let simple = &bob.messages()[0]["conversations"]["team"];
        assert_eq!(full[0]["contents"], "ñandú");
        assert_eq!(full[1]["contents"], "[[img]]|.png|AAAA");
        assert_eq!(simple[0]["contents"], "?and?");
        assert_eq!(simple[1]["contents"], "[image]");
    }
}
