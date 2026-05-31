"""Soporte de imágenes en mensajes.

Formato en tránsito (wire):  TAG|.ext|base64
Formato en sesión/disco:     TAG|uuid.ext
Fichero en disco:            chats/<user>/images/uuid.ext

Cada cliente genera su propio UUID al recibir o enviar una imagen; el UUID
no viaja por red, solo el binario en base64 y la extensión del fichero.
"""

import base64
import os
import subprocess
import uuid
from pathlib import Path

IMG_TAG = ''
SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def is_wire_format(s: str) -> bool:
    """TAG|.ext|base64 — binario todavía presente."""
    return isinstance(s, str) and s.startswith(IMG_TAG + '|') and s.count('|') >= 2


def is_image_ref(s: str) -> bool:
    """TAG|uuid.ext — binario ya guardado en disco."""
    return isinstance(s, str) and s.startswith(IMG_TAG + '|') and s.count('|') == 1


def get_filename(s: str) -> str:
    """Extrae uuid.ext de una ref."""
    parts = s.split('|', 2)
    return parts[1] if len(parts) >= 2 else ''


def encode_file(path: str) -> str | None:
    """Lee el fichero y devuelve el payload wire (TAG|.ext|base64), o None si no es imagen soportada."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTS:
        return None
    try:
        data = Path(path).read_bytes()
        b64 = base64.b64encode(data).decode('ascii')
        if '\x04' in b64:
            b64 = b64.replace('\x04', '')
        return f"{IMG_TAG}|{ext}|{b64}"
    except OSError:
        return None


def decode_and_save(wire: str, images_dir: Path) -> str:
    """Genera un UUID propio, guarda el binario en disco y devuelve la ref (TAG|uuid.ext)."""
    parts = wire.split('|', 2)
    if len(parts) != 3:
        return wire
    _, ext, b64 = parts

    images_dir.mkdir(parents=True, exist_ok=True)
    local_filename = f"{uuid.uuid4()}{ext}"
    try:
        (images_dir / local_filename).write_bytes(base64.b64decode(b64))
    except Exception:
        pass
    return f"{IMG_TAG}|{local_filename}"


def open_image(ref: str, images_dir: Path):
    """Abre la imagen con el visor por defecto del SO."""
    filename = get_filename(ref)
    if not filename:
        return
    path = images_dir / filename
    if not path.exists():
        return
    for cmd in (['xdg-open'], ['open']):
        try:
            subprocess.Popen(cmd + [str(path)])
            return
        except FileNotFoundError:
            continue
