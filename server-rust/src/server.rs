use std::collections::HashMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::os::unix::io::{AsRawFd, RawFd};
use std::sync::mpsc::Receiver;
use chrono::Local;
use crate::db::*;

// ── Session entry ────────────────────────────────────────────────────────────
#[derive(Debug)]
struct Session {
    stream:   TcpStream,
    username: Option<String>, // None = not logged in yet
}

// ── Sessions (no Arc, no Mutex, lives entirely on the main-loop stack) ───────

pub struct Sessions {
    /// ip-string → Session
    map: HashMap<String, Session>,
    /// per-client accumulation buffer for incomplete (chunked) messages
    buffers: HashMap<String, Vec<u8>>,
    /// single persistent connection to the DB server
    db:  DbConn,
}

impl Sessions {
    pub fn new() -> Self {
        Sessions {
            map: HashMap::new(),
            buffers: HashMap::new(),
            db:  DbConn::new(),
        }
    }

    // ── low-level helpers ────────────────────────────────────────────────────

    fn is_logged(&self, ip: &str) -> bool {
        self.map.get(ip).map_or(false, |s| s.username.is_some())
    }

    fn username_of(&self, ip: &str) -> Option<&str> {
        self.map.get(ip)?.username.as_deref()
    }

    fn ip_of(&self, username: String) -> &str {
    self.map
        .iter()
        .find(|(_, s)| s.username.as_deref() == Some(&username))
        .map(|(ip, _)| ip.as_str()).unwrap()
}

    fn ip_of_opt(&self, username: String) -> Option<&str> {
    self.map
        .iter()
        .find(|(_, s)| s.username.as_deref() == Some(&username))
        .map(|(ip, _)| ip.as_str())
}


    fn write_to(&mut self, ip: &str, msg: &str) {
        if let Some(sess) = self.map.get_mut(ip) {
            let _ = sess.stream.write_all(msg.as_bytes());
        }
    }

    // ── called by run() when a new TCP connection arrives ────────────────────

    pub fn add_stream(&mut self, ip: String, stream: TcpStream) {
        self.map.insert(ip, Session { stream, username: None });
    }

    // ── called by run() when a fd goes readable ──────────────────────────────

    /// Returns false if the client disconnected and should be removed.
    pub fn handle_readable(&mut self, ip: &str) -> bool {
        let mut buf = [0u8; 4096];
        let n = match self.map.get_mut(ip) {
            None => return false,
            Some(sess) => match sess.stream.read(&mut buf) {
                Ok(0)  => return false,          // clean disconnect
                Ok(n)  => n,
                Err(_) => return false,
            },
        };

        // Append the new chunk to this client's accumulation buffer.
        let buffer = self.buffers.entry(ip.to_owned()).or_default();
        buffer.extend_from_slice(&buf[..n]);

        // Drain all complete messages (terminated by EOT 0x04) into an owned Vec
        // so that the borrow on `self.buffers` is fully released before we call
        // `match_json`, which needs `&mut self`.
        let mut complete: Vec<String> = Vec::new();
        while let Some(pos) = buffer.iter().position(|&b| b == 0x04) {
            let message: Vec<u8> = buffer.drain(..pos).collect();
            buffer.remove(0); // drop the EOT byte itself
            match String::from_utf8(message) {
                Ok(s)  => complete.push(s),
                Err(_) => eprintln!("Invalid UTF-8 from {}", ip),
            }
        }
        // `buffer` (and its &mut borrow of self.buffers) is no longer live here.

        for json in complete {
            let username = self.username_of(ip).map(str::to_owned).unwrap_or_default();
            self.match_json(json, username, ip.to_owned());
        }

        true
    }

    pub fn remove(&mut self, ip: &str) {
        self.map.remove(ip);
        self.buffers.remove(ip);
        println!("Client {} disconnected", ip);
    }

    // ── iterator over (fd, ip) pairs for select() ───────────────────────────

    pub fn fds(&self) -> Vec<(RawFd, String)> {
        self.map
            .iter()
            .map(|(ip, sess)| (sess.stream.as_raw_fd(), ip.clone()))
            .collect()
    }

    // ── JSON dispatch ────────────────────────────────────────────────────────

