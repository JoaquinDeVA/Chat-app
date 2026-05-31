package com.ped3.chat.loadConversations.domain;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class LoadConversationsResponseDTO {
    private Map<String, List<MessageDTO>> conversations = new HashMap<>();

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class MessageDTO {
        private String chatname;
        private String author;
        private String contents;
        private String sent;

        public String getChatname() { return chatname; }
        public void setChatname(String chatname) { this.chatname = chatname; }
        public String getAuthor() { return author; }
        public void setAuthor(String author) { this.author = author; }
        public String getContents() { return contents; }
        public void setContents(String contents) { this.contents = contents; }
        public String getSent() { return sent; }
        public void setSent(String sent) { this.sent = sent; }
    }

    public Map<String, List<MessageDTO>> getConversations() { return conversations; }
    public void setConversations(Map<String, List<MessageDTO>> conversations) { this.conversations = conversations; }
}
