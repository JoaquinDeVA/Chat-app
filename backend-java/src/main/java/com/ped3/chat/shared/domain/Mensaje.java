package com.ped3.chat.shared.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "Mensajes")
@Getter
@Setter
@NoArgsConstructor
public class Mensaje {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "id_mensaje")
  private int idMensaje;

  @ManyToOne
  @JoinColumn(name = "id_chat", nullable = false)
  private Chat chat;

  @ManyToOne
  @JoinColumn(name = "id_autor", nullable = false)
  private Usuario autor;

  @Column(name = "contenido", nullable = false, columnDefinition = "TEXT")
  private String contenido;

  @Column(name = "fecha_envio")
  private LocalDateTime fechaEnvio;

  public int getIdMensaje() {
    return idMensaje;
  }

  public void setIdMensaje(int idMensaje) {
    this.idMensaje = idMensaje;
  }

  public Chat getChat() {
    return chat;
  }

  public void setChat(Chat chat) {
    this.chat = chat;
  }

  public Usuario getAutor() {
    return autor;
  }

  public void setAutor(Usuario autor) {
    this.autor = autor;
  }

  public String getContenido() {
    return contenido;
  }

  public void setContenido(String contenido) {
    this.contenido = contenido;
  }

  public LocalDateTime getFechaEnvio() {
    return fechaEnvio;
  }

  public void setFechaEnvio(LocalDateTime fechaEnvio) {
    this.fechaEnvio = fechaEnvio;
  }
}
