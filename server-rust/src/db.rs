use serde::{Deserialize, Serialize};
use std::collections::HashMap;
// use chrono::{DateTime,Utc};


#[derive(Debug,Serialize,Deserialize,Clone,PartialEq,Eq,Hash)]
pub struct User{
    pub uid: i32,
    pub username: String,
    pub password: String,
}
impl User{
    pub fn new(username: &str,password: &str)-> Option<Self>{

        let user = User{
            username: username.to_string(),
            password: password.to_string(),
            uid: 0,
        };


        Some(user)
    }

}

#[derive(Debug,Serialize,Deserialize)]
pub struct Chat{
    cid: i32,
    chatname: String
}
#[derive(Debug,Serialize,Deserialize)]
pub struct Participant {
    uid: i32,
    cid: i32,
    union_date: String,
}
#[derive(Debug,Serialize,Deserialize,Clone)]
pub struct Message{
    pub author: String,
    pub contents: String,
    pub sent: String,
    pub chatname: String,
}

//----------------------------------------------//
//            JSON REQS/RESPONSES               //
//----------------------------------------------//

#[derive(Debug,Serialize,Deserialize)]
pub struct  AddUserRequest{
    username: String,
    password: String,
}

impl AddUserRequest{
    pub fn new(username: String,password: String) -> Self{
        AddUserRequest { username, password }
    } 
    pub fn to_json(&self) -> String{
        let header = "AddUserRequest";
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
        content
    }
}

impl Message{
    pub fn to_cli_json(&self) -> String{
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}",json,0x04 as char));
        content
    }
}

#[derive(Debug,Serialize,Deserialize)]
pub struct  LoadConvDeltaReq{
    username: String,
    since: String,
}
impl LoadConvDeltaReq{
    
    pub fn new(username: String, since: String) -> Self{
        LoadConvDeltaReq { username, since }
    } 
    
    pub fn to_json(&self) -> String{
        let header = "LOADMESSAGEDELTA";
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
        content
    }

}
#[derive(Debug,Serialize,Deserialize)]
pub struct  LoadConvDeltaResp{
    pub conversations: HashMap<String, Vec<Message>>,
}

impl LoadConvDeltaResp{
    pub fn from_json(json: &str) -> Option<Self>{
       serde_json::from_str(json).ok()
    }
}

// #[derive(Debug,Serialize,Deserialize)]
// pub struct  LoadConversationsRequest{
//     username: String
// }

// impl LoadConversationsRequest{
    
//     pub fn new(username: String) -> Self{
//         LoadConversationsRequest { username }
//     } 
    
//     pub fn to_json(&self) -> String{
//         let header = "LoadConversationsRequest";
//         let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
//         let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
//         content
//     }
// }

#[derive(Debug,Serialize,Deserialize)]
pub struct  LoadConversationsResponse{
    //all info can be rebuilt from name and vec messages, except for chat creation date
    pub conversations: HashMap<String, Vec<Message>>,
}
impl LoadConversationsResponse{    

    pub fn new(conversations: HashMap<String, Vec<Message>>) -> Self{
        LoadConversationsResponse { conversations }
    } 

    pub fn from_json(json: &str) -> Option<Self>{
       serde_json::from_str(json).ok()
    }

    pub fn to_cli_json(&self) -> String{
        let r = LoginResponse{
            code: 1,
            msg: String::new(),
            conversations: self.conversations.clone(),
        };

        let json = serde_json::to_string_pretty(&r).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}",json,0x04 as char));
        content
    }
}

#[derive(Debug,Serialize,Deserialize)]
pub struct  LoadChatUsersResponse{
    //all info can be rebuilt from name and vec messages, except for chat creation date
    pub members: Vec<String>,
}
impl LoadChatUsersResponse{    
    
    pub fn from_json(json: &str) -> Option<Self>{
       serde_json::from_str(json).ok()
    }

}

#[derive(Debug,Serialize,Deserialize)]
pub struct  LoadChatUsersRequest{
    //all info can be rebuilt from name and vec messages, except for chat creation date
    pub chatname: String,
}
impl LoadChatUsersRequest{    
    pub fn new(chatname: String) -> Self{
        LoadChatUsersRequest { chatname }
    } 

