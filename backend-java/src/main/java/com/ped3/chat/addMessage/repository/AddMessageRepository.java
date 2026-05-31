package com.ped3.chat.addMessage.repository;

import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Mensaje;
import com.ped3.chat.shared.domain.Usuario;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface AddMessageRepository extends JpaRepository<Mensaje, Long> {

    @Query("SELECT u FROM Usuario u WHERE u.nombreUsuario = :nombreUsuario")
    Optional<Usuario> findUserByNombreUsuario(@Param("nombreUsuario") String nombreUsuario);

    @Query("SELECT c FROM Chat c WHERE c.nombreChat = :nombreChat")
    Optional<Chat> findChatByNombreChat(@Param("nombreChat") String nombreChat);
}
