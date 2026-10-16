package com.chatapp.backend.service;

import com.chatapp.backend.domain.User;
import com.chatapp.backend.repository.UserRepository;
import com.chatapp.backend.security.PasswordHasher;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Registration and authentication of users. */
@Service
public class UserService {

  private static final Logger log = LoggerFactory.getLogger(UserService.class);

  private final UserRepository users;
  private final PasswordHasher passwordHasher;

  public UserService(UserRepository users, PasswordHasher passwordHasher) {
    this.users = users;
    this.passwordHasher = passwordHasher;
  }

  /**
   * Registers a user.
   *
   * @return true if created; false if the name or password is blank or the name is taken
   */
  @Transactional
  public boolean register(String username, String password) {
    if (isBlank(username) || isBlank(password) || users.findByUsername(username).isPresent()) {
      return false;
    }
    try {
      users.saveAndFlush(new User(username, passwordHasher.hash(password)));
      return true;
    } catch (DataIntegrityViolationException e) { // lost a race with a concurrent registration
      log.warn("Username '{}' was taken concurrently", username);
      return false;
    }
  }

  /** True if the user exists and {@code password} is correct. */
  @Transactional(readOnly = true)
  public boolean authenticate(String username, String password) {
    if (isBlank(username) || password == null) {
      return false;
    }
    return users
        .findByUsername(username)
        .map(user -> passwordHasher.matches(password, user.getPasswordHash()))
        .orElse(false);
  }

  private static boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
