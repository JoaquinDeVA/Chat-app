package com.ped3.chat.loadMessageDelta.service;

import com.ped3.chat.loadMessageDelta.domain.LoadMessageDeltaResponseDTO;
import com.ped3.chat.loadMessageDelta.domain.LoadMessageDeltaResponseDTO.MessageDTO;
import com.ped3.chat.loadMessageDelta.repository.LoadMessageDeltaRepository;
import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Mensaje;
import com.ped3.chat.shared.domain.Usuario;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public class LoadMessageDeltaService {
    private final LoadMessageDeltaRepository repository;
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public LoadMessageDeltaService(LoadMessageDeltaRepository repository) {
        this.repository = repository;
    }

    public LoadMessageDeltaResponseDTO loadMessageDelta(String username, String since) {
        LoadMessageDeltaResponseDTO response = new LoadMessageDeltaResponseDTO();
        Map<String, List<MessageDTO>> conversations = new HashMap<>();

        try {
            LocalDateTime sinceDate = LocalDateTime.parse(since, DATE_FORMATTER);

            Optional<Usuario> userOpt = repository.findUserByNombreUsuario(username);
            if (userOpt.isEmpty()) {
                return response;
            }

            Usuario user = userOpt.get();
            List<Chat> userChats = repository.findChatsByUserId(user.getIdUsuario());

            for (Chat chat : userChats) {
                List<Mensaje> messages = repository.findMessagesSince(chat.getIdChat(), sinceDate);
                List<MessageDTO> dtos = new ArrayList<>();
                for (Mensaje m : messages) {
                    dtos.add(toMessageDTO(chat.getNombreChat(), m));
                }
                conversations.put(chat.getNombreChat(), dtos);
            }

            response.setConversations(conversations);
            return response;
        } catch (Exception e) {
            System.err.println("Error loading message delta for user '" + username + "' since '" + since + "': " + e.getMessage());
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
