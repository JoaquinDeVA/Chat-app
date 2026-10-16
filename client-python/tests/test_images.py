import base64

from chat_client import images


def write_png(path, size=100):
    path.write_bytes(b"\x89PNG" + b"x" * size)
    return path


def test_formats_are_told_apart_and_text_with_pipes_is_not_an_image():
    wire = f"{images.IMG_TAG}|.png|AAAA"
    ref = f"{images.IMG_TAG}|abc.png"
    assert images.is_wire_format(wire) and not images.is_image_ref(wire)
    assert images.is_image_ref(ref) and not images.is_wire_format(ref)
    for text in ("|a|b", "a|b|c", "plain", "", None, 5):
        assert not images.is_wire_format(text) and not images.is_image_ref(text)


def test_encode_then_decode_restores_the_bytes(tmp_path):
    source = write_png(tmp_path / "pic.PNG")
    wire = images.encode_file(source)
    assert wire.startswith(f"{images.IMG_TAG}|.png|")
    ref = images.decode_and_save(wire, tmp_path / "store")
    assert images.is_image_ref(ref)
    assert (tmp_path / "store" / images.get_filename(ref)).read_bytes() == source.read_bytes()


def test_unsupported_missing_and_oversized_files_are_refused(tmp_path, monkeypatch):
    assert images.encode_file(tmp_path / "notes.txt") is None
    assert images.encode_file(tmp_path / "missing.png") is None
    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 10)
    assert images.encode_file(write_png(tmp_path / "big.png", 100)) is None


def test_corrupt_data_is_reported_in_text_and_non_wire_text_is_untouched(tmp_path):
    assert images.decode_and_save(f"{images.IMG_TAG}|.png|not base64!!", tmp_path) == "[image could not be decoded]"
    assert images.decode_and_save("hello", tmp_path) == "hello"
    assert not list(tmp_path.iterdir())


def test_every_decode_uses_a_new_name(tmp_path):
    wire = f"{images.IMG_TAG}|.gif|" + base64.b64encode(b"GIF89a").decode()
    assert images.decode_and_save(wire, tmp_path) != images.decode_and_save(wire, tmp_path)


def test_open_image_needs_an_existing_file(tmp_path):
    assert not images.open_image(f"{images.IMG_TAG}|nope.png", tmp_path)
    assert not images.open_image("plain", tmp_path)