    pub fn to_json(&self) -> String{
        let header = "GETCHATMEMBERSREQUEST";
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
        content
    }

}

#[derive(Debug,Serialize,Deserialize)]
pub struct  LoginResponse{
    //all info can be rebuilt from name and vec messages, except for chat creation date
    pub code: i32,
    pub msg: String,
    pub conversations: HashMap<String, Vec<Message>>,
}


//add user, send message
#[derive(Debug,Serialize,Deserialize)]
pub struct  Response{
    pub processed: bool
}
impl Response{
    pub fn parse(response: &Vec<u8>) -> bool{
        let response_str = String::from_utf8_lossy(&response);
        serde_json::from_str::<Response>(&response_str)
        .map(|r| r.processed)  // or whatever the relevant field is
        .unwrap_or(false)
    }
    pub fn new(processed: bool) -> Self{
        Response { processed }
    } 

    pub fn from_json(json: &str) -> Option<Self>{
       serde_json::from_str(json).ok()
    }

    pub fn to_cli_json(&mut self,msg: String) -> String{
        let response = CliResponse{
            processed:self.processed as i32,
            msg
        };

        let json = serde_json::to_string_pretty(&response).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}",json,0x04 as char));
        content
    }
}

#[derive(Debug,Serialize,Deserialize)]
pub struct  CliResponse{
    pub processed: i32,
    pub msg: String,
}

#[derive(Debug,Serialize,Deserialize)]
pub struct  SendMessageRequest{
    username: String,
    chatname: String,
    message: String,
    date: String
}
impl SendMessageRequest{

    pub fn new(username: String, chatname: String, message: String, date: String) -> Self{
        SendMessageRequest { username, chatname, message, date }
    }

    pub fn to_json(&self) -> String{
        let header = "SendMessageRequest";
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
        content
    }
}


#[derive(Debug,Serialize,Deserialize)]
pub struct AuthRequest{
    username: String,
    password: String,
}
impl AuthRequest{

    pub fn new(username: String, password: String) -> Self{
        AuthRequest { username, password }
    }

    pub fn to_json(&self) -> String{
        let header = "AuthRequest";
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
        content
    }
}

#[derive(Debug,Serialize,Deserialize)]
pub struct AuthResponse{
    authorized: bool
}
impl AuthResponse{

    pub fn new(authorized: bool) -> Self{
        AuthResponse { authorized }
    } 

    pub fn parse(response: &Vec<u8>) -> bool{
        let response_str = String::from_utf8_lossy(&response);
        serde_json::from_str::<AuthResponse>(&response_str)
        .map(|r| r.authorized)  // or whatever the relevant field is
        .unwrap_or(false)
    }

    pub fn from_json(json: &str) -> Option<Self>{
       serde_json::from_str(json).ok()
    }

    // pub fn to_cli_json(&mut self,msg : String, new_chats: HashMap<String, Vec<Message>>) -> String{
    //     String::from("")
    // }
}

#[derive(Debug,Serialize,Deserialize)]
struct CliAuthResponse{
    code: i32,
    msg: String,
    new_chats: HashMap<String, Vec<Message>>,
}
#[derive(Debug,Serialize,Deserialize)]
pub struct CreateChatRequest{
    usernames: Vec<String>,
    chatname: String,
}
impl CreateChatRequest{

    pub fn new(usernames: Vec<String>, chatname: String) -> Self{
        CreateChatRequest { usernames, chatname }
    }

    pub fn to_json(&self) -> String{
        let header = "CreateChatRequest";
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
        content
    }
}
#[derive(Debug,Serialize,Deserialize)]
pub struct ShutdownRequest{
    
}
impl ShutdownRequest{

    pub fn new() -> Self{
        ShutdownRequest {  }
    }

    pub fn to_json(&self) -> String{
        let header = "SHUTDOWN";
        let json = serde_json::to_string_pretty(&self).expect("failed to serialize to json");
        let content: String = String::from(&format!("{}{}{}",header,json,0x04 as char));
        content
    }
}