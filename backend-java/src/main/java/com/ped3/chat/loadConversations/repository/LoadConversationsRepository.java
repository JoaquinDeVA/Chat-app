package com.ped3.chat.loadConversations.repository;

import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Mensaje;
import com.ped3.chat.shared.domain.Usuario;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface LoadConversationsRepository extends JpaRepository<Mensaje, Long> {

    // Find user by username
    @Query("SELECT u FROM Usuario u WHERE u.nombreUsuario = :nombreUsuario")
    Optional<Usuario> findUserByNombreUsuario(@Param("nombreUsuario") String nombreUsuario);

    // Find all chats where user is a participant
    @Query("SELECT p.chat FROM Participante p WHERE p.usuario.idUsuario = :idUsuario ORDER BY p.chat.idChat")
    List<Chat> findUserChats(@Param("idUsuario") Integer idUsuario);

    // Find all messages in a specific chat, ordered by date
    @Query(value = """
        SELECT m.* FROM Mensajes m
        WHERE m.id_chat = :idChat
        ORDER BY m.fecha_envio ASC
        """, nativeQuery = true)
    List<Mensaje> findChatMessages(@Param("idChat") Long idChat);
}
