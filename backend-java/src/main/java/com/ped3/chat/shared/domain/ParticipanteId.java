package com.ped3.chat.shared.domain;

import java.io.Serializable;
import lombok.AllArgsConstructor;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode
public class ParticipanteId implements Serializable {
  private static final long serialVersionUID = 1L;

  private Integer usuario;
  private Long chat;
}
