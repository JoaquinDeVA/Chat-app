"""Persistencia local de conversaciones por usuario.

Los datos se guardan en `./chats/<usuario>/`:
  - `<chat>.txt`    — mensajes en JSON, uno por línea (dicts) o texto plano (strings).
  - `last_sync.txt` — fecha del mensaje más reciente recibido (para la delta).
"""

import json
from pathlib import Path
from typing import Dict, List

CHATS_DIR = Path("./chats")


def _format_message(msg) -> str:
    """Serializa un mensaje para disco: JSON si es dict, texto plano si es str."""
    if isinstance(msg, dict):
        return json.dumps(msg, ensure_ascii=False)
    return str(msg)


def _parse_message(line: str):
    """Deserializa una línea de disco: dict si es JSON válido, str si no."""
    try:
        return json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return line


class PersistenceManager:
    """Gestiona la lectura y escritura de conversaciones en el directorio local."""

    def __init__(self):
        """Crea el directorio raíz de chats si no existe."""
        CHATS_DIR.mkdir(exist_ok=True)

    @staticmethod
    def _safe(name: str) -> str:
        """Sanitiza `name` para usarlo como parte de una ruta de fichero."""
        return "".join(c for c in name if c.isalnum() or c in ('-', '_'))

    def _user_dir(self, username: str) -> Path:
        """Devuelve la ruta del directorio personal del usuario."""
        return CHATS_DIR / self._safe(username)

    def images_dir(self, username: str) -> Path:
        """Devuelve la ruta del directorio de imágenes del usuario."""
        return self._user_dir(username) / 'images'

    def load_last_sync(self, username: str) -> str:
        """Devuelve la fecha del mensaje más reciente conocido, o '1970-01-01 00:00:00'."""
        path = self._user_dir(username) / "last_sync.txt"
        if not path.exists():
            return "1970-01-01 00:00:00"
        try:
            return path.read_text(encoding='utf-8').strip() or "1970-01-01 00:00:00"
        except Exception:
            return "1970-01-01 00:00:00"

    def _save_last_sync(self, user_dir: Path, date: str):
        """Escribe `date` en `last_sync.txt` del directorio de usuario."""
        try:
            (user_dir / "last_sync.txt").write_text(date, encoding='utf-8')
        except Exception:
            pass

    def load_user_conversations(self, username: str) -> Dict[str, List[str]]:
        """Carga todos los ficheros de chat del usuario y los devuelve como {chat: [líneas]}."""
        user_dir = self._user_dir(username)
        conversations: Dict[str, List[str]] = {}
        try:
            if not user_dir.exists():
                return conversations
            for filepath in user_dir.glob("*.txt"):
                if filepath.stem == "last_sync":
                    continue
                with open(filepath, 'r', encoding='utf-8') as f:
                    conversations[filepath.stem] = [
                        _parse_message(line.rstrip('\n')) for line in f if line.strip()
                    ]
        except Exception as e:
            print(f"Error cargando conversaciones de {username}: {e}")
        return conversations

    def save_user_conversations(self, username: str, conversations: Dict[str, List]):
        """Escribe todas las conversaciones del usuario en disco y actualiza last_sync.txt.

        Útil al inicio/cierre de sesión para volcar el estado completo en memoria.
        """
        user_dir = self._user_dir(username)
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            for chat_name, messages in conversations.items():
                with open(user_dir / f"{self._safe(chat_name)}.txt", 'w', encoding='utf-8') as f:
                    for msg in messages:
                        f.write(_format_message(msg) + '\n')
            last_sent = max(
                (m['sent'] for msgs in conversations.values()
                 for m in msgs if isinstance(m, dict) and m.get('sent')),
                default=None
            )
            if last_sent:
                self._save_last_sync(user_dir, last_sent)
        except Exception as e:
            print(f"Error guardando conversaciones de {username}: {e}")

    def update_user_chat(self, username: str, chat_name: str, messages: List):
        """Reescribe el fichero de un único chat y avanza last_sync.txt si hay fecha más nueva.

        Se llama en tiempo real tras cada mensaje push o enviado, para no volcar
        todos los chats cada vez.
        """
        user_dir = self._user_dir(username)
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            with open(user_dir / f"{self._safe(chat_name)}.txt", 'w', encoding='utf-8') as f:
                for msg in messages:
                    f.write(_format_message(msg) + '\n')
            last_sent = next(
                (m['sent'] for m in reversed(messages) if isinstance(m, dict) and m.get('sent')),
                None
            )
            if last_sent and last_sent > self.load_last_sync(username):
                self._save_last_sync(user_dir, last_sent)
        except Exception as e:
            print(f"Error guardando chat {chat_name} de {username}: {e}")
