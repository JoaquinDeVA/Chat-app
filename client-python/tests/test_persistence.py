from .conftest import message


def test_a_fresh_user_has_nothing_and_syncs_from_the_epoch(persistence):
    assert persistence.load_user_conversations("ana") == {}
    assert persistence.load_last_sync("ana") == "1970-01-01 00:00:00"


def test_conversations_roundtrip_including_unicode(persistence):
    chats = {"équipe": [message(contents="hola ñ 😀", chat="équipe")], "b": []}
    persistence.save_user_conversations("ana", chats)
    loaded = persistence.load_user_conversations("ana")
    assert loaded["équipe"][0]["contents"] == "hola ñ 😀"


def test_last_sync_only_moves_forward(persistence):
    persistence.update_user_chat("ana", "a", [message(sent="2026-05-04 10:00:00")])
    persistence.update_user_chat("ana", "b", [message(sent="2026-05-01 10:00:00")])
    assert persistence.load_last_sync("ana") == "2026-05-04 10:00:00"
    persistence.update_user_chat("ana", "a", [message(sent="2026-05-04 10:00:00"), message(sent="2026-05-05 09:00:00")])
    assert persistence.load_last_sync("ana") == "2026-05-05 09:00:00"


def test_undelivered_messages_are_not_stored(persistence):
    persistence.update_user_chat("ana", "a", [message(contents="ok"), message(contents="lost", failed=True)])
    assert [m["contents"] for m in persistence.load_user_conversations("ana")["a"]] == ["ok"]


def test_names_are_sanitized_so_they_cannot_escape_the_folder(persistence, tmp_path):
    persistence.update_user_chat("../evil", "../../x", [message()])
    assert not (tmp_path / "x.txt").exists()
    assert all(tmp_path in path.parents for path in (tmp_path / "chats").rglob("*") if path.is_file())


def test_unparsable_lines_of_other_formats_are_kept_as_text(persistence):
    user_dir = persistence.base_dir / "ana"
    user_dir.mkdir(parents=True)
    (user_dir / "old.txt").write_text('ana: plain text\n{"author": "ben"}\n\n[1, 2]\n', encoding="utf-8")
    assert persistence.load_user_conversations("ana")["old"] == ["ana: plain text", {"author": "ben"}, "[1, 2]"]


def test_images_live_in_the_users_folder(persistence):
    assert persistence.images_dir("ana") == persistence.base_dir / "ana" / "images"
