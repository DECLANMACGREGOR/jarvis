"""Tests for vision.capture_frame's backend fallback.

DSHOW is the fast path and MSMF is the shared-device rescue. What matters is
that the rescue costs nothing when DSHOW works — a second backend attempt on
every capture would add seconds to a spoken turn.
"""
import cv2

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
