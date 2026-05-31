package com.ped3.chat.checkPassword.domain;

import lombok.Data;

@Data
public class CheckPasswordResponseDTO {
    
    private boolean authorized;

    public CheckPasswordResponseDTO() {
    }

    public CheckPasswordResponseDTO(boolean authorized) {
        this.authorized = authorized;
    }

    public boolean isAuthorized() {
        return authorized;
    }
}