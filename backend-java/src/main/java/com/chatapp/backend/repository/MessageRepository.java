package com.chatapp.backend.repository;

import com.chatapp.backend.domain.Chat;
import com.chatapp.backend.domain.Message;
import java.time.LocalDateTime;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

/** Persistence of {@link Message}. */
public interface MessageRepository extends JpaRepository<Message, Long> {

  /** Messages of a chat sent strictly after {@code since}, oldest first. */
  List<Message> findByChatAndSentAtAfterOrderBySentAtAscIdAsc(Chat chat, LocalDateTime since);
}
