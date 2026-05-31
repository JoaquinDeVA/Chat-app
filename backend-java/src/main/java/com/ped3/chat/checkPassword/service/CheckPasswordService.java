package com.ped3.chat.checkPassword.service;

import com.ped3.chat.checkPassword.domain.CheckPasswordResponseDTO;
import com.ped3.chat.checkPassword.repository.CheckPasswordUsuarioRepository;
import com.ped3.chat.shared.domain.Usuario;
import com.ped3.chat.shared.util.CaesarCipher;

import java.util.Optional;

public class CheckPasswordService {
    private final CheckPasswordUsuarioRepository repository;

    public CheckPasswordService(CheckPasswordUsuarioRepository repository) {
        this.repository = repository;
    }

    public CheckPasswordResponseDTO checkPassword(String username, String password) {
        Optional<Usuario> user = repository.findByNombreUsuario(username);
        boolean isAuthorized = user.isPresent() && CaesarCipher.matches(password, user.get().getContrasenaHash());
        return new CheckPasswordResponseDTO(isAuthorized);
    }
}
