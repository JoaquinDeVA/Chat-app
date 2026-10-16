-- Deletes every row, keeping the schema (handy between manual test sessions).
USE chat_app;
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE messages;
TRUNCATE TABLE chat_members;
TRUNCATE TABLE chats;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;
