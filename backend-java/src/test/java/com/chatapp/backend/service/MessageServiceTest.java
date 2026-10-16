package com.chatapp.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.chatapp.backend.domain.Chat;
import com.chatapp.backend.domain.Message;
import com.chatapp.backend.domain.User;
import com.chatapp.backend.protocol.Responses.MessageView;
import com.chatapp.backend.repository.ChatMemberRepository;
import com.chatapp.backend.repository.ChatRepository;
import com.chatapp.backend.repository.MessageRepository;
import com.chatapp.backend.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class MessageServiceTest {

  @Mock MessageRepository messages;
  @Mock ChatRepository chats;
  @Mock ChatMemberRepository members;
  @Mock UserRepository users;
  MessageService service;

  final User ana = new User("ana", "h");
  final Chat team = new Chat("team");

  @BeforeEach
  void setUp() {
    service = new MessageService(messages, chats, members, users);
  }

  private void anaInTeam() {
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(chats.findByName("team")).thenReturn(Optional.of(team));
    when(members.findUsersOf(team)).thenReturn(List.of(ana));
  }

  @Test
  void addMessageStoresTheContentWithTheGivenTimestamp() {
    anaInTeam();
    assertThat(service.addMessage("ana", "team", "héllo 😀", "2026-05-04 10:30:00")).isTrue();

    ArgumentCaptor<Message> saved = ArgumentCaptor.forClass(Message.class);
    verify(messages).save(saved.capture());
    assertThat(saved.getValue().getContent()).isEqualTo("héllo 😀");
    assertThat(saved.getValue().getSentAt()).isEqualTo(LocalDateTime.of(2026, 5, 4, 10, 30, 0));
    assertThat(saved.getValue().getAuthor()).isSameAs(ana);
  }

  @Test
  void addMessageRequiresMembershipOfTheChat() {
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(chats.findByName("team")).thenReturn(Optional.of(team));
    when(members.findUsersOf(team)).thenReturn(List.of(new User("ben", "h")));

    assertThat(service.addMessage("ana", "team", "hi", "2026-05-04 10:30:00")).isFalse();
    verify(messages, never()).save(any());
  }

  @Test
  void addMessageRejectsAnUnknownUser() {
    when(users.findByUsername("ghost")).thenReturn(Optional.empty());
    when(chats.findByName("team")).thenReturn(Optional.of(team));
    assertThat(service.addMessage("ghost", "team", "hi", "2026-05-04 10:30:00")).isFalse();
    verify(messages, never()).save(any());
  }

  @Test
  void addMessageRejectsAnUnknownChat() {
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(chats.findByName("nope")).thenReturn(Optional.empty());
    assertThat(service.addMessage("ana", "nope", "hi", "2026-05-04 10:30:00")).isFalse();
    verify(messages, never()).save(any());
  }

  @Test
  void addMessageRejectsEmptyContent() {
    assertThat(service.addMessage("ana", "team", "", "2026-05-04 10:30:00")).isFalse();
    assertThat(service.addMessage("ana", "team", null, "2026-05-04 10:30:00")).isFalse();
    verify(messages, never()).save(any());
  }

  @Test
  void addMessageRejectsAMalformedTimestamp() {
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(chats.findByName("team")).thenReturn(Optional.of(team));
    assertThat(service.addMessage("ana", "team", "hi", "yesterday")).isFalse();
    assertThat(service.addMessage("ana", "team", "hi", null)).isFalse();
    verify(messages, never()).save(any());
  }

  @Test
  void conversationsSinceGroupsMessagesByChatIncludingEmptyOnes() {
    Chat quiet = new Chat("quiet");
    LocalDateTime since = LocalDateTime.of(2026, 5, 4, 10, 0, 0);
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(members.findChatsOf(ana)).thenReturn(List.of(team, quiet));
    when(messages.findByChatAndSentAtAfterOrderBySentAtAscIdAsc(team, since))
        .thenReturn(List.of(new Message(team, ana, "hi", LocalDateTime.of(2026, 5, 4, 10, 30, 5))));
    when(messages.findByChatAndSentAtAfterOrderBySentAtAscIdAsc(quiet, since)).thenReturn(List.of());

    Map<String, List<MessageView>> result = service.conversationsSince("ana", "2026-05-04 10:00:00");

    assertThat(result).containsOnlyKeys("team", "quiet");
    assertThat(result.get("team")).containsExactly(new MessageView("team", "ana", "hi", "2026-05-04 10:30:05"));
    assertThat(result.get("quiet")).isEmpty();
  }

  @Test
  void conversationsSinceIsEmptyForUnknownUsersOrBadDates() {
    when(users.findByUsername("ghost")).thenReturn(Optional.empty());
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    assertThat(service.conversationsSince("ghost", "2026-05-04 10:00:00")).isEmpty();
    assertThat(service.conversationsSince("ana", "nonsense")).isEmpty();
    assertThat(service.conversationsSince(null, "2026-05-04 10:00:00")).isEmpty();
  }
}
