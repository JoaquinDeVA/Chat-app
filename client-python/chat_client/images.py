"""Images inside messages.

An image travels as an ordinary text message in the *wire format* ``[[img]]|.ext|<base64>``. When a
client receives or sends one it saves the file under a name of its own and keeps the *reference*
``[[img]]|<uuid>.ext`` as the message contents.
"""

import base64
import binascii
import logging
import subprocess
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

IMG_TAG = "[[img]]"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
#: Largest file that can be sent: the database column holds 16 MB and base64 adds a third.
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def is_wire_format(text: object) -> bool:
    """True for ``[[img]]|.ext|base64``: the picture is still inside the text."""
    return isinstance(text, str) and text.startswith(IMG_TAG + "|") and text.count("|") == 2


def is_image_ref(text: object) -> bool:
    """True for ``[[img]]|uuid.ext``: the picture is already stored on disk."""
    return isinstance(text, str) and text.startswith(IMG_TAG + "|") and text.count("|") == 1


def get_filename(text: str) -> str:
    """File name (``uuid.ext``) of a reference, or of a wire payload's extension; ``""`` if neither."""
    parts = text.split("|", 2)
    return parts[1] if len(parts) >= 2 else ""


def encode_file(path: str | Path) -> str | None:
    """Reads an image and returns its wire payload.

    :return: The payload, or ``None`` if the file is not a supported image, is too big or
        cannot be read.
    """
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None
    try:
        if path.stat().st_size > MAX_IMAGE_BYTES:
            return None
        data = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return None
    return f"{IMG_TAG}|{path.suffix.lower()}|{data}"


def decode_and_save(wire: str, images_dir: Path) -> str:
    """Stores the picture of a wire payload under a fresh name and returns its reference.

    :return: ``[[img]]|<uuid>.ext``; ``wire`` unchanged if it is not a wire payload, and a plain
        text notice if the data is corrupt.
    """
    if not is_wire_format(wire):
        return wire
    _, extension, data = wire.split("|", 2)
    try:
        content = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        log.warning("received an image that is not valid base64")
        return "[image could not be decoded]"
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    (images_dir / filename).write_bytes(content)
    return f"{IMG_TAG}|{filename}"


def open_image(ref: str, images_dir: Path) -> bool:
    """Opens the image with the system viewer.

    :return: Whether a viewer was started.
    """
    filename = get_filename(ref)
    path = images_dir / filename
    if not filename or not path.is_file():
        return False
    for command in ("xdg-open", "open"):
        try:
            subprocess.Popen([command, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
    return False
