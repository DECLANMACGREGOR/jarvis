import json
import os
from config import MEMORY_FILE

_DEFAULT = {"summary": "", "user_facts": [], "turn_count": 0}


def load() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return dict(_DEFAULT, user_facts=[])
    try:
        # encoding is explicit: Windows defaults open() to cp1252, which silently
        # decodes UTF-8 fact text into mojibake that the next save() bakes in.
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            mem = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # A crash mid-write can truncate the file. Preserve the evidence,
        # start fresh, keep JARVIS runnable instead of erroring every turn.
        backup = MEMORY_FILE + ".corrupt"
        try:
            os.replace(MEMORY_FILE, backup)
            print(f"[JARVIS] Memory file unreadable ({e}) — backed up to {backup}, starting fresh.")
        except OSError:
            print(f"[JARVIS] Memory file unreadable ({e}) — starting fresh.")
        return dict(_DEFAULT, user_facts=[])
    # Tolerate partial/hand-edited files
    for key, default in _DEFAULT.items():
        mem.setdefault(key, [] if isinstance(default, list) else default)
    return mem


def save(mem: dict) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    # Atomic write: never leave a truncated file if we crash mid-dump.
    tmp = MEMORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)
    os.replace(tmp, MEMORY_FILE)


def add_fact(fact: str) -> None:
    mem = load()
    if fact not in mem["user_facts"]:
        mem["user_facts"].append(fact)
    save(mem)


def increment_turn() -> int:
    mem = load()
    mem["turn_count"] += 1
    save(mem)
    return mem["turn_count"]


def write_summary(summary: str) -> None:
    mem = load()
    mem["summary"] = summary
    save(mem)


def build_memory_context(mem: dict) -> str:
    parts = []
    if mem.get("summary"):
        parts.append(f"Conversation summary: {mem['summary']}")
    if mem.get("user_facts"):
        facts = "\n".join(f"- {f}" for f in mem["user_facts"])
        parts.append(f"Known facts about the user:\n{facts}")
    return "\n\n".join(parts)