    fn get_json_values(json: &str, keys: &[&str]) -> Vec<String> {
        let parsed: serde_json::Value = serde_json::from_str(json).unwrap_or_default();
        keys.iter()
            .map(|k| parsed[k].as_str().unwrap_or("").to_string())
            .collect()
    }

    fn match_json(&mut self, json: String, username: String, ip: String) {
        println!("Json is :{}",json);
        let parsed: serde_json::Value = match serde_json::from_str(&json) {
            Ok(v)  => v,
            Err(e) => { eprintln!("Bad JSON from {}: {}", ip, e); return; }
        };
        let action = parsed["action"].as_str().unwrap_or("unknown").to_owned();
        
        println!("Handling json: {}",json);

        match action.as_str() {
            "create_user" => {
                println!("Creating user");
                let vals = Self::get_json_values(&json, &["username", "password"]);
                self.handle_create_user(vals[0].clone(), vals[1].clone(), ip);
            }
            "login" => {
                println!("Authenticating user");
                let vals = Self::get_json_values(&json, &["username", "password"]);
                self.handle_login(vals[0].clone(), vals[1].clone(), ip);
            }
            "load_message_delta" => {
                println!("Loading message delta");
                let vals = Self::get_json_values(&json, &["username", "since"]);
                self.handle_message_delta(vals[0].clone(), vals[1].clone(), ip);
            }
            "create_chat" => {
                println!("Creating chat");
                let chatname = parsed["chat_name"].as_str().unwrap_or("").to_owned();
                let participants: Vec<String> = parsed["participants"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect();
                self.handle_create_chat(chatname, participants, ip);
            }
            "send_msg" => {
                println!("Sending message");
                let vals = Self::get_json_values(&json, &["username", "chat", "msg"]);
                self.handle_send_message(vals[0].clone(), vals[1].clone(), vals[2].clone(), ip);
            }
            "logout" => {
                println!("Logging user out");
                self.handle_logout(username, ip);
            }
            other => eprintln!("Unknown action '{}' from {}", other, ip),
        }
    }

    // ── handlers ─────────────────────────────────────────────────────────────

    fn handle_create_user(&mut self, username: String, password: String, ip: String) {
        if self.is_logged(&ip) {
            let r = Response::new(false).to_cli_json("You are already logged in".into());
            self.write_to(&ip, &r);
            return;
        }
        let resp = match self.db.add_user(username.clone(), password.clone()) {
            Ok(json)      => json,
            Err(err_json) => err_json,
        };

        println!("\nResponse to cli: {}\n",resp);
        println!("Raw response to cli: {:?}\n",resp);

        self.write_to(&ip, &resp);

        self.handle_login(username, password, ip);
    }

    fn handle_login(&mut self, username: String, password: String, ip: String) {
        if self.is_logged(&ip) {
            let r = Response::new(false).to_cli_json("Already logged in".into());

            println!("\nResponse to cli: {}\n",r);
            println!("Raw response to cli: {:?}\n",r);

            self.write_to(&ip, &r);
            return;
        }

        // if let Err(msg) = self.db.auth_user(username.clone(), password) {
        //     let r = Response::new(false).to_cli_json(msg);
        //     println!("\nResponse to cli: {}\n",r);
        //     println!("Raw response to cli: {:?}\n",r);
        //     self.write_to(&ip, &r);
        //     return;
        // }

        let auth_result = self.db.auth_user(username.clone(), password);
        let resp = match &auth_result {
            Ok(msg) => Response::new(true).to_cli_json(msg.clone()),
            Err(msg) => Response::new(false).to_cli_json(msg.clone()),
        };
        println!("\nResponse to cli: {}\n",resp);
        println!("Raw response to cli: {:?}\n",resp);
        self.write_to(&ip, &resp);

        if auth_result.is_ok() {
            if let Some(sess) = self.map.get_mut(&ip) {
                sess.username = Some(username);
            }
        }
    }

    fn handle_message_delta(&mut self, username: String, since: String, ip: String) {
        if !self.is_logged(&ip) {
            let r = Response::new(false).to_cli_json("Not logged in".into());

            println!("\nResponse to cli: {}\n",r);
            println!("Raw response to cli: {:?}\n",r);

            self.write_to(&ip, &r);
            return;
        }

        //LOAD CONVERSATIONS
        let resp = match self.db.load_conversations_delta(username.clone(),since.clone()) {
            Ok(r)  => r,
            Err(e) => { eprintln!("load_conversations error: {}", e); return; }
        };
        println!("\nResponse to cli: {}\n",resp);
        println!("Raw response to cli: {:?}\n",resp);

        //Get all conversations
        match LoadConvDeltaResp::from_json(&resp.clone()){
            Some(resp) => {
                for conv in resp.conversations.keys().into_iter(){
                let notify_json = format!("{{\"chatname\":\"{}\"}}{}", conv, 0x04 as char);
                self.write_to(&ip, &notify_json);
                }
            },
            None => {},
        }
        self.write_to(&ip, &resp);
    }

    fn handle_create_chat(&mut self, chatname: String, participants: Vec<String>, ip: String) {
    if !self.is_logged(&ip) {
        let r = Response::new(false).to_cli_json("You are not logged in".into());
        println!("\nResponse to cli: {}\n",r);
            println!("Raw response to cli: {:?}\n",r);
        self.write_to(&ip, &r);
        return;
    }

    let resp = match self.db.create_chat(participants.clone(), chatname.clone()) {
        Ok(json) => json,
        Err(err_json) => {
            println!("\nResponse to cli: {}\n",err_json);
            println!("Raw response to cli: {:?}\n",err_json);
            self.write_to(&ip, &err_json);
            return;
        }
    };

    // Send success response to creator first so api_create_group gets it from recv()
    println!("\nResponse to cli: {}\n",resp);
    println!("Raw response to cli: {:?}\n",resp);
    self.write_to(&ip, &resp);

    // Notify other online participants with proper JSON
    let notify_json = format!("{{\"chatname\":\"{}\"}}{}", chatname, 0x04 as char);
    let participant_ips: Vec<String> = participants
        .iter()
        .filter_map(|p| self.ip_of_opt(p.clone()))
        .map(|s| s.to_owned())
        .collect();

    for participant_ip in participant_ips {
        if participant_ip != ip {
            if let Some(session) = self.map.get_mut(&participant_ip) {
                println!("\nResponse to cli: {}\n",notify_json);
                println!("Raw response to cli: {:?}\n",notify_json);
                session
                    .stream
                    .write_all(notify_json.as_bytes())
                    .expect("Could not notify participant on chat creation");
            }
        }
    }
}

    fn handle_send_message(&mut self, username: String, chat: String, msg: String, ip: String) {
        if !self.is_logged(&ip) {
            let r = Response::new(false).to_cli_json("You are not logged in".into());
            println!("\nResponse to cli: {}\n",r);
            println!("Raw response to cli: {:?}\n",r);
            self.write_to(&ip, &r);
            return;
        }
        let now = Local::now().naive_local();
        let time = now.format("%Y-%m-%d %H:%M:%S").to_string(); 
        let resp = match self.db.send_message(username.clone(), chat.clone(), msg.clone(),time.clone()) {
            Ok(json)      => json,
            Err(err_json) => err_json,
        };

        let msg = Message{
            author: username.clone(),
            chatname: chat.clone(),
            contents: msg,
            sent : time,
        };

        self.notify_chat_users(username, chat, msg);

        println!("\nResponse to cli: {}\n",resp);
        println!("Raw response to cli: {:?}\n",resp);
        self.write_to(&ip, &resp);
    }

    fn handle_logout(&mut self, _username: String, ip: String) {
        if !self.is_logged(&ip) {
            let r = Response::new(false).to_cli_json("You are not logged in".into());
            println!("\nResponse to cli: {}\n",r);
            println!("Raw response to cli: {:?}\n",r);
            self.write_to(&ip, &r);
            return;
        }
        // if let Some(_sess) = self.map.get_mut(&ip) {
            self.map.remove(&ip);
        // }
        println!("Client {} logged out", ip);
        println!("Sessions: {:?}", self.map);
    }

    pub fn notify_chat_users(&mut self, username: String,chatname: String,msg: Message){

        let text = self.db.load_chat_users(chatname);
        match LoadChatUsersResponse::from_json(&text) {
        Some(lcr) => {
            let json = msg.to_cli_json();
            let users = lcr.members.clone();
            println!("Searching for notify users in :{:?}", self.map);
            for user in users.iter() {
                if *user != username {
                    let is_online = self.map.values().any(|s| s.username.as_deref() == Some(user));
                    if is_online {
                        println!("Notifying {} about message: {}", user, msg.contents);
                        self.notify_user(user.into(), json.clone());
                } else {
                        println!("User {} is offline, skipping", user);
                }
            }
        }
    },
    None => {
        //  :3
    },
}
    }

    pub fn notify_user(&mut self,username: String,json:String){
        let ip = String::from(self.ip_of(username.clone()));
        self.map.get_mut(&ip).unwrap().stream.write_all(json.clone().as_bytes()).expect(&format!("Could not notify {}",username));
    }

}

impl Drop for Sessions {
    fn drop(&mut self) {
        println!("Running cleanup: Closing database.");
        self.db.shutdown();
    }
}

// ── Main loop ────────────────────────────────────────────────────────────────

pub fn run(listener_addr: &str,rx: Receiver<&str>) {
    let listener = TcpListener::bind(listener_addr).expect("Failed to bind listener");
    listener.set_nonblocking(true).expect("set_nonblocking failed");

    let listener_fd = listener.as_raw_fd();
    let mut sessions = Sessions::new();


    println!("Listening on {}", listener_addr);

    loop {

        if let Ok(signal) = rx.try_recv() {
            if signal == "shutdown" {
                // CALL YOUR CLEANUP HERE
                drop(sessions); 
                break;
            }
        }

        // ── build fd_set ─────────────────────────────────────────────────────
        let mut read_fds = unsafe {
            let mut set = std::mem::zeroed::<libc::fd_set>();
            libc::FD_ZERO(&mut set);
            set
        };

        let mut max_fd = listener_fd;
        unsafe { libc::FD_SET(listener_fd, &mut read_fds); }

        let client_fds = sessions.fds();
        for (fd, _) in &client_fds {
            unsafe { libc::FD_SET(*fd, &mut read_fds); }
            if *fd > max_fd { max_fd = *fd; }
        }

        // ── block until something is readable (no timeout) ───────────────────
        let ready = unsafe {
            libc::select(
                max_fd + 1,
                &mut read_fds,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            )
        };

        if ready < 0 {
            eprintln!("select() error");
            continue;
        }

        // ── new connection? ───────────────────────────────────────────────────
        if unsafe { libc::FD_ISSET(listener_fd, &read_fds) } {
            match listener.accept() {
                Ok((stream, addr)) => {
                    let ip = addr.to_string();
                    println!("New connection: {}", ip);
                    stream.set_nonblocking(false).ok(); // blocking reads in handler
                    sessions.add_stream(ip, stream);
                }
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {}
                Err(e) => eprintln!("accept error: {}", e),
            }
        }

        // ── existing clients ──────────────────────────────────────────────────
        let mut to_remove: Vec<String> = Vec::new();
        for (fd, ip) in &client_fds {
            if unsafe { libc::FD_ISSET(*fd, &read_fds) } {
                if !sessions.handle_readable(ip) {
                    to_remove.push(ip.clone());
                }
            }
        }
        for ip in to_remove {
            sessions.remove(&ip);
        }

    }
}


// ── DbConn (single persistent connection, owned by Sessions) ─────────────────

pub struct DbConn {
    stream: TcpStream,
}

impl DbConn {
    pub fn new() -> Self {
        DbConn {
            stream: TcpStream::connect("127.0.0.1:9090")
                .expect("Failed to connect to database"),
        }
    }

