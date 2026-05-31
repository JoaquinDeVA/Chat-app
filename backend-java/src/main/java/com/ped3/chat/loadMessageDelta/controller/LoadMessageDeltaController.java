package com.ped3.chat.loadMessageDelta.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.loadMessageDelta.domain.LoadMessageDeltaRequestDTO;
import com.ped3.chat.loadMessageDelta.domain.LoadMessageDeltaResponseDTO;
import com.ped3.chat.loadMessageDelta.service.LoadMessageDeltaService;

public class LoadMessageDeltaController {

    private final LoadMessageDeltaService loadMessageDeltaService;
    private final ObjectMapper mapper = new ObjectMapper();

    public LoadMessageDeltaController(LoadMessageDeltaService loadMessageDeltaService) {
        this.loadMessageDeltaService = loadMessageDeltaService;
    }

    public String loadMessageDelta(String jsonInput) throws Exception {
        LoadMessageDeltaRequestDTO request = mapper.readValue(jsonInput, LoadMessageDeltaRequestDTO.class);
        LoadMessageDeltaResponseDTO response = loadMessageDeltaService.loadMessageDelta(
                request.getUsername(), request.getSince());
        return mapper.writeValueAsString(response);
    }
}
