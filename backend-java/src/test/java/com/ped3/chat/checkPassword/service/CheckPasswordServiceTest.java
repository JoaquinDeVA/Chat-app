package com.ped3.chat.checkPassword.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.checkPassword.controller.CheckPasswordController;
import com.ped3.chat.checkPassword.domain.CheckPasswordResponseDTO;
import com.ped3.chat.checkPassword.repository.CheckPasswordUsuarioRepository;
import com.ped3.chat.shared.domain.Usuario;
import com.ped3.chat.shared.util.CaesarCipher;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CheckPasswordServiceTest {

    @Mock
    private CheckPasswordUsuarioRepository repository;

    private final ObjectMapper mapper = new ObjectMapper();
    private CheckPasswordController app;

    @BeforeEach
    void setUp() {
        app = new CheckPasswordController(new CheckPasswordService(repository));
    }

    @Test
    void testCheckPassword_Success_WithRawJson() throws Exception {
        Usuario user = new Usuario();
        user.setNombreUsuario("admin");
        user.setContrasenaHash(CaesarCipher.encrypt("1234"));
        when(repository.findByNombreUsuario("admin")).thenReturn(Optional.of(user));

        String jsonReq = """
            {
              "username": "admin",
              "password": "1234"
            }
            """;

        String jsonResp = app.checkPassword(jsonReq);

        CheckPasswordResponseDTO response = mapper.readValue(jsonResp, CheckPasswordResponseDTO.class);
        assertThat(response.isAuthorized()).isTrue();
        assertThat(jsonResp).contains("\"authorized\":true");
    }

    @Test
    void testCheckPassword_Failure_WithRawJson() throws Exception {
        Usuario user = new Usuario();
        user.setNombreUsuario("admin");
        user.setContrasenaHash(CaesarCipher.encrypt("1234"));
        when(repository.findByNombreUsuario("admin")).thenReturn(Optional.of(user));

        String jsonReq = """
            {
              "username": "admin",
              "password": "wrong_password"
            }
            """;

        String jsonResp = app.checkPassword(jsonReq);

        CheckPasswordResponseDTO response = mapper.readValue(jsonResp, CheckPasswordResponseDTO.class);
        assertThat(response.isAuthorized()).isFalse();
        assertThat(jsonResp).contains("\"authorized\":false");
    }
}
