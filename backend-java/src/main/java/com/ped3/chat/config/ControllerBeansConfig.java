package com.ped3.chat.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.ped3.chat.addChat.controller.AddChatController;
import com.ped3.chat.addChat.repository.AddChatParticipanteRepository;
import com.ped3.chat.addChat.repository.AddChatRepository;
import com.ped3.chat.addChat.service.AddChatService;
import com.ped3.chat.addMessage.controller.AddMessageController;
import com.ped3.chat.addMessage.repository.AddMessageRepository;
import com.ped3.chat.addMessage.service.AddMessageService;
import com.ped3.chat.addUser.controller.AddUserController;
import com.ped3.chat.addUser.repository.AddUserRepository;
import com.ped3.chat.addUser.service.AddUserService;
import com.ped3.chat.checkPassword.controller.CheckPasswordController;
import com.ped3.chat.checkPassword.repository.CheckPasswordUsuarioRepository;
import com.ped3.chat.checkPassword.service.CheckPasswordService;
import com.ped3.chat.getChatMembers.controller.GetChatMembersController;
import com.ped3.chat.getChatMembers.repository.GetChatMembersRepository;
import com.ped3.chat.getChatMembers.service.GetChatMembersService;
import com.ped3.chat.loadConversations.controller.LoadConversationsController;
import com.ped3.chat.loadConversations.repository.LoadConversationsRepository;
import com.ped3.chat.loadConversations.service.LoadConversationsService;
import com.ped3.chat.loadMessageDelta.controller.LoadMessageDeltaController;
import com.ped3.chat.loadMessageDelta.repository.LoadMessageDeltaRepository;
import com.ped3.chat.loadMessageDelta.service.LoadMessageDeltaService;

@Configuration
public class ControllerBeansConfig {

  @Bean
  public CheckPasswordService checkPasswordService(CheckPasswordUsuarioRepository repository) {
    return new CheckPasswordService(repository);
  }

  @Bean
  public AddUserService addUserService(AddUserRepository repository) {
    return new AddUserService(repository);
  }

  @Bean
  public AddChatService addChatService(AddChatRepository chatRepository, AddChatParticipanteRepository participanteRepository) {
    return new AddChatService(chatRepository, participanteRepository);
  }

  @Bean
  public AddMessageService addMessageService(AddMessageRepository repository) {
    return new AddMessageService(repository);
  }

  @Bean
  public LoadConversationsService loadConversationsService(LoadConversationsRepository repository) {
    return new LoadConversationsService(repository);
  }

  @Bean
  public GetChatMembersService getChatMembersService(GetChatMembersRepository repository) {
    return new GetChatMembersService(repository);
  }

  @Bean
  public LoadMessageDeltaService loadMessageDeltaService(LoadMessageDeltaRepository repository) {
    return new LoadMessageDeltaService(repository);
  }

  @Bean
  public CheckPasswordController checkPasswordController(CheckPasswordService checkPasswordService) {
    return new CheckPasswordController(checkPasswordService);
  }

  @Bean
  public AddUserController addUserController(AddUserService addUserService) {
    return new AddUserController(addUserService);
  }

  @Bean
  public AddChatController addChatController(AddChatService addChatService) {
    return new AddChatController(addChatService);
  }

  @Bean
  public AddMessageController addMessageController(AddMessageService addMessageService) {
    return new AddMessageController(addMessageService);
  }

  @Bean
  public LoadConversationsController loadConversationsController(LoadConversationsService loadConversationsService) {
    return new LoadConversationsController(loadConversationsService);
  }

  @Bean
  public GetChatMembersController getChatMembersController(GetChatMembersService getChatMembersService) {
    return new GetChatMembersController(getChatMembersService);
  }

  @Bean
  public LoadMessageDeltaController loadMessageDeltaController(LoadMessageDeltaService loadMessageDeltaService) {
    return new LoadMessageDeltaController(loadMessageDeltaService);
  }
}
