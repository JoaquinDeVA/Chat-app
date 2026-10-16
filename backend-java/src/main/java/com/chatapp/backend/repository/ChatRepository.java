package com.chatapp.backend.repository;

import com.chatapp.backend.domain.Chat;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

/** Persistence of {@link Chat}. */
public interface ChatRepository extends JpaRepository<Chat, Long> {

  Optional<Chat> findByName(String name);
}
