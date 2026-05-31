package com.ped3.chat.loadConversations.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.loadConversations.domain.LoadConversationsRequestDTO;
import com.ped3.chat.loadConversations.domain.LoadConversationsResponseDTO;
import com.ped3.chat.loadConversations.service.LoadConversationsService;

/**
 * Library replacement for REST controller.
 * Accepts JSON input and returns JSON output so external callers (e.g., JNI/Rust)
 * can interact without any Spring dependency.
 */
public class LoadConversationsController {
    
    private final LoadConversationsService loadConversationsService;
    private final ObjectMapper mapper = new ObjectMapper();

    public LoadConversationsController(LoadConversationsService loadConversationsService) {
        this.loadConversationsService = loadConversationsService;
    }

    public String loadConversations(String jsonInput) throws Exception {
    
        LoadConversationsRequestDTO request = mapper.readValue(jsonInput, LoadConversationsRequestDTO.class);
        LoadConversationsResponseDTO response = loadConversationsService.loadConversations(request.getUsername());

        return mapper.writeValueAsString(response);
    }
}
