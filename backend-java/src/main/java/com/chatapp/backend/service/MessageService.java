package com.chatapp.backend.service;

import com.chatapp.backend.domain.Chat;
import com.chatapp.backend.domain.Message;
import com.chatapp.backend.domain.User;
import com.chatapp.backend.protocol.Responses.MessageView;
import com.chatapp.backend.repository.ChatMemberRepository;
import com.chatapp.backend.repository.ChatRepository;
import com.chatapp.backend.repository.MessageRepository;
import com.chatapp.backend.repository.UserRepository;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Storing messages and reading the history of a user's chats. */
@Service
public class MessageService {

  /** Timestamp format of the protocol. */
  public static final DateTimeFormatter TIMESTAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

  private final MessageRepository messages;
  private final ChatRepository chats;
  private final ChatMemberRepository members;
  private final UserRepository users;

  public MessageService(
      MessageRepository messages,
      ChatRepository chats,
      ChatMemberRepository members,
      UserRepository users) {
    this.messages = messages;
    this.chats = chats;
    this.members = members;
    this.users = users;
  }

  /**
   * Stores a message.
   *
   * @param timestamp send time, {@code yyyy-MM-dd HH:mm:ss}
   * @return true if stored; false if the user or chat does not exist, the user is not a member of
   *     the chat, the content is empty or the timestamp is malformed
   */
  @Transactional
  public boolean addMessage(String username, String chatName, String content, String timestamp) {
    if (content == null || content.isEmpty() || username == null || chatName == null) {
      return false;
    }
    Optional<User> author = users.findByUsername(username);
    Optional<Chat> chat = chats.findByName(chatName);
    LocalDateTime sentAt = parse(timestamp);
    if (author.isEmpty() || chat.isEmpty() || sentAt == null) {
      return false;
    }
    if (!members.findUsersOf(chat.get()).contains(author.get())) {
      return false;
    }
    messages.save(new Message(chat.get(), author.get(), content, sentAt));
    return true;
  }

  /**
   * Messages sent after {@code since} in every chat the user belongs to.
   *
   * @return messages grouped by chat name, oldest first; chats without new messages appear with an
   *     empty list; empty map if the user does not exist or {@code since} is malformed
   */
  @Transactional(readOnly = true)
  public Map<String, List<MessageView>> conversationsSince(String username, String since) {
    Map<String, List<MessageView>> result = new LinkedHashMap<>();
    LocalDateTime sinceTime = parse(since);
    Optional<User> user = username == null ? Optional.empty() : users.findByUsername(username);
    if (user.isEmpty() || sinceTime == null) {
      return result;
    }
    for (Chat chat : members.findChatsOf(user.get())) {
      result.put(
          chat.getName(),
          messages.findByChatAndSentAtAfterOrderBySentAtAscIdAsc(chat, sinceTime).stream()
              .map(MessageService::toView)
              .toList());
    }
    return result;
  }

  private static MessageView toView(Message message) {
    return new MessageView(
        message.getChat().getName(),
        message.getAuthor().getUsername(),
        message.getContent(),
        message.getSentAt().format(TIMESTAMP));
  }

  private static LocalDateTime parse(String timestamp) {
    try {
      return timestamp == null ? null : LocalDateTime.parse(timestamp, TIMESTAMP);
    } catch (DateTimeParseException e) {
      return null;
    }
  }
}
