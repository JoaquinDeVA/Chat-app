package com.ped3.chat.checkPassword.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.checkPassword.domain.CheckPasswordRequestDTO;
import com.ped3.chat.checkPassword.domain.CheckPasswordResponseDTO;
import com.ped3.chat.checkPassword.service.CheckPasswordService;

/**
 * Library replacement for the previous Spring controller.
 * Accepts JSON input and returns JSON output so external callers (e.g., JNI/Rust)
 * can interact without any Spring dependency.
 */
public class CheckPasswordController {
  private final CheckPasswordService checkPasswordService;
  private final ObjectMapper mapper = new ObjectMapper();

  public CheckPasswordController(CheckPasswordService checkPasswordService) {
    this.checkPasswordService = checkPasswordService;
  }

  public String checkPassword(String jsonInput) throws Exception {
    CheckPasswordRequestDTO request =
        mapper.readValue(jsonInput, CheckPasswordRequestDTO.class);

    CheckPasswordResponseDTO response =
        checkPasswordService.checkPassword(request.getUsername(), request.getPassword());

    return mapper.writeValueAsString(response);
  }
}
