"""Capa de abstracción sobre el protocolo de red.

Cada método de APIClient encapsula un ciclo petición-respuesta con el servidor:
envía el JSON construido por `protocol.py` y parsea la respuesta recibida.
"""

from typing import Dict, List, Tuple
from network import NetworkClient
from protocol import (
    build_login, build_create_user, build_create_chat,
    build_send_msg, build_logout, build_load_message_delta
)


class APIClient:
    """Interfaz de alto nivel para todas las operaciones contra el servidor."""

    def __init__(self, network_client: NetworkClient):
        """Recibe un NetworkClient ya conectado."""
        self.net = network_client

    def api_authenticate(self, username: str, password: str, is_register: bool = False) -> Tuple[bool, str, Dict]:
        """Autentica o registra al usuario.

        Con `is_register=True` envía `create_user`; con False envía `login`.
        Devuelve (éxito, mensaje_del_servidor, respuesta_completa).
        La respuesta de login incluye el campo `conversations` con todos los chats.
        """
        try:
            self.net.send(build_create_user(username, password) if is_register else build_login(username, password))
            resp = self.net.recv(timeout=5)
            if not resp or not isinstance(resp, dict):
                return False, "Respuesta inválida del servidor", {}
            if resp.get('code') == 1 or resp.get('processed') or resp.get('authorized'):
                return True, resp.get('msg', 'OK'), resp
            return False, resp.get('msg', 'Error de autenticación'), resp
        except Exception as e:
            return False, f"Error de conexión: {str(e)}", {}

    def api_send_message(self, chat_name: str, message: str, username: str) -> Tuple[bool, str]:
        """Envía un mensaje de texto a un chat y espera la confirmación del servidor.

        Devuelve (éxito, mensaje_del_servidor).
        """
        try:
            self.net.send(build_send_msg(chat_name, message, username))
            resp = self.net.recv(timeout=5)
            if not resp or not isinstance(resp, dict):
                return False, "Respuesta inválida"
            if resp.get('code') == 1 or resp.get('processed'):
                return True, resp.get('msg', 'Mensaje enviado')
            return False, resp.get('msg', 'Error enviando mensaje')
        except Exception as e:
            return False, f"Error: {str(e)}"

    def api_create_group(self, group_name: str, participants: List[str]) -> Tuple[bool, str]:
        """Solicita la creación de un chat nuevo con los participantes indicados.

        Devuelve (éxito, mensaje_del_servidor).
        """
        try:
            self.net.send(build_create_chat(group_name, participants))
            resp = self.net.recv(timeout=5)
            if not resp or not isinstance(resp, dict):
                return False, "Respuesta inválida"
            if resp.get('processed') == 1 or resp.get('code') == 1:
                return True, resp.get('msg', 'Grupo creado')
            return False, resp.get('msg', 'Error creando grupo')
        except Exception as e:
            return False, f"Error: {str(e)}"

    def api_load_message_delta(self, username: str, since: str) -> Tuple[bool, str, Dict]:
        """Solicita los mensajes posteriores a `since` para todos los chats del usuario.

        `since` debe tener formato 'yyyy-MM-dd HH:mm:ss'.
        Devuelve (éxito, mensaje, {chat: [msg_dict, ...]}).
        """
        try:
            self.net.send(build_load_message_delta(username, since))
            resp = self.net.recv(timeout=10)
            if not resp or not isinstance(resp, dict):
                return False, "Respuesta inválida", {}
            return True, "Delta recibida", resp.get('conversations', {})
        except Exception as e:
            return False, f"Error cargando delta: {str(e)}", {}

    def api_logout(self):
        """Notifica al servidor el cierre de sesión. Falla silenciosamente."""
        try:
            if self.net and self.net.running:
                self.net.send(build_logout())
        except Exception:
            pass