    fn read_until_eot(&mut self) -> Vec<u8> {
        let mut response = Vec::new();
        let mut buf = [0u8; 4096];
        loop {
            let n = self.stream.read(&mut buf).expect("DB read failed");
            if n == 0 { break; }
            if let Some(pos) = buf[..n].iter().position(|&b| b == 0x04) {
                response.extend_from_slice(&buf[..pos]);
                break;
            }
            response.extend_from_slice(&buf[..n]);
        }
        println!("DB RECV: {}\n\n", String::from_utf8_lossy(&response));
        response
    }

    fn parse_response(&mut self, success_str: String, err_str: String) -> Result<String, String> {
        let response = self.read_until_eot();
        match Response::parse(&response) {
            true  => Ok(success_str),
            false => Err(Response::new(false).to_cli_json(err_str)),
        }
    }

    pub fn add_user(&mut self, username: String, password: String) -> Result<String, String> {
        let json = AddUserRequest::new(username, password).to_json();
        println!("DB SEND: {}", json);
        self.stream.write_all(json.as_bytes()).expect("DB write failed");
        let ok = Response::new(true).to_cli_json("User added".into());
        self.parse_response(ok, "Could not add user".into())
    }

    pub fn auth_user(&mut self, username: String, password: String) -> Result<String, String> {
        let json = AuthRequest::new(username, password).to_json();
        self.stream.write_all(json.as_bytes()).expect("DB write failed");
        let response = self.read_until_eot();
        match AuthResponse::parse(&response) {
            true  => Ok("ok".into()),
            false => Err("Authentication failed".into()),
        }
    }

