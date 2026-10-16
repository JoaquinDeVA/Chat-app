package com.chatapp.backend.repository;

import com.chatapp.backend.domain.Chat;
import com.chatapp.backend.domain.ChatMember;
import com.chatapp.backend.domain.ChatMemberId;
import com.chatapp.backend.domain.User;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/** Persistence of {@link ChatMember}. */
public interface ChatMemberRepository extends JpaRepository<ChatMember, ChatMemberId> {

  /** Chats the user belongs to, in creation order. */
  @Query("SELECT m.chat FROM ChatMember m WHERE m.user = :user ORDER BY m.chat.id")
  List<Chat> findChatsOf(@Param("user") User user);

  /** Users that belong to the chat, in joining order. */
  @Query("SELECT m.user FROM ChatMember m WHERE m.chat = :chat ORDER BY m.joinedAt, m.user.id")
  List<User> findUsersOf(@Param("chat") Chat chat);
}
