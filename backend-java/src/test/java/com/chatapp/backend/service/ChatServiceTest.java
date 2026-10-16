package com.chatapp.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.chatapp.backend.domain.Chat;
import com.chatapp.backend.domain.ChatMember;
import com.chatapp.backend.domain.User;
import com.chatapp.backend.repository.ChatMemberRepository;
import com.chatapp.backend.repository.ChatRepository;
import com.chatapp.backend.repository.UserRepository;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ChatServiceTest {

  @Mock ChatRepository chats;
  @Mock ChatMemberRepository members;
  @Mock UserRepository users;
  ChatService service;

  final User ana = new User("ana", "h");
  final User ben = new User("ben", "h");

  @BeforeEach
  void setUp() {
    service = new ChatService(chats, members, users);
  }

  private void knownUsers() {
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(users.findByUsername("ben")).thenReturn(Optional.of(ben));
  }

  @Test
  @SuppressWarnings("unchecked")
  void createChatStoresTheChatAndOneMembershipPerDistinctUser() {
    knownUsers();
    when(chats.findByName("team")).thenReturn(Optional.empty());
    when(chats.save(any())).thenAnswer(call -> call.getArgument(0));

    assertThat(service.createChat("team", Arrays.asList("ana", "ben", "ana", "", null))).isTrue();

    ArgumentCaptor<List<ChatMember>> saved = ArgumentCaptor.forClass(List.class);
    verify(members).saveAll(saved.capture());
    assertThat(saved.getValue()).extracting(member -> member.getUser().getUsername()).containsExactly("ana", "ben");
    assertThat(saved.getValue()).allSatisfy(member -> assertThat(member.getChat().getName()).isEqualTo("team"));
  }

  @Test
  void createChatRejectsADuplicateName() {
    when(chats.findByName("team")).thenReturn(Optional.of(new Chat("team")));
    assertThat(service.createChat("team", List.of("ana"))).isFalse();
    verify(chats, never()).save(any());
  }

  @Test
  void createChatCreatesNothingIfAUserDoesNotExist() {
    when(chats.findByName("team")).thenReturn(Optional.empty());
    when(users.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(users.findByUsername("ghost")).thenReturn(Optional.empty());

    assertThat(service.createChat("team", List.of("ana", "ghost"))).isFalse();
    verify(chats, never()).save(any());
    verify(members, never()).saveAll(any());
  }

  @Test
  void createChatRejectsInvalidArguments() {
    assertThat(service.createChat(null, List.of("ana"))).isFalse();
    assertThat(service.createChat("  ", List.of("ana"))).isFalse();
    assertThat(service.createChat("team", null)).isFalse();
    assertThat(service.createChat("team", List.of())).isFalse();
    assertThat(service.createChat("team", Arrays.asList("", null))).isFalse();
    verify(chats, never()).save(any());
  }

  @Test
  void membersOfListsTheUsernames() {
    Chat chat = new Chat("team");
    when(chats.findByName("team")).thenReturn(Optional.of(chat));
    when(members.findUsersOf(chat)).thenReturn(List.of(ana, ben));
    assertThat(service.membersOf("team")).containsExactly("ana", "ben");
  }

  @Test
  void membersOfAnUnknownOrBlankChatIsEmpty() {
    when(chats.findByName("nope")).thenReturn(Optional.empty());
    assertThat(service.membersOf("nope")).isEmpty();
    assertThat(service.membersOf(" ")).isEmpty();
    assertThat(service.membersOf(null)).isEmpty();
  }
}
