package com.chatapp.backend.protocol;

import com.chatapp.backend.service.ChatService;
import com.chatapp.backend.service.MessageService;
import com.chatapp.backend.service.UserService;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Declares the requests of the protocol and the services that answer them.
 *
 * <p>Request names are the headers the Rust server writes before each JSON body.
 */
@Configuration
public class ProtocolConfig {

  @Bean
  ObjectMapper protocolObjectMapper() {
    return new ObjectMapper().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
  }

  @Bean
  RequestHandler authHandler(UserService users, ObjectMapper mapper) {
    return new JsonHandler<>(
        "AuthRequest",
        Requests.Auth.class,
        request -> new Responses.Authorized(users.authenticate(request.username(), request.password())),
        mapper);
  }

  @Bean
  RequestHandler addUserHandler(UserService users, ObjectMapper mapper) {
    return new JsonHandler<>(
        "AddUserRequest",
        Requests.AddUser.class,
        request -> new Responses.Processed(users.register(request.username(), request.password())),
        mapper);
  }

  @Bean
  RequestHandler createChatHandler(ChatService chats, ObjectMapper mapper) {
    return new JsonHandler<>(
        "CreateChatRequest",
        Requests.CreateChat.class,
        request -> new Responses.Processed(chats.createChat(request.chatname(), request.usernames())),
        mapper);
  }

  @Bean
  RequestHandler chatMembersHandler(ChatService chats, ObjectMapper mapper) {
    return new JsonHandler<>(
        "GetChatMembersRequest",
        Requests.ChatMembers.class,
        request -> new Responses.Members(chats.membersOf(request.chatname())),
        mapper);
  }

  @Bean
  RequestHandler sendMessageHandler(MessageService messages, ObjectMapper mapper) {
    return new JsonHandler<>(
        "SendMessageRequest",
        Requests.SendMessage.class,
        request ->
            new Responses.Processed(
                messages.addMessage(
                    request.username(), request.chatname(), request.message(), request.date())),
        mapper);
  }

  @Bean
  RequestHandler messageDeltaHandler(MessageService messages, ObjectMapper mapper) {
    return new JsonHandler<>(
        "LoadMessageDelta",
        Requests.MessageDelta.class,
        request ->
            new Responses.Conversations(
                messages.conversationsSince(request.username(), request.since())),
        mapper);
  }
}
