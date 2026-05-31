package com.ped3.chat.getChatMembers.repository;

import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Usuario;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface GetChatMembersRepository extends JpaRepository<Chat, Long> {

    @Query(value = "SELECT c.* FROM Chats c WHERE c.nombre_chat = :nombreChat LIMIT 1", nativeQuery = true)
    Optional<Chat> findByNombreChat(@Param("nombreChat") String nombreChat);

    @Query("SELECT p.usuario FROM Participante p WHERE p.chat.idChat = :idChat")
    List<Usuario> findMembersByChatId(@Param("idChat") Long idChat);
}
