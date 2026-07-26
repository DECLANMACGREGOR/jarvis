"""Presence heuristic — is the user "at the PC" right now?

The nudge scheduler (nudge.py) uses this to decide whether to deliver a
reminder via TTS/HUD (user present) or Telegram (user away). The
committed heuristic is **last-PTT-interaction age**: the user is "present" if
they used push-to-talk within the last PRESENCE_WINDOW_S seconds.

Rationale (decided upstream, not re-litigated here): last-PTT-age measures
engagement with JARVIS specifically, and it degrades correctly for the
multi-month away period — no PTT ever means always "away", so reminders
always route to Telegram. The alternative, Windows GetLastInputInfo, would
conflate general PC use (typing, browsing) with actually talking to JARVIS.
"""

import time

_last_ptt: float | None = None  # monotonic timestamp of the last PTT interaction; None = never

PRESENCE_WINDOW_S = 300  # 5 minutes


def mark_ptt() -> None:
    """Record that a genuine PTT voice interaction just happened."""
    global _last_ptt
    _last_ptt = time.monotonic()


def is_present(window_seconds: float = PRESENCE_WINDOW_S) -> bool:
    """True iff a PTT interaction happened within the last `window_seconds`.

    Thread-safety: this is read from the scheduler thread while mark_ptt()
    writes from the main thread. A single float read/write is atomic under
    CPython's GIL, so no lock is needed.
    """
    return _last_ptt is not None and (time.monotonic() - _last_ptt) < window_seconds
