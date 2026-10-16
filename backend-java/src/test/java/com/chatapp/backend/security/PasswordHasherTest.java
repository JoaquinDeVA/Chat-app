package com.chatapp.backend.security;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class PasswordHasherTest {

  private final PasswordHasher hasher = new PasswordHasher();

  @Test
  void hashIsNotThePasswordAndIsABcryptHash() {
    String hash = hasher.hash("secret");
    assertThat(hash).isNotEqualTo("secret").startsWith("$2").hasSize(60);
  }

  @Test
  void hashesAreSaltedSoTheyDiffer() {
    assertThat(hasher.hash("secret")).isNotEqualTo(hasher.hash("secret"));
  }

  @Test
  void matchesOnlyTheOriginalPassword() {
    String hash = hasher.hash("secret");
    assertThat(hasher.matches("secret", hash)).isTrue();
    assertThat(hasher.matches("Secret", hash)).isFalse();
    assertThat(hasher.matches("", hash)).isFalse();
  }

  @Test
  void nonAsciiPasswordsWork() {
    String password = "contraseña-密码-😀";
    assertThat(hasher.matches(password, hasher.hash(password))).isTrue();
  }

  @Test
  void aMissingOrLegacyHashNeverMatches() {
    assertThat(hasher.matches("secret", null)).isFalse();
    assertThat(hasher.matches("secret", "not-a-bcrypt-hash")).isFalse();
  }
}
