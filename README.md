# J.A.R.V.I.S. — a local push-to-talk voice agent

A locally-running, private, Iron Man-style voice assistant for Windows. Hold a key, speak, release — JARVIS transcribes locally, thinks with Claude, acts through a permission-gated toolset, and answers out loud in a British voice, with a floating HUD tracking every turn.

> Speech-to-text is fully local and the mic is only open while the key is held. The only data that leaves the machine is the text sent to the Claude and ElevenLabs APIs, plus the tool calls you approve.

## The loop

```
hold F8 ──► record mic ──► faster-whisper (local STT)
                                   │
                             brain.think()
                     Claude + tools, serialized turns
                                   │
                        ElevenLabs TTS (streaming)
              hold F8 mid-sentence to barge in and cut it off
```

## Features

- **Push-to-talk, no wake word** — the mic records only while `F8` is held. No ambient listening, ever.
- **Barge-in** — holding PTT while JARVIS speaks cuts the response off immediately and cancels the remaining TTS fetches.
- **Dynamic model routing** — everyday turns run on a fast Claude model; requests that need heavy reasoning ("think hard", coding, analysis) auto-escalate to a stronger one. Prompt caching plus auto-summarization every 20 turns keep token usage flat over long sessions.
- **Tools** — web search (DuckDuckGo), open apps/files, run Python/shell, persistent memory, Obsidian vault read/search/write, webcam capture with local face recognition, Google Calendar, Gmail read + draft, user-initiated task reminders, morning briefing (weather + calendar).
- **Vision** — one-shot webcam capture (OpenCV) with YuNet + SFace face recognition, entirely on-CPU. Only 128-float embeddings are stored — never photos.
- **Second channel: Telegram** — text JARVIS from a phone; same brain, same tool gates, single-chat allowlist.
- **Nudges** — a background scheduler reminds you about your tasks at 24h / 3h / overdue, routed to speakers if you're at the PC or Telegram if you're not.
- **HUD** — a floating tkinter window with live status, the current exchange, and an animated arc reactor. (`hud_v2_neural_mockup.py` is a standalone PyQt6 design mockup for the next-generation HUD.)

## Safety design

This project treats a tool-using voice agent as an untrusted-input problem, and the guardrails are structural rather than prompt-only:

- **Permission gate on dangerous tools.** `run_code`, `open_item`, vault writes, and calendar deletes require an explicit spoken *yes* (or a typed `YES` over Telegram) before executing — deny by default, timeout = deny, and the request always states what will actually run.
- **Draft-only email, enforced in code.** No function that can send email exists in the codebase; JARVIS can only create Gmail drafts for human review.
- **Structural no-tools guarantee for reminders.** The nudge scheduler composes reminders from pure string templates and its import graph cannot reach the model or the tool dispatcher — it is architecturally incapable of acting on a task.
- **Untrusted-data framing.** Web search results and email bodies are wrapped as data-not-instructions before the model sees them, cutting off the prompt-injection → code-execution path.
- **Allowlisted Telegram.** One hardcoded chat ID; every other sender is silently dropped before any processing.
- **Audible side effects.** Camera captures, memory writes, calendar creates, and email drafts are announced out loud — nothing real-world happens silently.
- **Sandboxed vault access.** Vault tools resolve paths against the vault root and refuse anything that escapes it.

## File map

| File | Role |
|------|------|
| `main.py` | Entry point — the PTT → listen → think → speak loop |
| `listener.py` | Push-to-talk key detection + mic recording |
| `stt.py` | faster-whisper speech-to-text (local, CPU) |
| `brain.py` | Claude orchestration: routing, tool loop, auto-summarize |
| `voice.py` | ElevenLabs TTS, sentence-chunked streaming, barge-in |
| `tools.py` | Tool schemas + implementations, permission gate |
| `google_tools.py` | Google Calendar + Gmail (read/draft only) |
| `briefing.py` | Morning briefing: datetime, weather, calendar |
| `vision.py` | Webcam capture + YuNet/SFace face recognition |
| `memory.py` | Persistent JSON memory (facts + summary) |
| `tasks.py` | User-initiated task/reminder store |
| `nudge.py` | Background deadline-reminder scheduler |
| `presence.py` | At-the-PC heuristic for reminder routing |
| `telegram_io.py` | Telegram text channel (allowlisted) |
| `hud.py` | Tkinter HUD |
| `config.py` | Settings; secrets and locations via `.env` |

## Setup

Windows-only (uses `winreg`, `os.startfile`, and the `keyboard` package).

1. **Python 3.12+ venv** — install deps with `pip install -r requirements.txt`. If ElevenLabs install fails with path-length errors, create the venv somewhere short (e.g. `C:\jv`) — Windows' 260-char path limit.
2. **Keys** — copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` and `ELEVENLABS_API_KEY` (plus optional Telegram/vault/location values).
3. **Google (optional)** — create an OAuth desktop client in Google Cloud Console with the Calendar + Gmail APIs enabled, save it as `credentials.json` in the project root, then run `python google_tools.py` for a one-time browser consent and self-test.
4. **Run** — `python main.py`. First run downloads the Whisper model (~150 MB) and, on first camera use, the two face-recognition ONNX models.

## Usage

- Hold **F8** (configurable via `PTT_KEY` in `config.py`), speak, release.
- Interrupt JARVIS at any time by holding F8 while it speaks.
- Try: *"what's on my calendar tomorrow?"*, *"search my vault for interview prep"*, *"remind me to submit the form by Friday 5pm"*, *"who's on camera?"*, *"morning briefing"*.
- Say *"think hard"* to force escalation to the stronger model.

## Privacy

- STT is local; audio never leaves the machine.
- No ambient listening — the mic is open only while PTT is held.
- Face recognition stores embeddings only (not reconstructable into images), locally.
- Memory, tasks, tokens, and enrolled faces live in the gitignored `memory/` directory.
- Home coordinates and vault path are configured through `.env`, not committed.

## Roadmap

- **Reel-to-AI** (in progress on a feature branch): a Gmail-fed queue that turns saved Instagram reels into extracted, versioned agent skills via yt-dlp + vision.
- HUD v2 — wire the Neural Constellation mockup to live brain/tool events.
- Voice cloning for a closer JARVIS timbre.

## License

[MIT](LICENSE)
