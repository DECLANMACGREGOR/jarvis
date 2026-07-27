"""Tests for vision.capture_frame's backend fallback.

DSHOW is the fast path and MSMF is the shared-device rescue. What matters is
that the rescue costs nothing when DSHOW works — a second backend attempt on
every capture would add seconds to a spoken turn.
"""
import numpy as np
import cv2
import pytest

import vision


def test_dshow_success_never_touches_msmf(monkeypatch):
    tried = []

    def fake(backend, warmup):
        tried.append(backend)
        return "frame"

    monkeypatch.setattr(vision, "_capture_with_backend", fake)
    assert vision.capture_frame() == "frame"
    assert tried == [cv2.CAP_DSHOW]


def test_msmf_rescues_a_busy_camera(monkeypatch):
    # The Windows Camera app holding the device makes DSHOW return None;
    # MSMF shares it through the Frame Server and still gets a frame.
    tried = []

    def fake(backend, warmup):
        tried.append(backend)
        return None if backend == cv2.CAP_DSHOW else "frame"

    monkeypatch.setattr(vision, "_capture_with_backend", fake)
    assert vision.capture_frame() == "frame"
    assert tried == [cv2.CAP_DSHOW, cv2.CAP_MSMF]


def test_both_backends_failing_returns_none(monkeypatch):
    # No webcam at all — callers surface this as a spoken failure, so it must
    # stay None rather than raising out of the tool call.
    monkeypatch.setattr(vision, "_capture_with_backend", lambda b, w: None)
    assert vision.capture_frame() is None


# ── preview window ───────────────────────────────────────────────────────────

def test_preview_disabled_opens_no_window(monkeypatch):
    # CAMERA_PREVIEW_SECONDS=0 must be a true no-op, not a zero-length flash.
    monkeypatch.setattr(cv2, "imshow", lambda *a: pytest.fail("window opened"))
    vision.show_preview(np.zeros((4, 4, 3), np.uint8), [], 0)


def test_annotation_never_mutates_the_captured_frame():
    # The same frame object is JPEG-encoded and sent to Claude right after
    # this runs — drawing boxes onto it would send Claude the marked-up copy.
    frame = np.zeros((40, 40, 3), np.uint8)
    out = vision._draw_annotations(frame, [{"name": "Declan", "score": 0.9, "box": (1, 1, 10, 10)}])
    assert out.shape == frame.shape
    assert frame.max() == 0, "original frame was drawn on"
    assert out.max() > 0, "annotation was not drawn"


def test_unrecognized_face_is_still_boxed():
    # name=None must not crash the label path — it's the common case when
    # someone unenrolled is on camera.
    frame = np.zeros((40, 40, 3), np.uint8)
    out = vision._draw_annotations(frame, [{"name": None, "score": None, "box": (1, 1, 10, 10)}])
    assert out.max() > 0
