package com.ped3.chat.shared.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "Chats")
@Getter
@Setter
@NoArgsConstructor
public class Chat {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "id_chat")
  private Long idChat;

  @Column(name = "nombre_chat", length = 100)
  private String nombreChat;

  public Long getIdChat() {
    return idChat;
  }

  public void setIdChat(Long idChat) {
    this.idChat = idChat;
  }

  public String getNombreChat() {
    return nombreChat;
  }

  public void setNombreChat(String nombreChat) {
    this.nombreChat = nombreChat;
  }
}
