//! The network loop: accepts connections, reads from them with `poll(2)` and hands the bytes to
//! [`Sessions`].
//!
//! The loop wakes up every [`POLL_INTERVAL_MS`] milliseconds even if nothing happens, so a
//! shutdown request (Ctrl+C) is noticed at once instead of waiting for the next client event.

use std::collections::HashMap;
use std::io::{self, Read};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::os::fd::AsRawFd;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use crate::backend::Backend;
use crate::sessions::{ClientId, Sessions};

/// How long `poll` may block before the shutdown flag is checked again.
pub const POLL_INTERVAL_MS: i32 = 100;

/// A write that blocks longer than this drops the client instead of freezing the server.
const WRITE_TIMEOUT: Duration = Duration::from_secs(5);

/// A listening socket plus the state of every connected client.
pub struct Server<B: Backend> {
    listener: TcpListener,
    sessions: Sessions<B, TcpStream>,
    readers: HashMap<ClientId, TcpStream>,
    next_id: ClientId,
}

impl<B: Backend> Server<B> {
    /// Starts listening on `address` (`host:port`; port 0 picks a free one).
    pub fn bind(address: &str, backend: B) -> io::Result<Self> {
        let listener = TcpListener::bind(address)?;
        listener.set_nonblocking(true)?;
        Ok(Server {
            listener,
            sessions: Sessions::new(backend),
            readers: HashMap::new(),
            next_id: 1,
        })
    }

    /// The address the server is listening on.
    pub fn local_addr(&self) -> io::Result<SocketAddr> {
        self.listener.local_addr()
    }

    /// Serves clients until `shutdown` becomes true, then tells the backend to stop.
    pub fn serve(&mut self, shutdown: &AtomicBool) {
        match self.local_addr() {
            Ok(address) => log::info!("listening on {address}"),
            Err(error) => log::warn!("listening (address unknown: {error})"),
        }

        while !shutdown.load(Ordering::SeqCst) {
            self.poll_once();
        }

        log::info!("shutting down");
        self.sessions.shutdown_backend();
    }

    /// One round of the loop: wait for activity, accept new clients, read from the ready ones.
    fn poll_once(&mut self) {
        let ids: Vec<ClientId> = self.readers.keys().copied().collect();
        let mut fds = Vec::with_capacity(ids.len() + 1);
        fds.push(libc::pollfd {
            fd: self.listener.as_raw_fd(),
            events: libc::POLLIN,
            revents: 0,
        });
        fds.extend(ids.iter().map(|id| libc::pollfd {
            fd: self.readers[id].as_raw_fd(),
            events: libc::POLLIN,
            revents: 0,
        }));

        // SAFETY: `fds` is a valid, initialized array of `fds.len()` pollfd structures.
        let ready = unsafe {
            libc::poll(
                fds.as_mut_ptr(),
                fds.len() as libc::nfds_t,
                POLL_INTERVAL_MS,
            )
        };
        if ready < 0 {
            let error = io::Error::last_os_error();
            if error.kind() != io::ErrorKind::Interrupted {
                log::error!("poll failed: {error}");
                std::thread::sleep(Duration::from_millis(POLL_INTERVAL_MS as u64));
            }
            return;
        }
        if ready == 0 {
            return;
        }

        if fds[0].revents & libc::POLLIN != 0 {
            self.accept_all();
        }
        for (id, fd) in ids.iter().zip(&fds[1..]) {
            if fd.revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR) != 0 {
                self.read_from(*id);
            }
        }
    }

    fn accept_all(&mut self) {
        loop {
            match self.listener.accept() {
                Ok((stream, address)) => self.add_client(stream, address),
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => return,
                Err(error) => {
                    log::warn!("accept failed: {error}");
                    return;
                }
            }
        }
    }

    fn add_client(&mut self, stream: TcpStream, address: SocketAddr) {
        let id = self.next_id;
        self.next_id += 1;
        let prepared = stream
            .set_nonblocking(false)
            .and_then(|()| stream.set_write_timeout(Some(WRITE_TIMEOUT)))
            .and_then(|()| stream.try_clone());
        match prepared {
            Ok(writer) => {
                log::info!("client {id} connected from {address}");
                self.sessions.connect(id, writer);
                self.readers.insert(id, stream);
            }
            Err(error) => log::warn!("could not set up the connection from {address}: {error}"),
        }
    }

    fn read_from(&mut self, id: ClientId) {
        let mut buffer = [0u8; 16 * 1024];
        let keep_open = match self
            .readers
            .get_mut(&id)
            .map(|stream| stream.read(&mut buffer))
        {
            None | Some(Ok(0)) | Some(Err(_)) => false,
            Some(Ok(read)) => self.sessions.receive(id, &buffer[..read]),
        };
        if !keep_open {
            self.sessions.disconnect(id);
        }
        // Sessions drop clients they cannot write to; close those sockets too.
        let sessions = &self.sessions;
        self.readers.retain(|client, _| sessions.contains(*client));
    }
}
