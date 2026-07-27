"""
vision.py — JARVIS eyes, iteration 1.

One-shot camera capture + local face enrollment/recognition.
- Capture: opens the webcam only for the moment of capture, then releases it
  (camera LED behaves honestly — no persistent feed in this iteration).
- Recognition: OpenCV YuNet (detection) + SFace (128-d embeddings), both ONNX,
  CPU-only. Models auto-download once into ./models/.
- Privacy: raw frames live in memory only and are never written to disk.
  Only face EMBEDDINGS (128 floats, not reconstructable into a photo) are
  persisted, in memory/faces.json.
"""

import base64
import json
import os
import threading
import time
import urllib.request

import cv2
import numpy as np

_DIR = os.path.dirname(__file__)
MODELS_DIR = os.path.join(_DIR, "models")
FACES_FILE = os.path.join(_DIR, "memory", "faces.json")

# OpenCV Zoo — official model hosting for cv2's face APIs.
# NOTE: must use github.com/.../raw/ URLs (they resolve Git LFS via redirect);
# raw.githubusercontent.com returns a 131-byte LFS pointer file, not the model.
_YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/"
              "models/face_detection_yunet/face_detection_yunet_2023mar.onnx")
_SFACE_URL = ("https://github.com/opencv/opencv_zoo/raw/main/"
              "models/face_recognition_sface/face_recognition_sface_2021dec.onnx")
_YUNET_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
_SFACE_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

# SFace's published cosine-similarity match threshold
MATCH_THRESHOLD = 0.363


_detector = None
_recognizer = None


def _download(url: str, dest: str) -> None:
    os.makedirs(MODELS_DIR, exist_ok=True)
    print(f"[JARVIS] Downloading vision model: {os.path.basename(dest)} ...")
    tmp = dest + ".part"
    urllib.request.urlretrieve(url, tmp)
    if os.path.getsize(tmp) < 10_000:  # a real ONNX is 100KB+; tiny = LFS pointer
        os.remove(tmp)
        raise RuntimeError(f"Model download for {os.path.basename(dest)} returned "
                           "a pointer/error page, not the model. Check the URL.")
    os.replace(tmp, dest)  # atomic — a killed download can't leave a corrupt model


def _get_models():
    """Lazy-load detector + recognizer, downloading ONNX files on first use."""
    global _detector, _recognizer
    if _detector is None:
        if not os.path.exists(_YUNET_PATH):
            _download(_YUNET_URL, _YUNET_PATH)
        if not os.path.exists(_SFACE_PATH):
            _download(_SFACE_URL, _SFACE_PATH)
        # input size is set per-frame in _detect_faces
        _detector = cv2.FaceDetectorYN.create(_YUNET_PATH, "", (320, 320), 0.7)
        _recognizer = cv2.FaceRecognizerSF.create(_SFACE_PATH, "")
    return _detector, _recognizer


def _capture_with_backend(backend: int, warmup: int) -> np.ndarray | None:
    """Grab one frame through a specific OpenCV capture backend, or None."""
    cap = cv2.VideoCapture(0, backend)
    if not cap.isOpened():
        return None
    try:
        frame = None
        for _ in range(max(1, warmup)):  # let auto-exposure settle
            ok, frame = cap.read()
            if not ok:
                return None
        return frame
    finally:
        cap.release()


def capture_frame(warmup: int = 5) -> np.ndarray | None:
    """Open the webcam, grab one frame, release immediately. None on failure.

    DSHOW opens fast but claims the device exclusively, so it comes back empty
    whenever another app already holds the webcam — the Windows Camera app
    being open is enough. MSMF goes through the Windows Frame Server, which
    shares the device, but is slower to open, so it's only tried once DSHOW has
    actually failed. The common case pays nothing for the fallback.
    """
    frame = _capture_with_backend(cv2.CAP_DSHOW, warmup)
    if frame is None:
        print("[JARVIS] Webcam unavailable on DirectShow — retrying via Media Foundation.")
        frame = _capture_with_backend(cv2.CAP_MSMF, warmup)
    return frame


def _detect_faces(frame: np.ndarray):
    """Return list of YuNet face rows (x,y,w,h,landmarks...,score) or []."""
    detector, _ = _get_models()
    h, w = frame.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    return list(faces) if faces is not None else []


def _embed(frame: np.ndarray, face_row) -> np.ndarray:
    """Align + crop the face, return its 128-d SFace embedding."""
    _, recognizer = _get_models()
    aligned = recognizer.alignCrop(frame, face_row)
    return recognizer.feature(aligned).flatten()


# ── Enrollment store — embeddings only, never images ─────────────────────────

