"""Push-to-talk audio capture.

Hold PTT_KEY (config.py, default F8) to record; release to send.
No wake word, no ambient listening — the mic only records while the key is down.
"""
import time
import numpy as np
import sounddevice as sd
import keyboard
from config import PTT_KEY

SAMPLE_RATE = 16000
CHUNK = 1024  # frames per callback


def wait_for_ptt(timeout: float | None = None) -> bool:
    """Block until the PTT key is pressed. Returns False if timeout expires first."""
    start = time.monotonic()
    while not keyboard.is_pressed(PTT_KEY):
        if timeout is not None and (time.monotonic() - start) > timeout:
            return False
        time.sleep(0.02)
    return True


def record_while_held() -> np.ndarray:
    """Record audio for as long as the PTT key is held. Call after wait_for_ptt().

    Returns float32 16kHz mono audio; empty array if the press was too short.
    """
    chunks: list[np.ndarray] = []

    def callback(indata, frames, time_info, status):
        chunks.append(indata[:, 0].copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        blocksize=CHUNK, callback=callback):
        while keyboard.is_pressed(PTT_KEY):
            time.sleep(0.03)
        time.sleep(0.15)  # small tail so the last word isn't clipped

    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0
