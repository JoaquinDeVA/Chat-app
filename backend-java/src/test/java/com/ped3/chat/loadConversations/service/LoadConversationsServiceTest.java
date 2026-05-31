package com.ped3.chat.loadConversations.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.loadConversations.controller.LoadConversationsController;
import com.ped3.chat.loadConversations.domain.LoadConversationsResponseDTO;
import com.ped3.chat.loadConversations.repository.LoadConversationsRepository;
import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Mensaje;
import com.ped3.chat.shared.domain.Usuario;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class LoadConversationsServiceTest {

    @Mock
    private LoadConversationsRepository repository;

    private final ObjectMapper mapper = new ObjectMapper();
    private LoadConversationsController app;

    @BeforeEach
    void setUp() {
        app = new LoadConversationsController(new LoadConversationsService(repository));
    }

    @Test
    void testLoadConversations_UserNotExists() throws Exception {
        when(repository.findUserByNombreUsuario("nonexistent")).thenReturn(Optional.empty());

        String jsonReq = """
            {
              "username": "nonexistent"
            }
            """;

        String jsonResp = app.loadConversations(jsonReq);

        LoadConversationsResponseDTO response = mapper.readValue(jsonResp, LoadConversationsResponseDTO.class);
        assertThat(response.getConversations()).isEmpty();
    }

    @Test
    void testLoadConversations_UserHasNoChats() throws Exception {
        Usuario user = new Usuario();
        user.setIdUsuario(1);
        user.setNombreUsuario("alice");

        when(repository.findUserByNombreUsuario("alice")).thenReturn(Optional.of(user));
        when(repository.findUserChats(1)).thenReturn(List.of());

        String jsonReq = """
            {
              "username": "alice"
            }
            """;

        String jsonResp = app.loadConversations(jsonReq);

        LoadConversationsResponseDTO response = mapper.readValue(jsonResp, LoadConversationsResponseDTO.class);
        assertThat(response.getConversations()).isEmpty();
    }

    @Test
    void testLoadConversations_UserHasConversations() throws Exception {
        Usuario alice = new Usuario();
        alice.setIdUsuario(1);
        alice.setNombreUsuario("alice");

        Usuario bob = new Usuario();
        bob.setIdUsuario(2);
        bob.setNombreUsuario("bob");

        Chat chat = new Chat();
        chat.setIdChat(1L);
        chat.setNombreChat("grupo-amigos");

        Mensaje msg = new Mensaje();
        msg.setIdMensaje(1);
        msg.setAutor(bob);
        msg.setContenido("Hola Alice!");
        msg.setFechaEnvio(LocalDateTime.of(2026, 5, 2, 10, 0, 0));

        when(repository.findUserByNombreUsuario("alice")).thenReturn(Optional.of(alice));
        when(repository.findUserChats(1)).thenReturn(List.of(chat));
        when(repository.findChatMessages(1L)).thenReturn(List.of(msg));

        String jsonReq = """
            {
              "username": "alice"
            }
            """;

        String jsonResp = app.loadConversations(jsonReq);

        LoadConversationsResponseDTO response = mapper.readValue(jsonResp, LoadConversationsResponseDTO.class);
        assertThat(response.getConversations()).containsKey("grupo-amigos");
        assertThat(response.getConversations().get("grupo-amigos")).hasSize(1);
        assertThat(response.getConversations().get("grupo-amigos").get(0).getChatname()).isEqualTo("grupo-amigos");
        assertThat(response.getConversations().get("grupo-amigos").get(0).getAuthor()).isEqualTo("bob");
        assertThat(response.getConversations().get("grupo-amigos").get(0).getContents()).isEqualTo("Hola Alice!");
    }
}
