package com.ped3.chat.addUser.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.addUser.domain.AddUserRequestDTO;
import com.ped3.chat.addUser.domain.AddUserResponseDTO;
import com.ped3.chat.addUser.service.AddUserService;

/**
 * Library replacement for REST controller.
 * Accepts JSON input and returns JSON output so external callers (e.g., JNI/Rust)
 * can interact without any Spring dependency.
 */
public class AddUserController {
  private final AddUserService addUserService;
  private final ObjectMapper mapper = new ObjectMapper();

  public AddUserController(AddUserService addUserService) {
    this.addUserService = addUserService;
  }

  public String addUser(String jsonInput) throws Exception {
    AddUserRequestDTO request =
        mapper.readValue(jsonInput, AddUserRequestDTO.class);

    AddUserResponseDTO response =
        addUserService.addUser(request.getUsername(), request.getPassword());

    return mapper.writeValueAsString(response);
  }
}
