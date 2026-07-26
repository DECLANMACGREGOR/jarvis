"""Local speech-to-text via faster-whisper — CPU, int8, fully offline."""
import numpy as np
from faster_whisper import WhisperModel
from config import WHISPER_MODEL

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"[JARVIS] Loading Whisper ({WHISPER_MODEL}) — first run downloads ~150MB...")
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        print("[JARVIS] Whisper ready.")
    return _model


def warm_up() -> None:
    """Load the model ahead of first use so the first turn isn't slow."""
    _get_model()


def transcribe(audio: np.ndarray) -> str:
    """Transcribe float32 audio array (16kHz mono) to text."""
    model = _get_model()
    segments, _ = model.transcribe(audio, beam_size=5, language="en", vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text
