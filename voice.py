"""ElevenLabs TTS with sentence-chunked streaming playback.

Sentences are fetched in a background thread while the previous one plays, so
speech starts fast; holding PTT barges in and cancels the rest (see speak()'s
return-value contract).
"""
import io
import threading
import queue
import re
import time
import pygame
import keyboard
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, PTT_KEY

RESPONSE_DEADLINE_S = 90  # hard cap for speaking one full response, not per sentence

_client: ElevenLabs | None = None
_pygame_ready = False

# Serializes all audio playback. The main loop speaks responses; the nudge
# scheduler speaks reminders from its own thread. Without this they would both
# drive the single pygame mixer at once and garble each other — a nudge instead
# waits for the current response to finish (and vice versa).
_speak_lock = threading.Lock()


def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        _client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _client


def _ensure_pygame() -> None:
    global _pygame_ready
    if not _pygame_ready:
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=2048)
        _pygame_ready = True


def _play_audio_bytes(data: bytes, deadline: float, cancel: threading.Event) -> None:
    _ensure_pygame()
    try:
        buf = io.BytesIO(data)
        pygame.mixer.music.load(buf, "mp3")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy() and time.monotonic() < deadline:
            # Barge-in: pressing PTT while JARVIS speaks cuts it off immediately.
            if keyboard.is_pressed(PTT_KEY):
                cancel.set()
                pygame.mixer.music.stop()
                print("[JARVIS] — interrupted.")
                return
            pygame.time.wait(50)
        if time.monotonic() >= deadline:
            cancel.set()
            pygame.mixer.music.stop()
            print("[JARVIS] Playback deadline reached — cutting response short.")
    except Exception as e:
        print(f"[JARVIS] Playback error: {e}")
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


def _sanitize_for_tts(text: str) -> str:
    """Make model text speakable. Claude sometimes formats with markdown and
    symbols; ElevenLabs reads them literally ("asterisk asterisk seventy-five
    degree-sign F"), so strip formatting and expand symbols on the spoken path
    only — the printed/HUD text keeps the original.
    """
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"[*_`#]+", "", text)                    # markdown markers
    text = text.replace("°F", " degrees Fahrenheit").replace("°C", " degrees Celsius")
    text = text.replace("°", " degrees")
    text = re.sub(r"(?<=\d)%", " percent", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    raw = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    # Merge tiny fragments into their neighbor. Abbreviations like "9:41 P.M."
    # split into shards like "M." — ElevenLabs produces garbled noise on
    # near-empty inputs, so never send a chunk shorter than ~20 chars alone.
    merged: list[str] = []
    for s in raw:
        if merged and (len(s) < 20 or len(merged[-1]) < 20):
            merged[-1] = f"{merged[-1]} {s}"
        else:
            merged.append(s)
    # A lone shard like "M." has no neighbor to merge into — ElevenLabs garbles
    # it, so skip TTS entirely (the text is already printed). Short-but-real
    # lone sentences ("Yes, sir.") synthesize fine and pass through.
    if len(merged) == 1 and len(merged[0]) < 4:
        return []
    return merged


def speak(text: str) -> bool:
    """Convert text to speech and play it. Speaks sentence-by-sentence for low latency.

    Holding the PTT key at any point cuts JARVIS off (barge-in) and cancels
    the remaining TTS fetches. One shared deadline caps the whole response.

    Returns True if the text was delivered to the user's ears, False if it was
    cut short (barge-in or deadline) and they effectively didn't hear it. The
    main loop ignores this — a barged-in response is *meant* to be dropped — but
    the nudge scheduler needs it: an unheard reminder must not be marked as
    delivered, or it is lost forever.
    """
    client = _get_client()
    sentences = _split_sentences(_sanitize_for_tts(text))
    if not sentences:
        return True  # nothing to say (e.g. a lone "M." shard) — not a failure

    with _speak_lock:
        return _speak_locked(client, sentences)


def _speak_locked(client: ElevenLabs, sentences: list[str]) -> bool:
    audio_queue: queue.Queue[bytes | None] = queue.Queue()
    cancel = threading.Event()
    deadline = time.monotonic() + RESPONSE_DEADLINE_S

    def fetch_all():
        for sentence in sentences:
            if cancel.is_set():
                break  # user barged in — don't waste API calls on unheard audio
            try:
                audio = client.text_to_speech.convert(
                    voice_id=ELEVENLABS_VOICE_ID,
                    text=sentence,
                    model_id="eleven_turbo_v2_5",
                    voice_settings=VoiceSettings(
                        stability=0.4,
                        similarity_boost=0.8,
                        style=0.2,
                        use_speaker_boost=True,
                    ),
                    output_format="mp3_44100_128",
                )
                audio_queue.put(b"".join(audio))
            except Exception as e:
                print(f"[JARVIS] TTS error: {e}")
                audio_queue.put(b"")  # skip marker — keep speaking remaining sentences
        audio_queue.put(None)  # sentinel

    fetcher = threading.Thread(target=fetch_all, daemon=True)
    fetcher.start()

    while True:
        chunk = audio_queue.get()
        if chunk is None:
            break
        if not chunk or cancel.is_set():
            continue  # failed sentence, or user cut us off — drain to sentinel
        _play_audio_bytes(chunk, deadline, cancel)

    return not cancel.is_set()
