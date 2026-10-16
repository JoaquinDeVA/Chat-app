package com.chatapp.backend.protocol;

import java.util.List;

/** Request bodies of the TCP/JSON protocol (field names are part of the wire format). */
public final class Requests {

  private Requests() {}

  /** Check a username/password pair. */
  public record Auth(String username, String password) {}

  /** Register a new user. */
  public record AddUser(String username, String password) {}

  /** Create a chat with the given members. */
  public record CreateChat(String chatname, List<String> usernames) {}

  /** Store a message; {@code date} is {@code yyyy-MM-dd HH:mm:ss}. */
  public record SendMessage(String username, String chatname, String message, String date) {}

  /** List the members of a chat. */
  public record ChatMembers(String chatname) {}

  /** Messages of all the user's chats sent after {@code since} ({@code yyyy-MM-dd HH:mm:ss}). */
  public record MessageDelta(String username, String since) {}
}
