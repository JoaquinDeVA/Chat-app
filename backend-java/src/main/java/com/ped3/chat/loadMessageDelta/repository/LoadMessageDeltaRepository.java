package com.ped3.chat.loadMessageDelta.repository;

import com.ped3.chat.shared.domain.Chat;
import com.ped3.chat.shared.domain.Mensaje;
import com.ped3.chat.shared.domain.Usuario;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

public interface LoadMessageDeltaRepository extends JpaRepository<Mensaje, Long> {

    @Query("SELECT u FROM Usuario u WHERE u.nombreUsuario = :nombreUsuario")
    Optional<Usuario> findUserByNombreUsuario(@Param("nombreUsuario") String nombreUsuario);

    @Query("SELECT p.chat FROM Participante p WHERE p.usuario.idUsuario = :idUsuario ORDER BY p.chat.idChat")
    List<Chat> findChatsByUserId(@Param("idUsuario") Integer idUsuario);

    @Query(value = """
        SELECT m.* FROM Mensajes m
        WHERE m.id_chat = :idChat AND m.fecha_envio > :since
        ORDER BY m.fecha_envio ASC
        """, nativeQuery = true)
    List<Mensaje> findMessagesSince(@Param("idChat") Long idChat, @Param("since") LocalDateTime since);
}
