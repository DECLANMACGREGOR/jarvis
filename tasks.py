"""
tasks.py — JARVIS's user-initiated task/reminder store.

Storage model mirrors memory.py exactly: corrupt-file recovery (rename to
.corrupt, print a notice, start fresh) and atomic writes (dump to .tmp, then
os.replace). A LATER step adds a background scheduler that reads these tasks
and sends reminders based on the `notified` thresholds; this module only
initializes that field — no scheduling/nudge logic here.

Tasks are USER-INITIATED ONLY: JARVIS must never create a task on its own
inference — only in direct response to the user explicitly asking to be
reminded of something (enforced in brain.py's SYSTEM_PROMPT, not here).
"""

import json
import os
import threading
from datetime import datetime

from config import TASKS_FILE

_DEFAULT = {"tasks": []}

# Serializes read-modify-write sequences. Step 7 adds a second writer — the
# nudge scheduler thread (mark_notified) — running concurrently with add/
# complete/delete from the voice and Telegram threads. Without this, a
# scheduler save could clobber a just-added task (lost update). Reads
# (load/list_tasks) don't need it: save() is atomic (tmp + os.replace), so a
# reader always sees a whole file, never a partial one.
_lock = threading.Lock()


def load() -> dict:
    if not os.path.exists(TASKS_FILE):
        return dict(_DEFAULT, tasks=[])
    try:
        # encoding is explicit: Windows defaults open() to cp1252, which silently
        # decodes UTF-8 task text (em dashes, accents) into mojibake that the
        # next save() then bakes into the file permanently.
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # A crash mid-write can truncate the file. Preserve the evidence,
        # start fresh, keep JARVIS runnable instead of erroring every turn.
        backup = TASKS_FILE + ".corrupt"
        try:
            os.replace(TASKS_FILE, backup)
            print(f"[JARVIS] Tasks file unreadable ({e}) — backed up to {backup}, starting fresh.")
        except OSError:
            print(f"[JARVIS] Tasks file unreadable ({e}) — starting fresh.")
        return dict(_DEFAULT, tasks=[])
    # Tolerate partial/hand-edited files
    for key, default in _DEFAULT.items():
        data.setdefault(key, [] if isinstance(default, list) else default)
    return data


def save(data: dict) -> None:
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    # Atomic write: never leave a truncated file if we crash mid-dump.
    tmp = TASKS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, TASKS_FILE)


def add_task(text: str, due_iso: str) -> str:
    with _lock:
        data = load()
        tasks = data["tasks"]
        next_id = max((t.get("id", 0) for t in tasks), default=0) + 1
        task = {
            "id": next_id,
            "text": text,
            "due_iso": due_iso,
            "created_iso": datetime.now().isoformat(timespec="seconds"),
            "done": False,
            "notified": {"24h": False, "3h": False, "overdue": False},
        }
        tasks.append(task)
        save(data)
    return f"Task #{next_id} saved: {text} (due {due_iso})."


def list_tasks(include_done: bool = False) -> str:
    data = load()
    tasks = data["tasks"]
    if not include_done:
        tasks = [t for t in tasks if not t.get("done")]
    if not tasks:
        return "No tasks."
    lines = []
    for t in tasks:
        state = "done" if t.get("done") else "pending"
        lines.append(f"#{t['id']} [{state}] {t['text']} — due {t['due_iso']}")
    return "\n".join(lines)


def complete_task(task_id: int) -> str:
    with _lock:
        data = load()
        for t in data["tasks"]:
            if t.get("id") == task_id:
                t["done"] = True
                save(data)
                return f"Task #{task_id} marked complete: {t['text']}."
    return f"No task found with id #{task_id}."


def delete_task(task_id: int) -> str:
    with _lock:
        data = load()
        tasks = data["tasks"]
        for i, t in enumerate(tasks):
            if t.get("id") == task_id:
                removed = tasks.pop(i)
                save(data)
                return f"Task #{task_id} deleted: {removed['text']}."
    return f"No task found with id #{task_id}."


def mark_notified(task_id: int, threshold: str) -> None:
    """Flip one per-task nudge dedup flag. This is the ONLY write the nudge
    scheduler makes — it never creates, completes, or deletes a task. Kept
    narrow on purpose: the reminder path can record that it reminded, nothing
    more."""
    with _lock:
        data = load()
        for t in data["tasks"]:
            if t.get("id") == task_id:
                t.setdefault("notified", {})[threshold] = True
                save(data)
                return
