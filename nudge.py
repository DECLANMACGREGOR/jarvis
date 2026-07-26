"""
nudge.py — JARVIS's bounded task/deadline reminder scheduler.

A background daemon thread wakes every NUDGE_POLL_S seconds, reads the tasks the
user has explicitly stored (via the add_task tool), and delivers a reminder when
a deadline crosses a threshold: 24h out, 3h out, or overdue — each fired at most
once per task (tracked by the per-task `notified` flags in tasks.json).

STRUCTURAL NO-TOOLS GUARANTEE (the whole point of this module):
- The nudge is composed by _compose(), a pure string template. There is no
  model call here — no _client.messages.create, no `tools=`, nothing.
- This module imports ONLY: time, threading, datetime, tasks, presence, voice,
  hud, telegram_io. It does NOT import brain or tools, and its call graph never
  reaches brain.think() or tools.dispatch(). So the reminder path is
  architecturally incapable of calling a tool or acting on a task — it can read
  tasks and flip a `notified` flag (tasks.mark_notified), and it can SAY things
  (TTS / HUD / Telegram). Nothing else. It never creates, infers, or executes
  tasks. (telegram_io transitively imports brain for the *interactive* channel;
  the nudge path here only ever calls telegram_io.send_message, an HTTP POST.)

Delivery routing: same content either way — TTS + HUD if the user is present at
the PC (recent push-to-talk), else Telegram. During the multi-month away period
there is no PTT, so every reminder routes to Telegram automatically.
"""

import threading
import time
from datetime import datetime

import tasks
import presence
import voice
import hud
import telegram_io

NUDGE_POLL_S = 60          # how often to sweep tasks for due deadlines
_H24 = 24 * 3600
_H3 = 3 * 3600


def _fmt_due(due_iso: str) -> str:
    """Human-friendly due time for the spoken/typed reminder; ISO as fallback."""
    try:
        dt = datetime.fromisoformat(due_iso)
    except (ValueError, TypeError):
        return due_iso
    # e.g. "Fri Aug 14, 5:00 PM" — strip the leading zero on the day if present.
    return dt.strftime("%a %b %d, %I:%M %p").replace(" 0", " ", 1)


def _compose(task: dict, stage: str) -> str:
    """Pure template — no model, no tools. This is the no-tools guarantee in code."""
    text = task.get("text", "a task")
    due = _fmt_due(task.get("due_iso", ""))
    if stage == "overdue":
        return f"Reminder, sir: '{text}' was due {due} and is now overdue."
    if stage == "3h":
        return f"Reminder, sir: '{text}' is due within three hours — {due}."
    return f"Heads up, sir: '{text}' is due within twenty-four hours — {due}."


def _deliver(text: str) -> bool:
    """Route one reminder: TTS + HUD if present, else Telegram. Telegram is the
    fallback if the present-path (audio) fails, so a reminder is never silently
    lost.

    Returns True only if the reminder actually reached the user — the caller
    uses this to decide whether to burn the stage's `notified` flag.

    The barge-in case is why this returns a bool at all: if the user is holding
    PTT when the nudge starts playing, voice.speak() cancels mid-sentence and
    returns normally, having said nothing audible. Reporting that as delivered
    would mark the stage notified and lose the reminder permanently. We do NOT
    fall back to Telegram here — a barge-in means the user is sitting right at
    the mic, so the correct move is to retry on the next sweep, not to text
    someone who is in the room.
    """
    print(f"[JARVIS] NUDGE: {text}")
    if presence.is_present():
        try:
            hud.update(status="SPEAKING", response=text)
            spoken = voice.speak(text)  # serialized against live responses via voice._speak_lock
            if not spoken:
                print("[JARVIS] Nudge cut off by push-to-talk — retrying next sweep.")
            return spoken
        except Exception as e:
            print(f"[JARVIS] Nudge TTS failed ({e}) — falling back to Telegram.")
    telegram_io.send_message(text)
    return True


def _stage_for(delta_s: float) -> str | None:
    """Current (mutually exclusive) threshold for a time-to-due in seconds.

    Because stages are mutually exclusive and time only decreases, a task walks
    24h -> 3h -> overdue and each stage is entered at most once; the notified
    flag then guarantees at most one nudge per stage. A task created already
    inside a horizon simply starts at that stage (a 2h-out task never fires a
    24h nudge — it's moot)."""
    if delta_s <= 0:
        return "overdue"
    if delta_s <= _H3:
        return "3h"
    if delta_s <= _H24:
        return "24h"
    return None


def _check_once() -> None:
    """One sweep: fire the due, unfired reminders. Any per-task error is isolated
    so one bad record can't stop the sweep."""
    data = tasks.load()
    now = datetime.now()
    for t in data.get("tasks", []):
        try:
            if t.get("done"):
                continue
            due = datetime.fromisoformat(t.get("due_iso", ""))
            stage = _stage_for((due - now).total_seconds())
            if stage is None:
                continue
            if t.get("notified", {}).get(stage):
                continue  # already nudged for this stage
            if _deliver(_compose(t, stage)):
                # Persist dedup only for a reminder that actually landed. An
                # undelivered one leaves the flag false and re-fires next sweep.
                tasks.mark_notified(t["id"], stage)
        except (ValueError, TypeError, KeyError) as e:
            print(f"[JARVIS] Nudge skipped a task ({type(e).__name__}: {e}).")
            continue


def _run() -> None:
    print("[JARVIS] Nudge scheduler online.")
    while True:
        time.sleep(NUDGE_POLL_S)  # sleep first: avoids a cold-start burst
        try:
            _check_once()
        except Exception as e:
            print(f"[JARVIS] Nudge sweep error — {type(e).__name__}: {e}")


# ── Module-level singleton ─────────────────────────────────────────────────────

_thread: threading.Thread | None = None


def start() -> None:
    global _thread
    if _thread is not None:
        return
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
