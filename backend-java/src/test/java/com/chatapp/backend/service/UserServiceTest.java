package com.chatapp.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.chatapp.backend.domain.User;
import com.chatapp.backend.repository.UserRepository;
import com.chatapp.backend.security.PasswordHasher;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

  @Mock UserRepository users;
  final PasswordHasher hasher = new PasswordHasher();
  UserService service;

  @BeforeEach
  void setUp() {
    service = new UserService(users, hasher);
  }

  @Test
  void registerStoresAHashNeverThePlainPassword() {
    when(users.findByUsername("ana")).thenReturn(Optional.empty());

    assertThat(service.register("ana", "secret")).isTrue();

    ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
    verify(users).saveAndFlush(saved.capture());
    assertThat(saved.getValue().getUsername()).isEqualTo("ana");
    assertThat(saved.getValue().getPasswordHash()).isNotEqualTo("secret");
    assertThat(hasher.matches("secret", saved.getValue().getPasswordHash())).isTrue();
  }

  @Test
  void registerRejectsAnExistingUsername() {
    when(users.findByUsername("ana")).thenReturn(Optional.of(new User("ana", "hash")));
    assertThat(service.register("ana", "secret")).isFalse();
    verify(users, never()).saveAndFlush(any());
  }

  @Test
  void registerRejectsBlankValues() {
    assertThat(service.register("", "secret")).isFalse();
    assertThat(service.register("  ", "secret")).isFalse();
    assertThat(service.register(null, "secret")).isFalse();
    assertThat(service.register("ana", "")).isFalse();
    assertThat(service.register("ana", null)).isFalse();
    verify(users, never()).saveAndFlush(any());
  }

  @Test
  void registerHandlesALostRaceOnTheUniqueConstraint() {
    when(users.findByUsername("ana")).thenReturn(Optional.empty());
    when(users.saveAndFlush(any())).thenThrow(new DataIntegrityViolationException("duplicate"));
    assertThat(service.register("ana", "secret")).isFalse();
  }

  @Test
  void authenticateAcceptsTheRightPasswordOnly() {
    when(users.findByUsername("ana")).thenReturn(Optional.of(new User("ana", hasher.hash("secret"))));
    assertThat(service.authenticate("ana", "secret")).isTrue();
    assertThat(service.authenticate("ana", "wrong")).isFalse();
  }

  @Test
  void authenticateRejectsUnknownUsersAndMissingValues() {
    when(users.findByUsername("ghost")).thenReturn(Optional.empty());
    assertThat(service.authenticate("ghost", "secret")).isFalse();
    assertThat(service.authenticate(null, "secret")).isFalse();
    assertThat(service.authenticate("ana", null)).isFalse();
  }
}
