from chat_client import __main__ as entry


def test_main_builds_the_app_runs_it_and_always_cleans_up(monkeypatch):
    events = []

    class FakeApp:
        def __init__(self, screen, address):
            events.append(("init", address.host, address.port))

        def run(self):
            events.append("run")
            raise KeyboardInterrupt  # Ctrl+C is a normal way to leave

        def cleanup(self):
            events.append("cleanup")

    monkeypatch.setattr(entry, "MessagingApp", FakeApp)
    monkeypatch.setattr(entry.curses, "wrapper", lambda function: function(object()))
    monkeypatch.setattr(
        entry,
        "resolve_address",
        lambda: entry.resolve_address.__wrapped__ if False else type("A", (), {"host": "h", "port": 1})(),
    )
    assert entry.main() == 0
    assert events == [("init", "h", 1), "run", "cleanup"]
