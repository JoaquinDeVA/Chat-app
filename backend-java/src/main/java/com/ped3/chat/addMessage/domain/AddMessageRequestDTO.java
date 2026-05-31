package com.ped3.chat.addMessage.domain;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class AddMessageRequestDTO {
    private String username;
    private String chatname;
    private String message;
    private String date;

    public String getUsername() {
        return username;
    }

    public String getChatname() {
        return chatname;
    }

    public String getMessage() {
        return message;
    }

    public String getDate() {
        return date;
    }
}
