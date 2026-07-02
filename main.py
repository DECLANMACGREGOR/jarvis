import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import ANTHROPIC_API_KEY, ELEVENLABS_API_KEY
import listener
import stt
import brain
import voice
import memory as mem_module
import hud


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
    if mem.get("summary"):
        print(f"  Memory loaded: {mem['turn_count']} prior turns")
    print("  Double-clap to activate.\n")

    # Start HUD window
    hud.start()
    hud.update(status="STANDBY", turn=mem.get("turn_count", 0))

    # Warm up Whisper before first use
    stt._get_model()  # type: ignore[attr-defined]
    hud.update(status="LISTENING")

    while True:
        try:
            hud.update(status="LISTENING", command="", response="")
            listener.wait_for_clap()

            hud.update(status="ACTIVATED", response="Hello, sir. How can I assist you?")
            greeting = "Hello, sir. JARVIS is online. How can I assist you?"
            print(f"[JARVIS] {greeting}")
            voice.speak(greeting)

            print("[JARVIS] Activated — listening for your command.")
            audio = listener.record_until_silence()

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
            print(f"[JARVIS] Error: {e}")
            hud.update(status="ERROR")
            continue


if __name__ == "__main__":
    main()
