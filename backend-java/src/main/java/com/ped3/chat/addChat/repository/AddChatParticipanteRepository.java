package com.ped3.chat.addChat.repository;

import com.ped3.chat.shared.domain.Participante;
import com.ped3.chat.shared.domain.ParticipanteId;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AddChatParticipanteRepository extends JpaRepository<Participante, ParticipanteId> {
}
