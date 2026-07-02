# JARVIS — Iron Man Voice Agent

## Goal
A locally-running, privately-sourced JARVIS agent activated by a double-clap sound cue. Sounds, feels, and behaves like the JARVIS from Iron Man — calm, precise, dry wit, always useful.

## Stack
- **AI**: Claude API (`claude-opus-4-7`) with prompt caching + auto-summarization
- **Wake word**: Double-clap detection via `sounddevice` (real-time amplitude transient detection)
- **STT**: `faster-whisper` (local, offline, private)
- **TTS**: ElevenLabs (`eleven_turbo_v2_5`, sentence-chunked streaming)
- **Tools**: web search (DuckDuckGo), open apps/files, run code/shell, update memory
- **Memory**: JSON file — persists facts + conversation summary across sessions

## File Map
| File | Role |
|------|------|
| `main.py` | Entry point — full clap→listen→think→speak loop |
| `listener.py` | Clap detection + voice recording |
| `stt.py` | Whisper speech-to-text |
| `brain.py` | Claude API, tool orchestration, auto-summarize |
| `voice.py` | ElevenLabs TTS + playback |
| `tools.py` | web_search, open_item, run_code, update_memory |
| `memory.py` | Load/save persistent memory |
| `config.py` | All settings + API keys via .env |
| `memory/jarvis_memory.json` | Persistent facts + conversation summary |

## Run
```powershell
cd "C:\Users\declan macgregor\Opus4.6\jarvis"
C:\jv\Scripts\python.exe main.py
```
> Note: Must use `C:\jv\Scripts\python.exe` — deps are installed in the `C:\jv` venv (Windows long-path workaround).

## Tuning
- Clap sensitivity: `CLAP_THRESHOLD` in `config.py` (lower = more sensitive)
- Voice: swap `ELEVENLABS_VOICE_ID` in `.env`
- Whisper accuracy: change `WHISPER_MODEL` to `small` or `medium`
- Auto-summarize interval: `SUMMARIZE_EVERY` (default: 20 turns)

## Character
JARVIS speaks with calm confidence, dry wit, and precision. Concise unless depth is needed. Never breaks character. Does not mention Claude or Anthropic unless directly asked.
