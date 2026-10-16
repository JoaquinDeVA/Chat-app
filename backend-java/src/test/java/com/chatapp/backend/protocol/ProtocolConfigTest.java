package com.chatapp.backend.protocol;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.chatapp.backend.domain.Chat;
import com.chatapp.backend.domain.Message;
import com.chatapp.backend.domain.User;
import com.chatapp.backend.repository.ChatMemberRepository;
import com.chatapp.backend.repository.ChatRepository;
import com.chatapp.backend.repository.MessageRepository;
import com.chatapp.backend.repository.UserRepository;
import com.chatapp.backend.security.PasswordHasher;
import com.chatapp.backend.service.ChatService;
import com.chatapp.backend.service.MessageService;
import com.chatapp.backend.service.UserService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** The wire format, end to end through the dispatcher, with real services over mocked repositories. */
class ProtocolConfigTest {

  UserRepository userRepository = mock(UserRepository.class);
  ChatRepository chatRepository = mock(ChatRepository.class);
  ChatMemberRepository memberRepository = mock(ChatMemberRepository.class);
  MessageRepository messageRepository = mock(MessageRepository.class);
  PasswordHasher hasher = new PasswordHasher();
  RequestDispatcher dispatcher;

  User ana = new User("ana", hasher.hash("secret"));
  User ben = new User("ben", hasher.hash("x"));
  Chat team = new Chat("team");

  @BeforeEach
  void setUp() {
    UserService users = new UserService(userRepository, hasher);
    ChatService chats = new ChatService(chatRepository, memberRepository, userRepository);
    MessageService messages =
        new MessageService(messageRepository, chatRepository, memberRepository, userRepository);
    ProtocolConfig config = new ProtocolConfig();
    ObjectMapper mapper = config.protocolObjectMapper();
    dispatcher =
        new RequestDispatcher(
            List.of(
                config.authHandler(users, mapper),
                config.addUserHandler(users, mapper),
                config.createChatHandler(chats, mapper),
                config.chatMembersHandler(chats, mapper),
                config.sendMessageHandler(messages, mapper),
                config.messageDeltaHandler(messages, mapper)),
            mapper);
    when(userRepository.findByUsername("ana")).thenReturn(Optional.of(ana));
    when(userRepository.findByUsername("ben")).thenReturn(Optional.of(ben));
    when(chatRepository.findByName("team")).thenReturn(Optional.of(team));
  }

  @Test
  void authRequest() {
    assertThat(dispatcher.dispatch("AuthRequest{\"username\":\"ana\",\"password\":\"secret\"}"))
        .isEqualTo("{\"authorized\":true}");
    assertThat(dispatcher.dispatch("AuthRequest{\"username\":\"ana\",\"password\":\"nope\"}"))
        .isEqualTo("{\"authorized\":false}");
  }

  @Test
  void addUserRequestWithPrettyPrintedJsonAndUnknownFields() {
    when(userRepository.findByUsername("eve")).thenReturn(Optional.empty());
    String request = "AddUserRequest{\n  \"username\" : \"eve\",\n  \"password\" : \"pw\",\n  \"extra\" : 1\n}";
    assertThat(dispatcher.dispatch(request)).isEqualTo("{\"processed\":true}");
    assertThat(dispatcher.dispatch("AddUserRequest{\"username\":\"ana\",\"password\":\"pw\"}"))
        .as("existing user")
        .isEqualTo("{\"processed\":false}");
  }

  @Test
  void createChatRequest() {
    when(chatRepository.findByName("new")).thenReturn(Optional.empty());
    when(chatRepository.save(any())).thenAnswer(call -> call.getArgument(0));
    assertThat(dispatcher.dispatch("CreateChatRequest{\"chatname\":\"new\",\"usernames\":[\"ana\",\"ben\"]}"))
        .isEqualTo("{\"processed\":true}");
    assertThat(dispatcher.dispatch("CreateChatRequest{\"chatname\":\"team\",\"usernames\":[\"ana\"]}"))
        .as("existing chat name")
        .isEqualTo("{\"processed\":false}");
  }

  @Test
  void getChatMembersRequestIsCaseInsensitive() {
    when(memberRepository.findUsersOf(team)).thenReturn(List.of(ana, ben));
    assertThat(dispatcher.dispatch("GETCHATMEMBERSREQUEST{\"chatname\":\"team\"}"))
        .isEqualTo("{\"members\":[\"ana\",\"ben\"]}");
  }

  @Test
  void sendMessageRequestKeepsUnicode() {
    when(memberRepository.findUsersOf(team)).thenReturn(List.of(ana));
    assertThat(
            dispatcher.dispatch(
                "SendMessageRequest{\"username\":\"ana\",\"chatname\":\"team\","
                    + "\"message\":\"hola ñ 😀\",\"date\":\"2026-05-04 10:30:00\"}"))
        .isEqualTo("{\"processed\":true}");
    verify(messageRepository).save(argThat(message -> message.getContent().equals("hola ñ 😀")));
  }

  @Test
  void loadMessageDeltaRequest() {
    Chat quiet = new Chat("quiet");
    LocalDateTime since = LocalDateTime.of(2026, 5, 4, 10, 0, 0);
    when(memberRepository.findChatsOf(ana)).thenReturn(List.of(team, quiet));
    when(messageRepository.findByChatAndSentAtAfterOrderBySentAtAscIdAsc(team, since))
        .thenReturn(List.of(new Message(team, ana, "hi", LocalDateTime.of(2026, 5, 4, 10, 30, 5))));
    when(messageRepository.findByChatAndSentAtAfterOrderBySentAtAscIdAsc(quiet, since)).thenReturn(List.of());

    assertThat(dispatcher.dispatch("LOADMESSAGEDELTA{\"username\":\"ana\",\"since\":\"2026-05-04 10:00:00\"}"))
        .isEqualTo(
            "{\"conversations\":{\"team\":[{\"chatname\":\"team\",\"author\":\"ana\","
                + "\"contents\":\"hi\",\"sent\":\"2026-05-04 10:30:05\"}],\"quiet\":[]}}");
  }

  @Test
  void missingFieldsAreTreatedAsNull() {
    assertThat(dispatcher.dispatch("AuthRequest{}")).isEqualTo("{\"authorized\":false}");
  }
}
