package com.ped3.chat.addMessage.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.addMessage.domain.AddMessageRequestDTO;
import com.ped3.chat.addMessage.domain.AddMessageResponseDTO;
import com.ped3.chat.addMessage.service.AddMessageService;

/**
 * Library replacement for REST controller.
 * Accepts JSON input and returns JSON output so external callers (e.g., JNI/Rust)
 * can interact without any Spring dependency.
 */
public class AddMessageController {
  private final AddMessageService addMessageService;
  private final ObjectMapper mapper = new ObjectMapper();

  public AddMessageController(AddMessageService addMessageService) {
    this.addMessageService = addMessageService;
  }

  public String addMessage(String jsonInput) throws Exception {
    AddMessageRequestDTO request = mapper.readValue(jsonInput, AddMessageRequestDTO.class);
    AddMessageResponseDTO response = addMessageService.addMessage(request.getUsername(), request.getChatname(), request.getMessage(), request.getDate());
    return mapper.writeValueAsString(response);
  }
}
