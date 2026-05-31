package com.ped3.chat.loadMessageDelta.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.loadMessageDelta.controller.LoadMessageDeltaController;
import com.ped3.chat.loadMessageDelta.domain.LoadMessageDeltaResponseDTO;
import com.ped3.chat.loadMessageDelta.domain.LoadMessageDeltaResponseDTO.MessageDTO;
import com.ped3.chat.loadMessageDelta.repository.LoadMessageDeltaRepository;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class LoadMessageDeltaServiceTest {

    @Mock
    private LoadMessageDeltaRepository repository;

    private final ObjectMapper mapper = new ObjectMapper();
    private LoadMessageDeltaController app;

    private Usuario alice;
    private Usuario bob;
    private Chat chat;

    @BeforeEach
    void setUp() {
        app = new LoadMessageDeltaController(new LoadMessageDeltaService(repository));

        alice = new Usuario();
        alice.setIdUsuario(1);
        alice.setNombreUsuario("alice");

        bob = new Usuario();
        bob.setIdUsuario(2);
        bob.setNombreUsuario("bob");

        chat = new Chat();
        chat.setIdChat(10L);
        chat.setNombreChat("grupo-test");
    }

    private Mensaje mensaje(int id, Usuario autor, String contenido, LocalDateTime fecha) {
        Mensaje m = new Mensaje();
        m.setIdMensaje(id);
        m.setAutor(autor);
        m.setContenido(contenido);
        m.setFechaEnvio(fecha);
        return m;
    }

    private String request(String username, String since) {
        return String.format("{\"username\":\"%s\",\"since\":\"%s\"}", username, since);
    }

    // ── user not found ────────────────────────────────────────────────────────

    @Test
    void returnsEmptyWhenUserNotFound() throws Exception {
        when(repository.findUserByNombreUsuario("ghost")).thenReturn(Optional.empty());

        String json = app.loadMessageDelta(request("ghost", "2026-01-01 00:00:00"));

        LoadMessageDeltaResponseDTO resp = mapper.readValue(json, LoadMessageDeltaResponseDTO.class);
        assertThat(resp.getConversations()).isEmpty();
    }

    // ── no messages after the cutoff ─────────────────────────────────────────

    @Test
    void returnsEmptyChatWhenAllMessagesAreBeforeSince() throws Exception {
        LocalDateTime since = LocalDateTime.of(2026, 5, 10, 12, 0, 0);

        when(repository.findUserByNombreUsuario("alice")).thenReturn(Optional.of(alice));
        when(repository.findChatsByUserId(1)).thenReturn(List.of(chat));
        // repository returns nothing for the chat because the query uses > since
        when(repository.findMessagesSince(eq(10L), any(LocalDateTime.class))).thenReturn(List.of());

        String json = app.loadMessageDelta(request("alice", "2026-05-10 12:00:00"));

        LoadMessageDeltaResponseDTO resp = mapper.readValue(json, LoadMessageDeltaResponseDTO.class);
        assertThat(resp.getConversations()).containsKey("grupo-test");
        assertThat(resp.getConversations().get("grupo-test")).isEmpty();
    }

    // ── only messages strictly after since are returned ───────────────────────

    @Test
    void returnsOnlyMessagesAfterSince() throws Exception {
        LocalDateTime since = LocalDateTime.of(2026, 5, 11, 9, 0, 0);
        LocalDateTime before = since.minusSeconds(1);   // 08:59:59 — must NOT be returned
        LocalDateTime exact  = since;                   // 09:00:00 — must NOT be returned (> not >=)
        LocalDateTime after  = since.plusSeconds(1);    // 09:00:01 — must be returned

        Mensaje old    = mensaje(1, bob, "mensaje antiguo",  before);
        Mensaje border = mensaje(2, bob, "mensaje borde",    exact);
        Mensaje fresh  = mensaje(3, bob, "mensaje nuevo",    after);

        when(repository.findUserByNombreUsuario("alice")).thenReturn(Optional.of(alice));
        when(repository.findChatsByUserId(1)).thenReturn(List.of(chat));
        // The real query is `fecha_envio > :since`, so the repo already filters;
        // we simulate that by returning only `fresh`.
        when(repository.findMessagesSince(eq(10L), eq(since))).thenReturn(List.of(fresh));

        String json = app.loadMessageDelta(request("alice", "2026-05-11 09:00:00"));

        LoadMessageDeltaResponseDTO resp = mapper.readValue(json, LoadMessageDeltaResponseDTO.class);
        List<MessageDTO> msgs = resp.getConversations().get("grupo-test");
        assertThat(msgs).hasSize(1);
        assertThat(msgs.get(0).getContents()).isEqualTo("mensaje nuevo");
        assertThat(msgs.get(0).getSent()).isEqualTo("2026-05-11 09:00:01");
        assertThat(msgs.get(0).getAuthor()).isEqualTo("bob");
        assertThat(msgs.get(0).getChatname()).isEqualTo("grupo-test");
    }

    // ── multiple messages from multiple chats ────────────────────────────────

    @Test
    void returnsMessagesAcrossMultipleChats() throws Exception {
        Chat chat2 = new Chat();
        chat2.setIdChat(20L);
        chat2.setNombreChat("otro-chat");

        LocalDateTime since = LocalDateTime.of(2026, 5, 11, 0, 0, 0);
        Mensaje m1 = mensaje(1, bob,   "hola",  since.plusMinutes(1));
        Mensaje m2 = mensaje(2, alice, "mundo", since.plusMinutes(2));
        Mensaje m3 = mensaje(3, bob,   "bye",   since.plusMinutes(3));

        when(repository.findUserByNombreUsuario("alice")).thenReturn(Optional.of(alice));
        when(repository.findChatsByUserId(1)).thenReturn(List.of(chat, chat2));
        when(repository.findMessagesSince(eq(10L), eq(since))).thenReturn(List.of(m1, m2));
        when(repository.findMessagesSince(eq(20L), eq(since))).thenReturn(List.of(m3));

        String json = app.loadMessageDelta(request("alice", "2026-05-11 00:00:00"));

        LoadMessageDeltaResponseDTO resp = mapper.readValue(json, LoadMessageDeltaResponseDTO.class);
        assertThat(resp.getConversations()).containsKeys("grupo-test", "otro-chat");
        assertThat(resp.getConversations().get("grupo-test")).hasSize(2);
        assertThat(resp.getConversations().get("otro-chat")).hasSize(1);
    }

    // ── epoch since returns everything the repo gives ────────────────────────

    @Test
    void epochSinceReturnsAllMessages() throws Exception {
        LocalDateTime epoch = LocalDateTime.of(1970, 1, 1, 0, 0, 0);
        Mensaje m1 = mensaje(1, bob, "primero",  epoch.plusYears(50));
        Mensaje m2 = mensaje(2, bob, "segundo",  epoch.plusYears(55));

        when(repository.findUserByNombreUsuario("alice")).thenReturn(Optional.of(alice));
        when(repository.findChatsByUserId(1)).thenReturn(List.of(chat));
        when(repository.findMessagesSince(eq(10L), eq(epoch))).thenReturn(List.of(m1, m2));

        String json = app.loadMessageDelta(request("alice", "1970-01-01 00:00:00"));

        LoadMessageDeltaResponseDTO resp = mapper.readValue(json, LoadMessageDeltaResponseDTO.class);
        assertThat(resp.getConversations().get("grupo-test")).hasSize(2);
    }
}
