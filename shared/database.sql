-- Configuración de la Base de Datos para Chat Centralizado
CREATE DATABASE IF NOT EXISTS chat_app;
USE chat_app;

-- 1. Tabla de Usuarios
-- La contraseña se define amplia para soportar hashes (BCrypt/Argon2)
CREATE TABLE usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    nombre_usuario VARCHAR(50) NOT NULL UNIQUE,
    contraseña VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- 2. Tabla de Chats (Salas)
CREATE TABLE chats (
    id_chat INT AUTO_INCREMENT PRIMARY KEY,
    nombre_chat VARCHAR(100) UNIQUE
) ENGINE=InnoDB;

-- 3. Tabla Intermedia: Participantes
-- Relaciona Usuarios con Chats (N:N)
CREATE TABLE participantes (
    id_usuario INT NOT NULL,
    id_chat INT NOT NULL,
    fecha_union DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_usuario, id_chat),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    FOREIGN KEY (id_chat) REFERENCES chats(id_chat) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. Tabla de Mensajes
-- id_autor vincula quién lo escribió, id_chat vincula dónde se escribió
CREATE TABLE mensajes (
    id_mensaje INT AUTO_INCREMENT PRIMARY KEY,
    id_chat INT NOT NULL,
    id_autor INT NOT NULL,
    contenido TEXT NOT NULL,
    fecha_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_chat) REFERENCES chats(id_chat) ON DELETE CASCADE,
    FOREIGN KEY (id_autor) REFERENCES usuarios(id_usuario) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Índice para optimizar la reconstrucción del historial en el servidor
CREATE INDEX idx_chat_fecha ON mensajes(id_chat, fecha_envio);