def _load_faces() -> dict:
    try:
        with open(FACES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_faces(faces: dict) -> None:
    os.makedirs(os.path.dirname(FACES_FILE), exist_ok=True)
    tmp = FACES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(faces, f)
    os.replace(tmp, FACES_FILE)  # atomic, same pattern as jarvis_memory.json


def known_names() -> list[str]:
    return sorted(_load_faces().keys())


def enroll(name: str, samples: int = 5, min_good: int = 3) -> str:
    """Capture a short burst, embed the largest face in each frame, save.

    Multiple samples make matching robust to angle/lighting; requiring a
    minimum prevents enrolling off one blurry frame.
    """
    name = name.strip()
    if not name:
        return "Enrollment failed: empty name."
    embeddings = []
    for i in range(samples):
        frame = capture_frame(warmup=5 if i == 0 else 1)
        if frame is None:
            return "Enrollment failed: could not access the camera."
        faces = _detect_faces(frame)
        if faces:
            largest = max(faces, key=lambda f: f[2] * f[3])  # biggest = closest
            embeddings.append(_embed(frame, largest).tolist())
        time.sleep(0.35)  # spread samples over ~1.5s of natural head movement
    if len(embeddings) < min_good:
        return (f"Enrollment failed: only saw a clear face in {len(embeddings)} "
                f"of {samples} captures. Face the camera in decent light and retry.")
    faces_db = _load_faces()
    faces_db[name] = embeddings  # re-enrolling a name replaces old samples
    _save_faces(faces_db)
    return f"Enrolled '{name}' from {len(embeddings)} face samples."


def identify_in_frame(frame: np.ndarray) -> list[dict]:
    """For each detected face: best-matching enrolled name (or None) + score."""
    faces_db = _load_faces()
    results = []
    for row in _detect_faces(frame):
        emb = _embed(frame, row)
        best_name, best_score = None, -1.0
        for name, samples in faces_db.items():
            for s in samples:
                v = np.asarray(s, dtype=np.float32)
                score = float(np.dot(emb, v) /
                              ((np.linalg.norm(emb) * np.linalg.norm(v)) + 1e-9))
                if score > best_score:
                    best_name, best_score = name, score
        results.append({
            "name": best_name if best_score >= MATCH_THRESHOLD else None,
            "score": round(best_score, 3) if faces_db else None,
            "box": tuple(int(v) for v in row[:4]),  # x, y, w, h — for the preview
        })
    return results


# ── Preview window — shows what was captured, still never touches disk ───────

_PREVIEW_WINDOW = "JARVIS - what I see"
_ACCENT = (255, 212, 0)  # BGR for the HUD's #00d4ff


def _draw_annotations(frame: np.ndarray, results: list[dict]) -> np.ndarray:
    """Label each detected face on a copy of the frame."""
    img = frame.copy()
    for r in results:
        box = r.get("box")
        if not box:
            continue
        x, y, w, h = box
        text = r["name"] or "unrecognized"
        if r["score"] is not None:
            text += f"  {r['score']}"
        cv2.rectangle(img, (x, y), (x + w, y + h), _ACCENT, 2)
        cv2.putText(img, text, (x, max(18, y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, _ACCENT, 2)
    return img


def show_preview(frame: np.ndarray, results: list[dict], seconds: float) -> None:
    """Pop up the captured frame, labelled, in a window that closes itself.

    This exists because a webcam can only have one owner: with a live camera
    app open, JARVIS cannot read the device at all on most drivers. Showing
    the frame it actually analysed gives the same "you can see it working"
    view without a second app competing for the camera.

    The window renders the in-memory frame — nothing is written to disk, same
    as everywhere else here. It runs on its own thread so it stays up while
    JARVIS speaks rather than delaying the reply, and any GUI failure is
    logged and swallowed: a preview must never break a turn.
    """
    if seconds <= 0:
        return
    try:
        img = _draw_annotations(frame, results)
    except Exception as e:
        print(f"[JARVIS] Preview annotation failed ({e}) — skipping preview.")
        return

    def _run() -> None:
        try:
            cv2.imshow(_PREVIEW_WINDOW, img)
            cv2.waitKey(int(seconds * 1000))
            cv2.destroyWindow(_PREVIEW_WINDOW)
        except Exception as e:
            print(f"[JARVIS] Preview window failed ({e}) — continuing.")

    threading.Thread(target=_run, daemon=True).start()


def frame_to_b64_jpeg(frame: np.ndarray, max_width: int = 1024) -> str:
    """JPEG-encode a frame (downscaled to cap API payload) as base64."""
    h, w = frame.shape[:2]
    if w > max_width:
        frame = cv2.resize(frame, (max_width, int(h * max_width / w)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")
