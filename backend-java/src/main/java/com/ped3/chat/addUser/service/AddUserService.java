package com.ped3.chat.addUser.service;

import com.ped3.chat.addUser.domain.AddUserResponseDTO;
import com.ped3.chat.addUser.repository.AddUserRepository;
import com.ped3.chat.shared.domain.Usuario;
import com.ped3.chat.shared.util.CaesarCipher;
import org.springframework.transaction.annotation.Transactional;

public class AddUserService {
    private final AddUserRepository repository;

    public AddUserService(AddUserRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public AddUserResponseDTO addUser(String username, String password) {
        if (repository.findByNombreUsuario(username).isPresent()) {
            return new AddUserResponseDTO();
        }

        try {
            Usuario newUser = new Usuario();
            newUser.setNombreUsuario(username);
            newUser.setContrasenaHash(CaesarCipher.encrypt(password));
            repository.save(newUser);

            AddUserResponseDTO response = new AddUserResponseDTO();
            response.setProcessed(true);
            return response;
        } catch (Exception e) {
            System.err.println("Error adding user '" + username + "': " + e.getMessage());
            e.printStackTrace();
            return new AddUserResponseDTO();
        }
    }
}
