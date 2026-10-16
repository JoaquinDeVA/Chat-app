package com.chatapp.backend.repository;

import com.chatapp.backend.domain.User;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

/** Persistence of {@link User}. */
public interface UserRepository extends JpaRepository<User, Long> {

  Optional<User> findByUsername(String username);
}
