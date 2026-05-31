package com.ped3.chat.loadConversations.domain;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class LoadConversationsRequestDTO {
    private String username;

    public String getUsername() {
        return username;
    }
}
