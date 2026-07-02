import json
import os
from config import MEMORY_FILE


def load() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return {"summary": "", "user_facts": [], "turn_count": 0}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save(mem: dict) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)


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
