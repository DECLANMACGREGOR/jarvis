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

# Clap detection tuning
CLAP_THRESHOLD = 0.008     # amplitude threshold (0.0–1.0); lower = more sensitive
CLAP_SPIKE_RATIO = 6.0     # clap must be this many times louder than background noise
CLAP_WINDOW_MIN = 0.15     # min seconds between two claps
CLAP_WINDOW_MAX = 1.2      # max seconds between two claps
SILENCE_TIMEOUT = 1.5      # seconds of silence before ending recording

# Whisper STT
WHISPER_MODEL = "base"     # options: tiny, base, small, medium (larger = more accurate, slower)

# Memory
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory", "jarvis_memory.json")
SUMMARIZE_EVERY = 20       # auto-summarize conversation every N turns
