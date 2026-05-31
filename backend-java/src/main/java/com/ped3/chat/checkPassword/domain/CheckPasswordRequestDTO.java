package com.ped3.chat.checkPassword.domain;

import lombok.Data;

@Data 
public class CheckPasswordRequestDTO {
    private String username;
    private String password;

    public String getUsername() {
        return username;
    }

    public String getPassword() {
        return password;
    }

    public CheckPasswordRequestDTO() {
    }

    public CheckPasswordRequestDTO(String username, String password) {
        this.username = username;
        this.password = password;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public void setPassword(String password) {
        this.password = password;
    }
}