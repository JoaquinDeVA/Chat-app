package com.ped3.chat.tcp;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;

import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Component;

import com.ped3.chat.addChat.controller.AddChatController;
import com.ped3.chat.addMessage.controller.AddMessageController;
import com.ped3.chat.addUser.controller.AddUserController;
import com.ped3.chat.checkPassword.controller.CheckPasswordController;
import com.ped3.chat.getChatMembers.controller.GetChatMembersController;
import com.ped3.chat.loadConversations.controller.LoadConversationsController;
import com.ped3.chat.loadMessageDelta.controller.LoadMessageDeltaController;

@Component
@Lazy(false)
public class TcpServerRunner implements CommandLineRunner {

  private static final char SEPARADOR = 0x04; // Separador unico para delimitar mensajes

  private final CheckPasswordController checkPasswordController;
  private final AddUserController addUserController;
  private final AddChatController addChatController;
  private final AddMessageController addMessageController;
  private final LoadConversationsController loadConversationsController;
  private final GetChatMembersController getChatMembersController;
  private final LoadMessageDeltaController loadMessageDeltaController;

  public TcpServerRunner(
      CheckPasswordController checkPasswordController,
      AddUserController addUserController,
      AddChatController addChatController,
      AddMessageController addMessageController,
      LoadConversationsController loadConversationsController,
      GetChatMembersController getChatMembersController,
      LoadMessageDeltaController loadMessageDeltaController) {

    this.checkPasswordController = checkPasswordController;
    this.addUserController = addUserController;
    this.addChatController = addChatController;
    this.addMessageController = addMessageController;
    this.loadConversationsController = loadConversationsController;
    this.getChatMembersController = getChatMembersController;
    this.loadMessageDeltaController = loadMessageDeltaController;
  }

@Override
public void run(String... args) throws Exception {
    int puerto = 9090;

    try (ServerSocket serverSocket = new ServerSocket(puerto)) {
        System.out.println("TCP: Servidor iniciado y escuchando en puerto " + puerto);

        boolean shutdown = false;
        while (!shutdown) {
            try (Socket socket = serverSocket.accept();
                 InputStream input = socket.getInputStream();
                 OutputStream output = socket.getOutputStream();
                 BufferedReader reader = new BufferedReader(new InputStreamReader(input))) {

                System.out.println("Conectado con el Server Rust: " + socket.getRemoteSocketAddress());

                StringBuilder buffer = new StringBuilder();
                int caracter;

                while ((caracter = reader.read()) != -1) {
                    char c = (char) caracter;
                    if (c == SEPARADOR) {
                        String mensaje = buffer.toString();
                        buffer.setLength(0);

                        if (mensaje.trim().toUpperCase().startsWith("SHUTDOWN")) {
                            System.out.println("TCP: Recibido Shutdown del servidor. Cerrando backend...");
                            shutdown = true;
                            break;
                        }

                        String response = procesarMensaje(mensaje);
                        output.write(response.getBytes());
                        output.write(SEPARADOR);
                        output.flush();
                    } else {
                        buffer.append(c);
                    }
                }
            } catch (IOException e) {
                System.err.println("Conexión perdida con el Server Rust: " + e.getMessage());
            }
        }

        System.out.println("TCP: Backend cerrado correctamente.");
    } catch (Exception e) {
        System.err.println("Error crítico: No se pudo abrir el puerto " + puerto);
        e.printStackTrace();
    }
}

	/* Procesa el mensaje recibido del cliente */
  	private String procesarMensaje(String raw) {

		//Buscamos el indice del primer '{' para separar la peticion del cuerpo JSON. Si no lo encontramos, el formato es invalido.
    	int indexApertura = raw.indexOf('{');
    	if (indexApertura == -1) {
      		System.err.println("Formato invalido: " + raw);
      		return "{\"error\": \"Formato invalido\"}";
    	}

		//En base a la primera llave separamos la peticion (lo que viene antes) del cuerpo JSON (lo que viene despues). La peticion se trim para eliminar espacios.
    	String peticion = raw.substring(0, indexApertura).trim();
    	String bodyJson = raw.substring(indexApertura);

    	try {
			//uppercase pq no diferenciamos peticiones por mayus/minus. Pero no deberia ser necesario
    		switch (peticion.toUpperCase()) {

				//Peticion de autenticacion: Comprobar que el usuario y contraseña son correctos.
				case "AUTHREQUEST":
				String checkPasswordResponse = checkPasswordController.checkPassword(bodyJson);
				System.out.println("Response: " + checkPasswordResponse);
				return checkPasswordResponse;

				//Peticion de registro: Crear un nuevo usuario con el nombre y contraseña indicados.
				case "ADDUSERREQUEST":
				String addUserResponse = addUserController.addUser(bodyJson);
				System.out.println("Response: " + addUserResponse);
				return addUserResponse;

				//Peticion de crear chat: Crear un nuevo chat con los usuarios indicados.
				case "CREATECHATREQUEST":
				String addChatResponse = addChatController.addChat(bodyJson);
				System.out.println("Response: " + addChatResponse);
				return addChatResponse;

				//Peticion de enviar mensaje: Añadir un nuevo mensaje al chat indicado.
				case "SENDMESSAGEREQUEST":
				String addMessageResponse = addMessageController.addMessage(bodyJson);
				System.out.println("Response: " + addMessageResponse);
				return addMessageResponse;

				//Peticion de cargar conversaciones: Obtener la lista de conversaciones y mensajes para el usuario indicado.
				case "LOADCONVERSATIONSREQUEST":
				String loadConversationsResponse = loadConversationsController.loadConversations(bodyJson);
				System.out.println("Response: " + loadConversationsResponse);
				return loadConversationsResponse;

				//Peticion de obtener miembros: Devolver la lista de participantes del chat indicado.
				case "GETCHATMEMBERSREQUEST":
				String getChatMembersResponse = getChatMembersController.getChatMembers(bodyJson);
				System.out.println("Response: " + getChatMembersResponse);
				return getChatMembersResponse;

				//Peticion de delta de mensajes: Obtener mensajes posteriores a una fecha para el usuario indicado.
				case "LOADMESSAGEDELTA":
				String loadMessageDeltaResponse = loadMessageDeltaController.loadMessageDelta(bodyJson);
				System.out.println("Response: " + loadMessageDeltaResponse);
				return loadMessageDeltaResponse;

				//Si la peticion no coincide con ninguna de las anteriores, devolvemos un error indicando que la peticion es desconocida.
				default:
				String errorMsg = "Peticion desconocida: " + peticion;
				System.out.println(errorMsg);
				//Lo devuelve como JSON para que el cliente pueda parsearlo.
				return "{\"error\": \"" + errorMsg + "\"}";
			}
    	} catch (Throwable e) {
			//Nada deberia lanzar excepciones aqui. No es relativo a la red.
      		System.err.println("Error procesando peticion: " + e.getMessage());
      		e.printStackTrace();
      		return "{\"error\": \"" + e.getMessage() + "\"}";
    	}
  	}
}
