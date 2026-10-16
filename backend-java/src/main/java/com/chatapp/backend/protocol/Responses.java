package com.chatapp.backend.protocol;

import java.util.List;
import java.util.Map;

/** Response bodies of the TCP/JSON protocol (field names are part of the wire format). */
public final class Responses {

  private Responses() {}

  /** Result of an operation that changes data (register, create chat, send message). */
  public record Processed(boolean processed) {}

  /** Result of an authentication check. */
  public record Authorized(boolean authorized) {}

  /** Usernames of the members of a chat (empty if the chat does not exist). */
  public record Members(List<String> members) {}

  /** A message as sent to clients. */
  public record MessageView(String chatname, String author, String contents, String sent) {}

  /** Messages grouped by chat name. */
  public record Conversations(Map<String, List<MessageView>> conversations) {}

  /** Error reply for malformed or unknown requests. */
  public record Error(String error) {}
}
