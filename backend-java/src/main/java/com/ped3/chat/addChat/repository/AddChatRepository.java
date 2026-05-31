package com.ped3.chat.addChat.repository;

import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Usuario;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface AddChatRepository extends JpaRepository<Chat, Long> {

    @Query(value = "SELECT c.* FROM Chats c WHERE c.nombre_chat = :nombreChat LIMIT 1", nativeQuery = true)
    Optional<Chat> findByNombreChat(@Param("nombreChat") String nombreChat);

    @Query("SELECT u FROM Usuario u WHERE u.nombreUsuario = :nombreUsuario")
    Optional<Usuario> findUserByNombreUsuario(@Param("nombreUsuario") String nombreUsuario);
}