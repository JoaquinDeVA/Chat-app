package com.ped3.chat.loadConversations.service;

import com.ped3.chat.loadConversations.domain.LoadConversationsResponseDTO;
import com.ped3.chat.loadConversations.domain.LoadConversationsResponseDTO.MessageDTO;
import com.ped3.chat.loadConversations.repository.LoadConversationsRepository;
import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Mensaje;
import com.ped3.chat.shared.domain.Usuario;

import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public class LoadConversationsService {
    private final LoadConversationsRepository repository;
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public LoadConversationsService(LoadConversationsRepository repository) {
        this.repository = repository;
    }

    public LoadConversationsResponseDTO loadConversations(String username) {
        LoadConversationsResponseDTO response = new LoadConversationsResponseDTO();
        Map<String, List<MessageDTO>> conversations = new HashMap<>();

        try {
            Optional<Usuario> userOpt = repository.findUserByNombreUsuario(username);
            if (userOpt.isEmpty()) {
                return response;
            }

            Usuario user = userOpt.get();
            List<Chat> userChats = repository.findUserChats(user.getIdUsuario());

            for (Chat chat : userChats) {
                List<Mensaje> messages = repository.findChatMessages(chat.getIdChat());
                List<MessageDTO> dtos = new ArrayList<>();
                for (Mensaje m : messages) {
                    dtos.add(toMessageDTO(chat.getNombreChat(), m));
                }
                conversations.put(chat.getNombreChat(), dtos);
            }

            response.setConversations(conversations);
            return response;
        } catch (Exception e) {
            System.err.println("Error loading conversations for user '" + username + "': " + e.getMessage());
            e.printStackTrace();
            return response;
        }
    }

    private MessageDTO toMessageDTO(String chatname, Mensaje mensaje) {
        MessageDTO dto = new MessageDTO();
        dto.setChatname(chatname);
        dto.setAuthor(mensaje.getAutor().getNombreUsuario());
        dto.setContents(mensaje.getContenido());
        dto.setSent(mensaje.getFechaEnvio().format(DATE_FORMATTER));
        return dto;
    }
}
