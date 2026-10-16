//! Chat relay server: `chat-server`. Configuration comes from environment variables, see
//! [`chat_server::config::Config`].

use std::process::ExitCode;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use chat_server::backend::TcpBackend;
use chat_server::config::Config;
use chat_server::server::Server;

fn main() -> ExitCode {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = match Config::from_env() {
        Ok(config) => config,
        Err(error) => {
            log::error!("{error}");
            return ExitCode::from(2);
        }
    };

    let backend = match TcpBackend::connect(&config.backend_addr()) {
        Ok(backend) => backend,
        Err(error) => {
            log::error!(
                "cannot reach the backend at {}: {error} (is it running?)",
                config.backend_addr()
            );
            return ExitCode::FAILURE;
        }
    };

    let mut server = match Server::bind(&config.listen_addr(), backend) {
        Ok(server) => server,
        Err(error) => {
            log::error!("cannot listen on {}: {error}", config.listen_addr());
            return ExitCode::FAILURE;
        }
    };

    let shutdown = Arc::new(AtomicBool::new(false));
    let flag = Arc::clone(&shutdown);
    if let Err(error) = ctrlc::set_handler(move || flag.store(true, Ordering::SeqCst)) {
        log::error!("cannot install the Ctrl+C handler: {error}");
        return ExitCode::FAILURE;
    }

    server.serve(&shutdown);
    ExitCode::SUCCESS
}
