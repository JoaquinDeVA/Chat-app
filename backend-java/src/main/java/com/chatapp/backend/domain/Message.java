package com.chatapp.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/** A message written by a user in a chat. */
@Entity
@Table(name = "messages")
public class Message {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  private Long id;

  @ManyToOne(optional = false)
  @JoinColumn(name = "chat_id")
  private Chat chat;

  @ManyToOne(optional = false)
  @JoinColumn(name = "author_id")
  private User author;

  @Column(nullable = false, columnDefinition = "MEDIUMTEXT")
  private String content;

  @Column(name = "sent_at", nullable = false)
  private LocalDateTime sentAt;

  protected Message() {}

  public Message(Chat chat, User author, String content, LocalDateTime sentAt) {
    this.chat = chat;
    this.author = author;
    this.content = content;
    this.sentAt = sentAt;
  }

  public Long getId() {
    return id;
  }

  public Chat getChat() {
    return chat;
  }

  public User getAuthor() {
    return author;
  }

  public String getContent() {
    return content;
  }

  public LocalDateTime getSentAt() {
    return sentAt;
  }
}
