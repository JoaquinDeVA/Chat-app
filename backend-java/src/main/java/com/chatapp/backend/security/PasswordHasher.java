package com.chatapp.backend.security;

import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/** Hashes and verifies passwords with BCrypt (salted, deliberately slow, not reversible). */
@Component
public class PasswordHasher {

  private final PasswordEncoder encoder;

  public PasswordHasher() {
    this(new BCryptPasswordEncoder());
  }

  public PasswordHasher(PasswordEncoder encoder) {
    this.encoder = encoder;
  }

  /** Returns the BCrypt hash of {@code plainPassword}; two calls give different hashes (salt). */
  public String hash(String plainPassword) {
    return encoder.encode(plainPassword);
  }

  /** True if {@code plainPassword} produced {@code storedHash}. */
  public boolean matches(String plainPassword, String storedHash) {
    return storedHash != null && encoder.matches(plainPassword, storedHash);
  }
}
