# JARVIS — Iron Man Voice Agent

## Goal
A locally-running, privately-sourced JARVIS agent activated by push-to-talk. Sounds, feels, and behaves like the JARVIS from Iron Man — calm, precise, dry wit, always useful.

## Stack
- **AI**: Claude API with dynamic model routing — `claude-sonnet-4-6` for everyday turns, auto-escalates to `claude-opus-4-8` for heavy reasoning (coding, analysis, or say "think hard"). Prompt caching + auto-summarization.
- **Activation**: Push-to-talk — hold `PTT_KEY` (default F8, set in `config.py`) while speaking, release to send. No wake word, no ambient listening.
- **STT**: `faster-whisper` (local, offline, private)
- **TTS**: ElevenLabs (`eleven_turbo_v2_5`, sentence-chunked streaming)
- **Tools**: web search (DuckDuckGo), open apps/files, run code/shell, update memory
- **Memory**: JSON file — persists facts + conversation summary across sessions

## File Map
| File | Role |
|------|------|
| `main.py` | Entry point — full PTT→listen→think→speak loop |
| `listener.py` | Push-to-talk key detection + voice recording |
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
- PTT key: `PTT_KEY` in `config.py` (default "f8"; any `keyboard`-lib key name works)
- Voice: swap `ELEVENLABS_VOICE_ID` in `.env`
- Whisper accuracy: change `WHISPER_MODEL` to `small` or `medium`
- Auto-summarize interval: `SUMMARIZE_EVERY` (default: 20 turns)

## Character
JARVIS speaks with calm confidence, dry wit, and precision. Concise unless depth is needed. Never breaks character. Does not mention Claude or Anthropic unless directly asked.
