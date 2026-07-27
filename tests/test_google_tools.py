"""Tests for google_tools: the startup handshake and the datetime formatting
Google actually accepts.

Google is an optional integration, so the one thing warm_up must never do is
take JARVIS down with it. Each test pins one way it could fail loudly instead
of degrading quietly.
"""
import re

import google_tools


# ── _to_rfc3339: the offset Google needs ─────────────────────────────────────
# Assertions stay offset-agnostic on purpose — CI runs in UTC, the author's
# machine in US/Eastern, and both must pass.

def test_naive_local_time_gains_an_offset():
    # The bug: Windows names its zone "Eastern Daylight Time", which Google
    # can't parse, so events landed at the wrong hour. An explicit offset
    # needs no timezone database.
    out = google_tools._to_rfc3339("2026-07-27T15:00:00")
    assert out.startswith("2026-07-27T15:00:00")
    assert re.search(r"([+-]\d{2}:\d{2}|Z)$", out), f"no UTC offset in {out!r}"


def test_existing_offset_is_preserved():
    assert google_tools._to_rfc3339("2026-07-27T15:00:00-04:00") == "2026-07-27T15:00:00-04:00"


def test_wall_clock_time_is_never_shifted():
    # Whatever the offset, 3pm must stay 3pm — the offset annotates the time,
    # it does not convert it.
    for stamp in ("2026-07-27T15:00:00", "2027-01-15T09:30:00"):
        assert google_tools._to_rfc3339(stamp).startswith(stamp)


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
