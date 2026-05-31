package com.ped3.chat.getChatMembers.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.getChatMembers.domain.GetChatMembersRequestDTO;
import com.ped3.chat.getChatMembers.domain.GetChatMembersResponseDTO;
import com.ped3.chat.getChatMembers.service.GetChatMembersService;

public class GetChatMembersController {
    private final GetChatMembersService getChatMembersService;
    private final ObjectMapper mapper = new ObjectMapper();

    public GetChatMembersController(GetChatMembersService getChatMembersService) {
        this.getChatMembersService = getChatMembersService;
    }

    public String getChatMembers(String jsonInput) throws Exception {
        GetChatMembersRequestDTO request = mapper.readValue(jsonInput, GetChatMembersRequestDTO.class);
        GetChatMembersResponseDTO response = getChatMembersService.getChatMembers(request.getChatname());
        return mapper.writeValueAsString(response);
    }
}
