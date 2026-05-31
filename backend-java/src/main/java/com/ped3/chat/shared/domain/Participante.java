package com.ped3.chat.shared.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "Participantes")
@IdClass(ParticipanteId.class)
@Getter
@Setter
@NoArgsConstructor
public class Participante {
  @Id
  @ManyToOne
  @JoinColumn(name = "id_usuario", nullable = false)
  private Usuario usuario;

  @Id
  @ManyToOne
  @JoinColumn(name = "id_chat", nullable = false)
  private Chat chat;

  @Column(name = "fecha_union")
  private LocalDateTime fechaUnion;

  public Usuario getUsuario() {
    return usuario;
  }

  public void setUsuario(Usuario usuario) {
    this.usuario = usuario;
  }

  public Chat getChat() {
    return chat;
  }

  public void setChat(Chat chat) {
    this.chat = chat;
  }

  public LocalDateTime getFechaUnion() {
    return fechaUnion;
  }

  public void setFechaUnion(LocalDateTime fechaUnion) {
    this.fechaUnion = fechaUnion;
  }
}
