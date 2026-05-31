package com.ped3.chat.getChatMembers.domain;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class GetChatMembersRequestDTO {
    private String chatname;

    public String getChatname() {
        return chatname;
    }
}
