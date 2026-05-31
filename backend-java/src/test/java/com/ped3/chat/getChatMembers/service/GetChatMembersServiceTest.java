package com.ped3.chat.getChatMembers.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.getChatMembers.controller.GetChatMembersController;
import com.ped3.chat.getChatMembers.domain.GetChatMembersResponseDTO;
import com.ped3.chat.getChatMembers.repository.GetChatMembersRepository;
import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Usuario;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class GetChatMembersServiceTest {

    @Mock
    private GetChatMembersRepository repository;

    private final ObjectMapper mapper = new ObjectMapper();
    private GetChatMembersController app;

    @BeforeEach
    void setUp() {
        app = new GetChatMembersController(new GetChatMembersService(repository));
    }

    @Test
    void testGetChatMembers_ChatNotExists() throws Exception {
        when(repository.findByNombreChat("inexistente")).thenReturn(Optional.empty());

        String jsonReq = """
            {
              "chatname": "inexistente"
            }
            """;

        String jsonResp = app.getChatMembers(jsonReq);

        GetChatMembersResponseDTO response = mapper.readValue(jsonResp, GetChatMembersResponseDTO.class);
        assertThat(response.getMembers()).isEmpty();
    }

    @Test
    void testGetChatMembers_ChatExistsWithMembers() throws Exception {
        Chat chat = new Chat();
        chat.setIdChat(1L);
        chat.setNombreChat("grupo-amigos");

        Usuario alice = new Usuario();
        alice.setIdUsuario(1);
        alice.setNombreUsuario("alice");

        Usuario bob = new Usuario();
        bob.setIdUsuario(2);
        bob.setNombreUsuario("bob");

        when(repository.findByNombreChat("grupo-amigos")).thenReturn(Optional.of(chat));
        when(repository.findMembersByChatId(1L)).thenReturn(List.of(alice, bob));

        String jsonReq = """
            {
              "chatname": "grupo-amigos"
            }
            """;

        String jsonResp = app.getChatMembers(jsonReq);

        GetChatMembersResponseDTO response = mapper.readValue(jsonResp, GetChatMembersResponseDTO.class);
        assertThat(response.getMembers()).containsExactlyInAnyOrder("alice", "bob");
    }

    @Test
    void testGetChatMembers_ChatExistsNoMembers() throws Exception {
        Chat chat = new Chat();
        chat.setIdChat(2L);
        chat.setNombreChat("chat-vacio");

        when(repository.findByNombreChat("chat-vacio")).thenReturn(Optional.of(chat));
        when(repository.findMembersByChatId(2L)).thenReturn(List.of());

        String jsonReq = """
            {
              "chatname": "chat-vacio"
            }
            """;

        String jsonResp = app.getChatMembers(jsonReq);

        GetChatMembersResponseDTO response = mapper.readValue(jsonResp, GetChatMembersResponseDTO.class);
        assertThat(response.getMembers()).isEmpty();
    }
}
