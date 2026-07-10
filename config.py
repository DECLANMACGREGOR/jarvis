import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")  # default: Daniel

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

# Obsidian vault — tools are sandboxed to this directory only (see tools.py)
VAULT_PATH = r"C:\Users\declan macgregor\Documents\DECLAN-MACGREGOR"

# Morning briefing — weather location (Open-Meteo, no API key needed).
# UPDATE on Aug 15: Stockholm is lat 59.3293, lon 18.0686, "Stockholm"
BRIEFING_LAT = 40.7128
BRIEFING_LON = -74.0060
BRIEFING_PLACE = "New York, NY"
