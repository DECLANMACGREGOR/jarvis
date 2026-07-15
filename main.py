import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import config
from config import ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, PTT_KEY
import listener
import stt
import brain
import voice
import tools as tool_module
import memory as mem_module
import hud
import telegram_io


def check_env() -> bool:
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not ELEVENLABS_API_KEY:
        missing.append("ELEVENLABS_API_KEY")
    if missing:
        print(f"[JARVIS] Missing env vars: {', '.join(missing)}")
        print("[JARVIS] Copy .env.example to .env and fill in your API keys.")
        return False
    return True


def main():
    if not check_env():
        sys.exit(1)

    mem = mem_module.load()
    print("\n" + "=" * 50)
    print("  J.A.R.V.I.S. — Online")
    print("=" * 50)
    print(f"  Routing : {config.BASE_MODEL}  →  {config.SMART_MODEL} (heavy tasks)")
    print(f"  Tools   : {len(tool_module.TOOL_DEFINITIONS)} loaded — dangerous ones voice-gated")
    if mem.get("summary"):
        print(f"  Memory  : {mem['turn_count']} prior turns, {len(mem.get('user_facts', []))} saved facts")
    print(f"  Hold [{PTT_KEY.upper()}] to speak. Hold it mid-response to interrupt.\n")

    # Start HUD window
    hud.start()
    hud.update(status="STANDBY", turn=mem.get("turn_count", 0))
    telegram_io.start()

    # Warm up Whisper before first use
    stt._get_model()  # type: ignore[attr-defined]
    hud.update(status="STANDBY")

    while True:
        try:
            hud.update(status="STANDBY", command="", response="")
            print(f"\n[JARVIS] Standby — hold [{PTT_KEY.upper()}] to speak.")
            listener.wait_for_ptt()

            hud.update(status="LISTENING")
            print("[JARVIS] Listening — release the key when finished.")
            audio = listener.record_while_held()

            if audio.size < 8000:  # < 0.5s of audio — accidental tap
                print("[JARVIS] Too short — hold the key while you speak.")
                continue

            text = stt.transcribe(audio)
            if not text:
                print("[JARVIS] Didn't catch that. Try again.")
                continue

            print(f"[You] {text}")
            hud.update(status="PROCESSING", command=text)

            response = brain.think(text)
            print(f"[JARVIS] {response}")

            mem_state = mem_module.load()
            hud.update(status="SPEAKING", response=response, turn=mem_state.get("turn_count", 0))

            voice.speak(response)

        except KeyboardInterrupt:
            print("\n[JARVIS] Shutting down. Goodbye.")
            hud.update(status="OFFLINE")
            break
        except Exception as e:
            print(f"[JARVIS] Error — {type(e).__name__}: {e}")
            hud.update(status="ERROR", response=f"{type(e).__name__}: {e}")
            continue


if __name__ == "__main__":
    main()
