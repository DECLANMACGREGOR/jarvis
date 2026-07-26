"""Tests for google_tools.warm_up() — the startup authentication handshake.

Google is an optional integration, so the one thing warm_up must never do is
take JARVIS down with it. Each test pins one way it could fail loudly instead
of degrading quietly.
"""
import google_tools


def test_missing_credentials_file_is_not_an_error(monkeypatch):
    # No credentials.json = Google was never set up. Report "not connected"
    # without touching the network or raising.
    monkeypatch.setattr(google_tools.os.path, "exists", lambda p: False)
    called = []
    monkeypatch.setattr(google_tools, "_get_service", lambda *a: called.append(a))
    assert google_tools.warm_up() is False
    assert called == []


def test_failed_handshake_is_swallowed(monkeypatch):
    # A dead refresh token with no browser available raises inside _get_service.
    # JARVIS must still boot; the tools retry on first use.
    monkeypatch.setattr(google_tools.os.path, "exists", lambda p: True)

    def boom(*_a):
        raise RuntimeError("no browser")

    monkeypatch.setattr(google_tools, "_get_service", boom)
    assert google_tools.warm_up() is False


def test_success_warms_both_apis(monkeypatch):
    # Both services are built at boot: warming only calendar would leave the
    # first Gmail call of the session paying the discovery fetch mid-turn.
    monkeypatch.setattr(google_tools.os.path, "exists", lambda p: True)
    warmed = []
    monkeypatch.setattr(google_tools, "_get_service", lambda api, ver: warmed.append(api))
    assert google_tools.warm_up() is True
    assert warmed == ["calendar", "gmail"]
