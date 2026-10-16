//! Protocol versions.
//!
//! Every client opens the conversation with `{"action":"hello","version":N}`. The version it
//! announces selects an implementation of [`Protocol`] for that connection. Only what really
//! differs between versions is expressed here; everything else (authentication, chats, delivery)
//! is shared by all versions.
//!
//! | | v1 (simple clients, e.g. the C one) | v2 (full clients, e.g. the Python one) |
//! |---|---|---|
//! | Text sent | printable ASCII, up to 1000 characters | any text |
//! | Images | not understood: shown as `[image]` | supported |
//! | Text received | non-ASCII characters shown as `?` | unchanged |
//! | Registration | one reply, already logged in | two replies (result, then login) |

use crate::protocol::ChatMessage;

/// Versions this server speaks, oldest first.
pub const SUPPORTED_VERSIONS: [u32; 2] = [1, 2];

/// Longest message a v1 client may send, in characters.
pub const V1_MAX_MESSAGE_CHARS: usize = 1000;

/// Marker that starts a message carrying an image (see the Python client).
const IMAGE_TAG: &str = "[[img]]|";

/// What a message is shown as to a client that cannot display images.
const IMAGE_PLACEHOLDER: &str = "[image]";

/// True if `text` is a message that carries an image.
pub fn is_image(text: &str) -> bool {
    text.starts_with(IMAGE_TAG)
}

/// The behaviour that depends on the protocol version a client speaks.
///
/// The default methods are the behaviour of the most capable version, so a version only
/// overrides what it does differently.
pub trait Protocol: Send {
    /// The version number, as announced in `hello`.
    fn version(&self) -> u32;

    /// Whether registering is answered twice: first the result, then the result of the automatic
    /// login. Otherwise a single reply that already means "registered and logged in".
    fn registration_sends_login_reply(&self) -> bool {
        true
    }

    /// Checks a message a client wants to send.
    ///
    /// Returns the text to store, or the reason why it is refused.
    fn check_message(&self, text: &str) -> Result<String, &'static str> {
        if text.is_empty() {
            Err("Empty message")
        } else {
            Ok(text.to_owned())
        }
    }

    /// How a message is shown to a client of this version.
    fn present(&self, message: &ChatMessage) -> ChatMessage {
        message.clone()
    }
}

/// The full protocol: Unicode text and images.
pub struct V2;

impl Protocol for V2 {
    fn version(&self) -> u32 {
        2
    }
}

/// The simple protocol: plain ASCII text, no images, one reply to a registration.
pub struct V1;

impl Protocol for V1 {
    fn version(&self) -> u32 {
        1
    }

    fn registration_sends_login_reply(&self) -> bool {
        false
    }

    fn check_message(&self, text: &str) -> Result<String, &'static str> {
        let plain = text.chars().all(|c| c == ' ' || c.is_ascii_graphic());
        if text.is_empty()
            || text.chars().count() > V1_MAX_MESSAGE_CHARS
            || !plain
            || is_image(text)
        {
            return Err("Only plain ASCII text of up to 1000 characters is allowed");
        }
        Ok(text.to_owned())
    }

    fn present(&self, message: &ChatMessage) -> ChatMessage {
        let contents = if is_image(&message.contents) {
            IMAGE_PLACEHOLDER.to_owned()
        } else {
            message
                .contents
                .chars()
                .map(|c| {
                    if c == ' ' || c.is_ascii_graphic() {
                        c
                    } else if c.is_ascii_control() {
                        ' '
                    } else {
                        '?'
                    }
                })
                .collect()
        };
        ChatMessage {
            contents,
            ..message.clone()
        }
    }
}

/// The implementation for a version number, or `None` if it is not supported.
pub fn for_version(version: u32) -> Option<Box<dyn Protocol>> {
    match version {
        1 => Some(Box::new(V1)),
        2 => Some(Box::new(V2)),
        _ => None,
    }
}

/// True if `name` is acceptable as a username or chat name: 1 to `max` characters among ASCII
/// letters, digits, `_`, `-` and `.`.
///
/// Identifiers are plain ASCII in every version, so that a simple client can always type and
/// display the name of any user or chat.
pub fn is_valid_name(name: &str, max: usize) -> bool {
    !name.is_empty()
        && name.chars().count() <= max
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn message(contents: &str) -> ChatMessage {
        ChatMessage {
            author: "ana".into(),
            contents: contents.into(),
            sent: "2026-05-04 10:30:00".into(),
            chatname: "team".into(),
        }
    }

    #[test]
    fn only_known_versions_have_an_implementation() {
        assert_eq!(for_version(1).unwrap().version(), 1);
        assert_eq!(for_version(2).unwrap().version(), 2);
        assert!(for_version(0).is_none() && for_version(3).is_none());
        assert!(SUPPORTED_VERSIONS.iter().all(|v| for_version(*v).is_some()));
    }

    #[test]
    fn v2_accepts_and_shows_everything() {
        let v2 = V2;
        assert!(v2.registration_sends_login_reply());
        assert_eq!(
            v2.check_message("hola ñ 😀\nline 2").unwrap(),
            "hola ñ 😀\nline 2"
        );
        assert_eq!(
            v2.check_message("[[img]]|.png|AAAA").unwrap(),
            "[[img]]|.png|AAAA"
        );
        assert!(v2.check_message("").is_err());
        assert_eq!(v2.present(&message("hola ñ 😀")), message("hola ñ 😀"));
    }

    #[test]
    fn v1_accepts_only_plain_ascii_text() {
        let v1 = V1;
        assert!(!v1.registration_sends_login_reply());
        assert_eq!(
            v1.check_message("Hello, world! 123 ~").unwrap(),
            "Hello, world! 123 ~"
        );
        for refused in [
            "",
            "hola ñ",
            "smile 😀",
            "two\nlines",
            "tab\t",
            "[[img]]|.png|AAAA",
        ] {
            assert!(
                v1.check_message(refused).is_err(),
                "{refused:?} must be refused"
            );
        }
        assert!(v1.check_message(&"a".repeat(V1_MAX_MESSAGE_CHARS)).is_ok());
        assert!(
            v1.check_message(&"a".repeat(V1_MAX_MESSAGE_CHARS + 1))
                .is_err()
        );
    }

    #[test]
    fn v1_is_shown_a_degraded_but_readable_message() {
        let v1 = V1;
        assert_eq!(v1.present(&message("plain")).contents, "plain");
        assert_eq!(v1.present(&message("hola ñ")).contents, "hola ?");
        assert_eq!(
            v1.present(&message("😀 hi")).contents,
            "? hi",
            "one placeholder per character, not per byte"
        );
        assert_eq!(v1.present(&message("a\nb")).contents, "a b");
        assert_eq!(
            v1.present(&message("[[img]]|.png|AAAA")).contents,
            "[image]"
        );
        let shown = v1.present(&message("ñ"));
        assert_eq!(
            (shown.author.as_str(), shown.chatname.as_str()),
            ("ana", "team"),
            "only the text changes"
        );
    }

    #[test]
    fn names_are_plain_ascii_identifiers() {
        for good in ["ana", "Ana_01", "team-a", "v1.2", "a"] {
            assert!(is_valid_name(good, 50), "{good}");
        }
        for bad in ["", "équipe", "with space", "a/b", "quote\"", "😀"] {
            assert!(!is_valid_name(bad, 50), "{bad:?}");
        }
        assert!(is_valid_name(&"a".repeat(50), 50) && !is_valid_name(&"a".repeat(51), 50));
    }
}