    // pub fn load_conversations(&mut self, username: String) -> Result<String, String> {
    //     let json = LoadConversationsRequest::new(username.clone()).to_json();
    //     println!("DB SEND load_conversations for {}: {}", username, json);
    //     self.stream.write_all(json.as_bytes()).expect("DB write failed");
    //     let response = self.read_until_eot();
    //     let text = String::from_utf8_lossy(&response).to_string();
    //     match LoadConversationsResponse::from_json(&text) {
    //         Some(lcr) => Ok(lcr.to_cli_json()),
    //         None      => Err("Could not parse conversations response".into()),
    //     }
    // }

    pub fn load_conversations_delta(&mut self, username: String, since: String) -> Result<String, String> {
        let json = LoadConvDeltaReq::new(username.clone(),since).to_json();
        println!("DB SEND load_conversations for {}: {}", username, json);
        self.stream.write_all(json.as_bytes()).expect("DB write failed");
        let response = self.read_until_eot();
        let text = String::from_utf8_lossy(&response).to_string();
        match LoadConversationsResponse::from_json(&text) {
            Some(lcr) => Ok(lcr.to_cli_json()),
            None      => Err("Could not parse conversations response".into()),
        }
    }

    pub fn load_chat_users(&mut self,chatname: String) -> String{
        let json = LoadChatUsersRequest::new(chatname.clone()).to_json();
        self.stream.write_all(json.as_bytes()).expect("DB write failed");
        let response = self.read_until_eot();
        String::from_utf8_lossy(&response).to_string()
    }

