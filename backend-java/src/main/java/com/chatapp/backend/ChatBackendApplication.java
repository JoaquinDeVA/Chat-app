package com.chatapp.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** Entry point: starts Spring (JPA, services) and the TCP server that exposes them. */
@SpringBootApplication
public class ChatBackendApplication {

  public static void main(String[] args) {
    SpringApplication.run(ChatBackendApplication.class, args);
  }
}
