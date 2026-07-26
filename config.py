"""All settings in one place. Secrets and machine-specific values come from
.env (gitignored) via python-dotenv; everything else is a plain constant here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")  # default: Daniel

# Telegram — second I/O channel (text-mode equivalent of the F8 PTT loop).
# Secret pattern mirrors the API keys above: values live in .env (gitignored),
# loaded here, never committed. TELEGRAM_CHAT_ID is the single allowlisted
# account (mine) — the poller silently ignores every other chat_id.
#   TELEGRAM_BOT_TOKEN: from @BotFather after /newbot
#   TELEGRAM_CHAT_ID:   my numeric Telegram user id (from @userinfobot)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # kept as str; compared against str(update chat id)

# Models — dynamic routing:
#   BASE_MODEL handles everyday turns (fast + cheap).
#   SMART_MODEL is used when the request needs heavy reasoning (coding, analysis, planning),
#   or when you explicitly ask JARVIS to "think hard" / "use opus".
BASE_MODEL = "claude-sonnet-4-6"
SMART_MODEL = "claude-opus-4-8"
MAX_TOOL_ROUNDS = 8        # safety cap on tool-use loops per turn

# Push-to-talk
PTT_KEY = "f8"             # hold this key to speak, release to send

# Whisper STT
WHISPER_MODEL = "base"     # options: tiny, base, small, medium (larger = more accurate, slower)

# Memory
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory", "jarvis_memory.json")
SUMMARIZE_EVERY = 20       # auto-summarize conversation every N turns

# Tasks — user-initiated reminders (read by the nudge scheduler, nudge.py)
TASKS_FILE = os.path.join(os.path.dirname(__file__), "memory", "tasks.json")

# Obsidian vault — tools are sandboxed to this directory only (see tools.py).
# Path lives in .env (machine-specific + personal); empty disables vault tools.
VAULT_PATH = os.getenv("VAULT_PATH", "")

# Morning briefing — weather location (Open-Meteo, no API key needed).
# Coordinates live in .env (home location — not something to commit).
BRIEFING_LAT = float(os.getenv("BRIEFING_LAT", "40.7128"))
BRIEFING_LON = float(os.getenv("BRIEFING_LON", "-74.0060"))
BRIEFING_PLACE = os.getenv("BRIEFING_PLACE", "New York, NY")
