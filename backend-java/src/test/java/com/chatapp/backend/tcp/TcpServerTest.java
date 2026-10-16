package com.chatapp.backend.tcp;

import static org.assertj.core.api.Assertions.assertThat;

import com.chatapp.backend.protocol.RequestDispatcher;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** Real sockets against a server whose dispatcher echoes what it receives. */
class TcpServerTest {

  private final List<String> received = new ArrayList<>();
  private TcpServer server;
  private CompletableFuture<Void> serving;

  @BeforeEach
  void startServer() throws IOException {
    RequestDispatcher echo =
        new RequestDispatcher(List.of(), new ObjectMapper()) {
          @Override
          public String dispatch(String raw) {
            received.add(raw);
            return "echo:" + raw;
          }
        };
    server = new TcpServer(0, echo);
    serving = CompletableFuture.runAsync(server::serve);
  }

  @AfterEach
  void stopServer() throws IOException {
    server.close();
    serving.orTimeout(5, TimeUnit.SECONDS).join();
  }

  private Socket connect() throws IOException {
    Socket socket = new Socket("127.0.0.1", server.getPort());
    socket.setSoTimeout(5000);
    return socket;
  }

  private static void send(Socket socket, byte[]... parts) throws IOException, InterruptedException {
    OutputStream out = socket.getOutputStream();
    for (byte[] part : parts) {
      out.write(part);
      out.flush();
      Thread.sleep(30); // make the receiver see separate TCP segments
    }
  }

  private static String read(Socket socket) throws IOException {
    InputStream in = socket.getInputStream();
    ByteArrayOutputStream reply = new ByteArrayOutputStream();
    int next;
    while ((next = in.read()) != TcpServer.END_OF_TRANSMISSION) {
      assertThat(next).as("connection closed before the end of the reply").isNotEqualTo(-1);
      reply.write(next);
    }
    return reply.toString(StandardCharsets.UTF_8);
  }

  private static byte[] framed(String text) {
    byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
    byte[] result = new byte[bytes.length + 1];
    System.arraycopy(bytes, 0, result, 0, bytes.length);
    result[bytes.length] = TcpServer.END_OF_TRANSMISSION;
    return result;
  }

  @Test
  void answersAMessageAndKeepsTheConnectionOpen() throws Exception {
    try (Socket socket = connect()) {
      send(socket, framed("one"));
      assertThat(read(socket)).isEqualTo("echo:one");
      send(socket, framed("two"));
      assertThat(read(socket)).isEqualTo("echo:two");
    }
  }

  @Test
  void textIsUtf8EvenWhenACharacterIsSplitAcrossPackets() throws Exception {
    byte[] bytes = framed("ñandú 😀");
    try (Socket socket = connect()) {
      send(socket, java.util.Arrays.copyOfRange(bytes, 0, 1), java.util.Arrays.copyOfRange(bytes, 1, 8),
          java.util.Arrays.copyOfRange(bytes, 8, bytes.length));
      assertThat(read(socket)).isEqualTo("echo:ñandú 😀");
    }
  }

  @Test
  void severalMessagesInOnePacketAreAnsweredInOrder() throws Exception {
    byte[] both = new byte[framed("a").length + framed("b").length];
    System.arraycopy(framed("a"), 0, both, 0, 2);
    System.arraycopy(framed("b"), 0, both, 2, 2);
    try (Socket socket = connect()) {
      send(socket, both);
      assertThat(read(socket)).isEqualTo("echo:a");
      assertThat(read(socket)).isEqualTo("echo:b");
    }
  }

  @Test
  void aNewPeerIsServedAfterTheFirstOneDisconnects() throws Exception {
    try (Socket first = connect()) {
      send(first, framed("first"));
      assertThat(read(first)).isEqualTo("echo:first");
    }
    try (Socket second = connect()) {
      send(second, framed("second"));
      assertThat(read(second)).isEqualTo("echo:second");
    }
  }

  @Test
  void shutdownStopsTheServerWithoutAnswering() throws Exception {
    try (Socket socket = connect()) {
      send(socket, framed("SHUTDOWN{}"));
      assertThat(socket.getInputStream().read()).isEqualTo(-1);
    }
    serving.orTimeout(5, TimeUnit.SECONDS).join();
    assertThat(serving).isCompleted();
    assertThat(received).isEmpty();
  }

  @Test
  void closingTheServerEndsServe() throws Exception {
    server.close();
    serving.orTimeout(5, TimeUnit.SECONDS).join();
    assertThat(serving.isDone()).isTrue();
  }
}
