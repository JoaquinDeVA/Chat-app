package com.ped3.chat.addChat.service;

import com.ped3.chat.addChat.domain.AddChatResponseDTO;
import com.ped3.chat.addChat.repository.AddChatParticipanteRepository;
import com.ped3.chat.addChat.repository.AddChatRepository;
import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Participante;
import com.ped3.chat.shared.domain.Usuario;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public class AddChatService {
    private final AddChatRepository chatRepository;
    private final AddChatParticipanteRepository participanteRepository;

    public AddChatService(AddChatRepository chatRepository, AddChatParticipanteRepository participanteRepository) {
        this.chatRepository = chatRepository;
        this.participanteRepository = participanteRepository;
    }

    @Transactional
    public AddChatResponseDTO addChat(String chatname, List<String> users) {
        try {
            if (chatname == null || chatname.isBlank() || users == null || users.isEmpty()) {
                return new AddChatResponseDTO();
            }

            if (chatRepository.findByNombreChat(chatname).isPresent()) {
                return new AddChatResponseDTO();
            }

            List<String> uniqueUsers = users.stream()
                .filter(u -> u != null && !u.isBlank())
                .distinct()
                .toList();

            if (uniqueUsers.isEmpty()) {
                return new AddChatResponseDTO();
            }

            List<Usuario> participantes = new ArrayList<>();
            for (String username : uniqueUsers) {
                Optional<Usuario> found = chatRepository.findUserByNombreUsuario(username);
                if (found.isEmpty()) {
                    return new AddChatResponseDTO();
                }
                participantes.add(found.get());
            }

            Chat chat = new Chat();
            chat.setNombreChat(chatname);
            chatRepository.save(chat);

            for (Usuario usuario : participantes) {
                Participante participante = new Participante();
                participante.setChat(chat);
                participante.setUsuario(usuario);
                participante.setFechaUnion(LocalDateTime.now());
                participanteRepository.save(participante);
            }

            AddChatResponseDTO response = new AddChatResponseDTO();
            response.setProcessed(true);
            return response;
        } catch (Exception e) {
            System.err.println("Error adding chat '" + chatname + "': " + e.getMessage());
            e.printStackTrace();
            return new AddChatResponseDTO();
        }
    }
}
