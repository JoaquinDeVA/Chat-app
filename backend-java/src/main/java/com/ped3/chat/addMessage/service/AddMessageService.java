package com.ped3.chat.addMessage.service;

import com.ped3.chat.addMessage.domain.AddMessageResponseDTO;
import com.ped3.chat.addMessage.repository.AddMessageRepository;
import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Mensaje;
import com.ped3.chat.shared.domain.Usuario;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Optional;

public class AddMessageService {
    private final AddMessageRepository repository;

    public AddMessageService(AddMessageRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public AddMessageResponseDTO addMessage(String username, String chatname, String content, String timestamp) {
        try {
            Optional<Usuario> sender = repository.findUserByNombreUsuario(username);
            if (sender.isEmpty()) {
                return new AddMessageResponseDTO();
            }

            Optional<Chat> chat = repository.findChatByNombreChat(chatname);
            if (chat.isEmpty()) {
                return new AddMessageResponseDTO();
            }

            Mensaje mensaje = new Mensaje();
            mensaje.setAutor(sender.get());
            mensaje.setChat(chat.get());
            mensaje.setContenido(content);
            mensaje.setFechaEnvio(LocalDateTime.parse(timestamp, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
            repository.save(mensaje);

            AddMessageResponseDTO response = new AddMessageResponseDTO();
            response.setProcessed(true);
            return response;
        } catch (Exception e) {
            System.err.println("Error adding message for user '" + username + "' in chat '" + chatname + "': " + e.getMessage());
            e.printStackTrace();
            return new AddMessageResponseDTO();
        }
    }
}
