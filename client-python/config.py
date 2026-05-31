"""Lectura de la configuración de conexión desde config.txt.

Formato esperado del fichero (líneas con `clave = valor`, se ignoran comentarios `#`):

    ip = 127.0.0.1
    puerto = 6969
"""

import os


def load_config(path="config.txt"):
    """Lee `path` y devuelve (ip, puerto) como (str, int).

    Lanza FileNotFoundError si el fichero no existe y ValueError si faltan claves.
    """
    ip = None
    port = None
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró {path}")
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = [x.strip() for x in line.split("=", 1)]
            if key == "ip":
                ip = val
            elif key == "puerto":
                port = int(val)
    if not ip or not port:
        raise ValueError("Config incompleta, revisa config.txt")
    return ip, port
