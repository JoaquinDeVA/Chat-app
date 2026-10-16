package com.chatapp.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/** Membership of a user in a chat. */
@Entity
@Table(name = "chat_members")
@IdClass(ChatMemberId.class)
public class ChatMember {

  @Id
  @ManyToOne(optional = false)
  @JoinColumn(name = "user_id")
  private User user;

  @Id
  @ManyToOne(optional = false)
  @JoinColumn(name = "chat_id")
  private Chat chat;

  @Column(name = "joined_at", nullable = false)
  private LocalDateTime joinedAt;

  protected ChatMember() {}

  public ChatMember(User user, Chat chat, LocalDateTime joinedAt) {
    this.user = user;
    this.chat = chat;
    this.joinedAt = joinedAt;
  }

  public User getUser() {
    return user;
  }

  public Chat getChat() {
    return chat;
  }

  public LocalDateTime getJoinedAt() {
    return joinedAt;
  }
}
