package com.chatapp.backend.service;

import com.chatapp.backend.domain.Chat;
import com.chatapp.backend.domain.ChatMember;
import com.chatapp.backend.domain.User;
import com.chatapp.backend.repository.ChatMemberRepository;
import com.chatapp.backend.repository.ChatRepository;
import com.chatapp.backend.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Creation of chats and lookup of their members. */
@Service
public class ChatService {

  private final ChatRepository chats;
  private final ChatMemberRepository members;
  private final UserRepository users;

  public ChatService(ChatRepository chats, ChatMemberRepository members, UserRepository users) {
    this.chats = chats;
    this.members = members;
    this.users = users;
  }

  /**
   * Creates a chat and adds the given users to it.
   *
   * <p>Blank and repeated usernames are ignored. Nothing is created if the name is blank or
   * taken, if no valid username remains, or if any username does not exist.
   *
   * @return true if the chat was created
   */
  @Transactional
  public boolean createChat(String chatName, List<String> usernames) {
    if (chatName == null || chatName.isBlank() || usernames == null) {
      return false;
    }
    List<String> distinct =
        usernames.stream().filter(name -> name != null && !name.isBlank()).distinct().toList();
    if (distinct.isEmpty() || chats.findByName(chatName).isPresent()) {
      return false;
    }

    List<User> participants = new ArrayList<>();
    for (String username : distinct) {
      Optional<User> user = users.findByUsername(username);
      if (user.isEmpty()) {
        return false;
      }
      participants.add(user.get());
    }

    Chat chat = chats.save(new Chat(chatName));
    LocalDateTime now = LocalDateTime.now();
    members.saveAll(participants.stream().map(user -> new ChatMember(user, chat, now)).toList());
    return true;
  }

  /** Usernames of the chat's members; empty if the chat does not exist. */
  @Transactional(readOnly = true)
  public List<String> membersOf(String chatName) {
    if (chatName == null || chatName.isBlank()) {
      return List.of();
    }
    return chats
        .findByName(chatName)
        .map(chat -> members.findUsersOf(chat).stream().map(User::getUsername).toList())
        .orElse(List.of());
  }
}
