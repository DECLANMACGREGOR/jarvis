import time
import numpy as np
import sounddevice as sd
from config import (
    CLAP_THRESHOLD,
    CLAP_SPIKE_RATIO,
    CLAP_WINDOW_MIN,
    CLAP_WINDOW_MAX,
    SILENCE_TIMEOUT,
)

SAMPLE_RATE = 16000
CHUNK = 1024  # frames per callback


def _rms(data: np.ndarray) -> float:
    normalized = data.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(normalized ** 2)))


def wait_for_clap() -> None:
    """Block until a double-clap is detected.

    A clap must (1) exceed CLAP_THRESHOLD, (2) be CLAP_SPIKE_RATIO times louder
    than the rolling background level, and (3) decay back down within a few
    chunks (~250ms). Sustained sound like speech or music fails check (3),
    which prevents conversation/TV from waking JARVIS.
    """
    clap_times: list[float] = []
    detected = False
    background = 0.002       # rolling background-noise estimate (EMA)
    pending: float | None = None  # timestamp of a spike awaiting decay confirmation
    chunks_loud = 0

    def _register(now: float) -> None:
        nonlocal detected
        clap_times[:] = [t for t in clap_times if now - t <= CLAP_WINDOW_MAX]
        clap_times.append(now)
        if len(clap_times) >= 2:
            gap = clap_times[-1] - clap_times[-2]
            if CLAP_WINDOW_MIN <= gap <= CLAP_WINDOW_MAX:
                detected = True

    def callback(indata, frames, time_info, status):
        nonlocal detected, background, pending, chunks_loud
        if detected:
            return
        volume = _rms(indata[:, 0])
        if volume > 0.01:
            bar = min(int(volume * 40), 20)
            print(f"\r  vol: {'█' * bar}{' ' * (20 - bar)} {volume:.3f}", end="", flush=True)

        if pending is not None:
            # A spike happened recently — confirm it was a sharp transient (clap),
            # not the onset of sustained sound (speech).
            if volume < max(background * 2, CLAP_THRESHOLD * 0.5):
                _register(pending)
                pending = None
            else:
                chunks_loud += 1
                if chunks_loud > 4:  # still loud after ~250ms → not a clap
                    pending = None
        elif volume > CLAP_THRESHOLD and volume > background * CLAP_SPIKE_RATIO:
            pending = time.monotonic()
            chunks_loud = 0
        else:
            # Only adapt background during non-spike chunks
            background = 0.95 * background + 0.05 * max(volume, 1e-6)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        blocksize=CHUNK, callback=callback):
        while not detected:
            time.sleep(0.05)


def record_until_silence() -> np.ndarray:
    """Record audio until silence is detected, return as float32 array."""
    chunks: list[np.ndarray] = []
    last_sound = time.monotonic()

    def callback(indata, frames, time_info, status):
        nonlocal last_sound
        chunks.append(indata[:, 0].copy())
        if _rms(indata[:, 0]) > CLAP_THRESHOLD * 0.3:
            last_sound = time.monotonic()

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        blocksize=CHUNK, callback=callback):
        while True:
            time.sleep(0.05)
            if time.monotonic() - last_sound > SILENCE_TIMEOUT and len(chunks) > 5:
                break

    audio = np.concatenate(chunks).astype(np.float32) / 32768.0
    return audio


def listen() -> np.ndarray:
    """Wait for double-clap, then record and return the voice audio."""
    print("\n[JARVIS] Listening for activation clap clap...")
    wait_for_clap()
    print("[JARVIS] Activated — speak now.")
    audio = record_until_silence()
    return audio
