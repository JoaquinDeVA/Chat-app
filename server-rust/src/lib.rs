//! Relay server of the chat.
//!
//! Clients (the Python and C TUIs) speak a small JSON protocol over TCP. This server keeps one
//! [`sessions::Session`] per connection, authenticates users and forwards the operations to the
//! Java backend through the [`backend::Backend`] trait, pushing new messages and new chats to the
//! clients that are online.
//!
//! | Module | Role |
//! |---|---|
//! | [`config`] | ports and addresses, read from the environment |
//! | [`protocol`] | wire types shared by all the layers, framing helpers |
//! | [`backend`] | the backend interface and its TCP implementation |
//! | [`versions`] | what differs between protocol versions (v1 simple clients, v2 full clients) |
//! | [`sessions`] | the logic of every client request (no sockets, easy to test) |
//! | [`server`] | the `poll` loop that moves bytes between sockets and sessions |

pub mod backend;
pub mod config;
pub mod protocol;
pub mod server;
pub mod sessions;
pub mod versions;
