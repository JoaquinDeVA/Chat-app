-- Schema of the chat database. Loaded automatically by docker-compose.yml; to load it by hand:
--   mysql -u root -p < shared/database.sql
CREATE DATABASE IF NOT EXISTS chat_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE chat_app;

CREATE TABLE users (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL          -- BCrypt hash (60 characters)
) ENGINE=InnoDB;

CREATE TABLE chats (
    id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- Many-to-many relation between users and chats
CREATE TABLE chat_members (
    user_id   BIGINT   NOT NULL,
    chat_id   BIGINT   NOT NULL,
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, chat_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE messages (
    id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    chat_id   BIGINT   NOT NULL,
    author_id BIGINT   NOT NULL,
    content   MEDIUMTEXT NOT NULL,                      -- up to 16 MB: images travel inside messages
    sent_at   DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),   -- microseconds: the sync cursor
    FOREIGN KEY (chat_id)   REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_messages_chat_sent (chat_id, sent_at)   -- history and delta queries
) ENGINE=InnoDB;
