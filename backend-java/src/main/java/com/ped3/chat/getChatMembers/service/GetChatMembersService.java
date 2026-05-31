package com.ped3.chat.getChatMembers.service;

import com.ped3.chat.getChatMembers.domain.GetChatMembersResponseDTO;
import com.ped3.chat.getChatMembers.repository.GetChatMembersRepository;
import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Usuario;

import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

public class GetChatMembersService {
    private final GetChatMembersRepository repository;

    public GetChatMembersService(GetChatMembersRepository repository) {
        this.repository = repository;
    }

    public GetChatMembersResponseDTO getChatMembers(String chatname) {
        try {
            if (chatname == null || chatname.isBlank()) {
                return new GetChatMembersResponseDTO();
            }

            Optional<Chat> chat = repository.findByNombreChat(chatname);
            if (chat.isEmpty()) {
                return new GetChatMembersResponseDTO();
            }

            List<Usuario> usuarios = repository.findMembersByChatId(chat.get().getIdChat());
            List<String> members = usuarios.stream()
                    .map(Usuario::getNombreUsuario)
                    .collect(Collectors.toList());

            GetChatMembersResponseDTO response = new GetChatMembersResponseDTO();
            response.setMembers(members);
            return response;
        } catch (Exception e) {
            System.err.println("Error getting members for chat '" + chatname + "': " + e.getMessage());
            e.printStackTrace();
            return new GetChatMembersResponseDTO();
        }
    }
}
