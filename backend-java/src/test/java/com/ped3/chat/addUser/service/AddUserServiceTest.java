package com.ped3.chat.addUser.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ped3.chat.addUser.controller.AddUserController;
import com.ped3.chat.addUser.domain.AddUserResponseDTO;
import com.ped3.chat.addUser.repository.AddUserRepository;
import com.ped3.chat.shared.domain.Usuario;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AddUserServiceTest {

    @Mock
    private AddUserRepository repository;

    private final ObjectMapper mapper = new ObjectMapper();
    private AddUserController app;

    @BeforeEach
    void setUp() {
        app = new AddUserController(new AddUserService(repository));
    }

    @Test
    void testAddUser_Success_NewUser() throws Exception {
        when(repository.findByNombreUsuario("newuser")).thenReturn(Optional.empty());

        String jsonReq = """
            {
              "username": "newuser",
              "password": "password123"
            }
            """;

        String jsonResp = app.addUser(jsonReq);

        AddUserResponseDTO response = mapper.readValue(jsonResp, AddUserResponseDTO.class);
        assertThat(response.isProcessed()).isTrue();
        verify(repository, times(1)).save(any(Usuario.class));
    }

    @Test
    void testAddUser_Failure_UserExists() throws Exception {
        Usuario existingUser = new Usuario();
        existingUser.setNombreUsuario("existinguser");
        when(repository.findByNombreUsuario("existinguser")).thenReturn(Optional.of(existingUser));

        String jsonReq = """
            {
              "username": "existinguser",
              "password": "newpass"
            }
            """;

        String jsonResp = app.addUser(jsonReq);

        AddUserResponseDTO response = mapper.readValue(jsonResp, AddUserResponseDTO.class);
        assertThat(response.isProcessed()).isFalse();
        verify(repository, never()).save(any());
    }
}
