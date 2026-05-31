"""Constructores de mensajes JSON para el protocolo del servidor Rust.

Cada función `build_*` devuelve un string JSON listo para enviar; el framing
con EOT lo aplica `frame_message` antes de mandar por el socket.
"""

import json

EOT = b'\x04'


def build_login(username, password):
    """Construye la petición de autenticación de un usuario existente."""
    return json.dumps({"action": "login", "username": username, "password": password}, indent=4)


def build_create_user(username, password):
    """Construye la petición de registro de un usuario nuevo."""
    return json.dumps({"action": "create_user", "username": username, "password": password}, indent=4)


def build_create_chat(chat_name, participants):
    """Construye la petición de creación de un chat con la lista de participantes dada."""
    return json.dumps({"action": "create_chat", "chat_name": chat_name, "participants": participants}, indent=4)


def build_send_msg(chat, msg, username=None):
    """Construye la petición de envío de mensaje a un chat.

    `username` es opcional; si se omite el servidor usa la sesión activa.
    """
    d = {"action": "send_msg", "chat": chat, "msg": msg}
    if username:
        d["username"] = username
    return json.dumps(d)


def build_logout():
    """Construye la notificación de cierre de sesión."""
    return json.dumps({"action": "logout"}, indent=4)


def build_load_message_delta(username, since):
    """Construye la petición de delta: mensajes posteriores a `since` (formato 'yyyy-MM-dd HH:mm:ss')."""
    return json.dumps({"action": "load_message_delta", "username": username, "since": since}, indent=4)


def frame_message(msg):
    """Añade el delimitador EOT (0x04) al final del mensaje para su envío por TCP."""
    if isinstance(msg, str):
        msg = msg.encode('utf-8')
    return msg + EOT


def parse_response(raw):
    """Decodifica un mensaje raw (bytes o str) eliminando el EOT y parseando el JSON.

    Devuelve el objeto Python deserializado, o el string original si no es JSON válido.
    """
    if isinstance(raw, bytes):
        raw = raw.rstrip(EOT).decode('utf-8', errors='replace')
    else:
        raw = raw.rstrip('\x04')
    try:
        return json.loads(raw)
    except Exception:
        return raw
