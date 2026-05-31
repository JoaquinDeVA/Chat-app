package com.ped3.chat.addChat.domain;

import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class AddChatRequestDTO {
    private String chatname;
    private List<String> usernames;

    public String getChatname() {
        return chatname;
    }

    public List<String> getUsernames() {
        return usernames;
    }
}