package com.ped3.chat.loadMessageDelta.domain;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class LoadMessageDeltaRequestDTO {
    private String username;
    private String since;

    public String getUsername() { return username; }
    public String getSince() { return since; }
}
