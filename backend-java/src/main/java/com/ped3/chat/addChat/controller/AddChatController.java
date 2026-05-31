package com.ped3.chat.addChat.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.addChat.domain.AddChatRequestDTO;
import com.ped3.chat.addChat.domain.AddChatResponseDTO;
import com.ped3.chat.addChat.service.AddChatService;

public class AddChatController {
  private final AddChatService addChatService;
  private final ObjectMapper mapper = new ObjectMapper();

  public AddChatController(AddChatService addChatService) {
    this.addChatService = addChatService;
  }

  public String addChat(String jsonInput) throws Exception {
    AddChatRequestDTO request = mapper.readValue(jsonInput, AddChatRequestDTO.class);
    AddChatResponseDTO response = addChatService.addChat(request.getChatname(), request.getUsernames());
    return mapper.writeValueAsString(response);
  }
}