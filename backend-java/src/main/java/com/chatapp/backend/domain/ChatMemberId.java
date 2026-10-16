package com.chatapp.backend.domain;

import java.io.Serializable;
import java.util.Objects;

/** Composite primary key of {@link ChatMember}: the ids of the user and of the chat. */
public class ChatMemberId implements Serializable {

  private static final long serialVersionUID = 1L;

  private Long user;
  private Long chat;

  public ChatMemberId() {}

  public ChatMemberId(Long user, Long chat) {
    this.user = user;
    this.chat = chat;
  }

  @Override
  public boolean equals(Object other) {
    return other instanceof ChatMemberId id
        && Objects.equals(user, id.user)
        && Objects.equals(chat, id.chat);
  }

  @Override
  public int hashCode() {
    return Objects.hash(user, chat);
  }
}
