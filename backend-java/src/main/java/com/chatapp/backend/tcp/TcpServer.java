package com.chatapp.backend.tcp;

import com.chatapp.backend.protocol.RequestDispatcher;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Minimal TCP server of the backend: one peer at a time (the Rust server), UTF-8 messages
 * terminated by the end-of-transmission byte (0x04), one reply per message.
 *
 * <p>A message whose first word is {@code SHUTDOWN} stops the server.
 */
public final class TcpServer implements AutoCloseable {

  /** Delimiter between messages, in both directions. */
  public static final int END_OF_TRANSMISSION = 0x04;

  private static final Logger log = LoggerFactory.getLogger(TcpServer.class);

  private final ServerSocket serverSocket;
  private final RequestDispatcher dispatcher;
  private volatile boolean running = true;

  /**
   * Binds the server socket.
   *
   * @param port port to listen on; 0 picks a free one (see {@link #getPort()})
   * @param dispatcher answers the messages
   * @throws IOException if the port cannot be bound
   */
  public TcpServer(int port, RequestDispatcher dispatcher) throws IOException {
    this.serverSocket = new ServerSocket(port);
    this.dispatcher = dispatcher;
  }

  /** The port the server is listening on. */
  public int getPort() {
    return serverSocket.getLocalPort();
  }

  /** Accepts peers one after another until a {@code SHUTDOWN} message arrives or {@link #close()}. */
  public void serve() {
    log.info("Listening on port {}", getPort());
    while (running) {
      try (Socket peer = serverSocket.accept()) {
        log.info("Peer connected: {}", peer.getRemoteSocketAddress());
        serveConnection(peer);
      } catch (SocketException e) {
        if (running) {
          log.warn("Socket error: {}", e.getMessage());
        }
      } catch (IOException e) {
        log.warn("Connection lost: {}", e.getMessage());
      }
    }
    log.info("Server stopped");
  }

  private void serveConnection(Socket peer) throws IOException {
    InputStream in = peer.getInputStream();
    OutputStream out = peer.getOutputStream();
    ByteArrayOutputStream message = new ByteArrayOutputStream();
    int next;
    while (running && (next = in.read()) != -1) {
      if (next != END_OF_TRANSMISSION) {
        message.write(next);
        continue;
      }
      String text = message.toString(StandardCharsets.UTF_8);
      message.reset();
      if (text.strip().toUpperCase(Locale.ROOT).startsWith("SHUTDOWN")) {
        log.info("Shutdown requested");
        running = false;
        return;
      }
      out.write(dispatcher.dispatch(text).getBytes(StandardCharsets.UTF_8));
      out.write(END_OF_TRANSMISSION);
      out.flush();
    }
  }

  /** Stops accepting connections; {@link #serve()} returns shortly after. */
  @Override
  public void close() throws IOException {
    running = false;
    serverSocket.close();
  }
}
