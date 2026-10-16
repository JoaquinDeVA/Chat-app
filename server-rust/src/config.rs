//! Runtime configuration, read from environment variables.

use std::fmt;

/// Where the server listens and where the backend is.
///
/// | Variable | Default |
/// |---|---|
/// | `CHAT_SERVER_BIND` | `127.0.0.1` |
/// | `CHAT_SERVER_PORT` | `6969` |
/// | `CHAT_BACKEND_HOST` | `127.0.0.1` |
/// | `CHAT_BACKEND_PORT` | `9090` |
///
/// The server listens on the loopback interface by default because the protocol is not
/// encrypted; set `CHAT_SERVER_BIND=0.0.0.0` knowingly to accept remote clients.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    /// Interface the clients connect to.
    pub bind: String,
    /// Port the clients connect to.
    pub port: u16,
    /// Host of the Java backend.
    pub backend_host: String,
    /// Port of the Java backend.
    pub backend_port: u16,
}

/// A variable holds something that is not a valid port.
#[derive(Debug, PartialEq, Eq)]
pub struct ConfigError {
    /// Name of the offending variable.
    pub variable: &'static str,
    /// Its value.
    pub value: String,
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{}={:?} is not a valid port (1-65535)",
            self.variable, self.value
        )
    }
}

impl std::error::Error for ConfigError {}

impl Config {
    /// Reads the configuration from the process environment.
    pub fn from_env() -> Result<Self, ConfigError> {
        Self::from_lookup(|name| std::env::var(name).ok())
    }

    /// Reads the configuration through `lookup`, which returns the value of a variable if set.
    pub fn from_lookup(lookup: impl Fn(&str) -> Option<String>) -> Result<Self, ConfigError> {
        let text = |name: &str, default: &str| lookup(name).unwrap_or_else(|| default.to_owned());
        let port = |name: &'static str, default: u16| match lookup(name) {
            None => Ok(default),
            Some(value) => {
                value
                    .trim()
                    .parse::<u16>()
                    .ok()
                    .filter(|p| *p != 0)
                    .ok_or(ConfigError {
                        variable: name,
                        value,
                    })
            }
        };
        Ok(Config {
            bind: text("CHAT_SERVER_BIND", "127.0.0.1"),
            port: port("CHAT_SERVER_PORT", 6969)?,
            backend_host: text("CHAT_BACKEND_HOST", "127.0.0.1"),
            backend_port: port("CHAT_BACKEND_PORT", 9090)?,
        })
    }

    /// `host:port` the clients connect to.
    pub fn listen_addr(&self) -> String {
        format!("{}:{}", self.bind, self.port)
    }

    /// `host:port` of the backend.
    pub fn backend_addr(&self) -> String {
        format!("{}:{}", self.backend_host, self.backend_port)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lookup(pairs: &'static [(&'static str, &'static str)]) -> impl Fn(&str) -> Option<String> {
        move |name| {
            pairs
                .iter()
                .find(|(key, _)| *key == name)
                .map(|(_, v)| v.to_string())
        }
    }

    #[test]
    fn defaults() {
        let config = Config::from_lookup(lookup(&[])).unwrap();
        assert_eq!(config.listen_addr(), "127.0.0.1:6969");
        assert_eq!(config.backend_addr(), "127.0.0.1:9090");
    }

    #[test]
    fn every_value_can_be_overridden() {
        let config = Config::from_lookup(lookup(&[
            ("CHAT_SERVER_BIND", "0.0.0.0"),
            ("CHAT_SERVER_PORT", "7000"),
            ("CHAT_BACKEND_HOST", "db.local"),
            ("CHAT_BACKEND_PORT", " 9191 "),
        ]))
        .unwrap();
        assert_eq!(config.listen_addr(), "0.0.0.0:7000");
        assert_eq!(config.backend_addr(), "db.local:9191");
    }

    #[test]
    fn invalid_ports_are_reported_with_the_variable_name() {
        for bad in ["abc", "0", "70000", "-1", ""] {
            let owned = bad.to_string();
            let error = Config::from_lookup(move |name| {
                (name == "CHAT_SERVER_PORT").then(|| owned.clone())
            })
            .unwrap_err();
            assert_eq!(error.variable, "CHAT_SERVER_PORT");
            assert!(error.to_string().contains("CHAT_SERVER_PORT"));
        }
    }
}
