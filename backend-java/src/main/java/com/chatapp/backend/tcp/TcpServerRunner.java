package com.chatapp.backend.tcp;

import com.chatapp.backend.protocol.RequestDispatcher;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.stereotype.Component;

/** Starts the {@link TcpServer} once Spring is ready and closes the application when it stops. */
@Component
public class TcpServerRunner implements CommandLineRunner {

  private final RequestDispatcher dispatcher;
  private final ConfigurableApplicationContext context;
  private final int port;

  public TcpServerRunner(
      RequestDispatcher dispatcher,
      ConfigurableApplicationContext context,
      @Value("${chat.tcp.port}") int port) {
    this.dispatcher = dispatcher;
    this.context = context;
    this.port = port;
  }

  @Override
  public void run(String... args) throws Exception {
    try (TcpServer server = new TcpServer(port, dispatcher)) {
      server.serve();
    } finally {
      context.close();
    }
  }
}