    pub fn create_chat(&mut self, usernames: Vec<String>, chatname: String) -> Result<String, String> {
        let json = CreateChatRequest::new(usernames, chatname).to_json();
        println!("Sending create chat request: {}",json);
        self.stream.write_all(json.as_bytes()).expect("DB write failed");
        let ok = Response::new(true).to_cli_json("Chat created".into());
        self.parse_response(ok, "Could not create chat".into())
    }

    pub fn send_message(
        &mut self,
        username: String,
        chatname: String,
        contents: String,
        time: String,
    ) -> Result<String, String> {
        let json = SendMessageRequest::new(username, chatname, contents, time).to_json();
        self.stream.write_all(json.as_bytes()).expect("DB write failed");
        let ok = Response::new(true).to_cli_json("Message sent".into());
        self.parse_response(ok, "Could not send message".into())
    }

    // pub fn user_exists(&mut self, username: String) -> bool {
    //     let json = AddUserRequest::new(username, String::new()).to_json();
    //     self.stream.write_all(json.as_bytes()).expect("DB write failed");
    //     let response = self.read_until_eot();
    //     Response::parse(&response)
    // }

    pub fn shutdown(&mut self) {
    let json = ShutdownRequest::new().to_json();
    self.stream.write_all(json.as_bytes()).expect("DB write failed");
    self.stream.flush().expect("Failed to flush shutdown request");
}
}