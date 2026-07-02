import io
import threading
import queue
import re
import time
import pygame
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

_client: ElevenLabs | None = None
_pygame_ready = False


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


def _play_audio_bytes(data: bytes) -> None:
    _ensure_pygame()
    try:
        buf = io.BytesIO(data)
        pygame.mixer.music.load(buf, "mp3")
        pygame.mixer.music.play()
        deadline = time.monotonic() + 60  # safety: never wedge on stuck playback
        while pygame.mixer.music.get_busy() and time.monotonic() < deadline:
            pygame.time.wait(50)
    except Exception as e:
        print(f"[JARVIS] Playback error: {e}")
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


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
    return merged


def speak(text: str) -> None:
    """Convert text to speech and play it. Speaks sentence-by-sentence for low latency."""
    client = _get_client()
    sentences = _split_sentences(text)
    if not sentences:
        return

    audio_queue: queue.Queue[bytes | None] = queue.Queue()

    def fetch_all():
        for sentence in sentences:
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
        if not chunk:
            continue  # a sentence failed to synthesize — skip it, keep going
        _play_audio_bytes(chunk)
