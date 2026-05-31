mod db;
mod server;
use crate::server::run;
use std::sync::mpsc::{self,Sender};
use std::sync::OnceLock;

// Create a global storage for the sender
static PANIC_TX: OnceLock<Sender<&'static str>> = OnceLock::new();

fn main() {
    let (tx, rx) = mpsc::channel();

    // 1. Store a clone of the sender in the global OnceLock
    PANIC_TX.set(tx.clone()).expect("Failed to set global sender");

    // 2. Handle Ctrl+C
    let tx_ctrlc = tx.clone();
    ctrlc::set_handler(move || {
        println!("\nShutdown signal received (Ctrl+C)...");
        let _ = tx_ctrlc.send("shutdown"); 
    }).expect("Error setting Ctrl-C handler");

    // 3. Handle Panics
    std::panic::set_hook(Box::new(|info| {
        eprintln!("Critical failure: {}", info);
        // Access the global sender to signal the server loop
        if let Some(tx) = PANIC_TX.get() {
            let _ = tx.send("shutdown");
        }
    }));

    run("0.0.0.0:6969", rx);
}