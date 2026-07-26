"""Tests for nudge's pure helpers: stage thresholds and reminder composition.

_stage_for is all boundaries, so the cases sit exactly on and one second
either side of each threshold — that's where off-by-one bugs live (<= vs <).
"""
import pytest

from nudge import _stage_for, _fmt_due, _compose, _H3, _H24


@pytest.mark.parametrize(
    "delta_s, expected",
    [
        (-60,       "overdue"),  # past due
        (0,         "overdue"),  # due this instant counts as overdue
        (1,         "3h"),       # one second inside the 3h window
        (_H3,       "3h"),       # exactly 3h out is still "3h" (<=)
        (_H3 + 1,   "24h"),      # one second past 3h falls to "24h"
        (_H24,      "24h"),      # exactly 24h out is still "24h" (<=)
        (_H24 + 1,  None),       # beyond every horizon: no nudge yet
    ],
)
def test_stage_boundaries(delta_s, expected):
    assert _stage_for(delta_s) == expected


def test_fmt_due_formats_and_strips_leading_zero():
    out = _fmt_due("2026-08-14T17:00:00")
    assert "Aug 14" in out
    assert out.endswith("5:00 PM")  # not "05:00 PM"


def test_fmt_due_falls_back_to_raw_string_on_garbage():
    # A hand-edited tasks.json must degrade to showing the raw value,
    # never crash the reminder sweep.
    assert _fmt_due("whenever") == "whenever"


@pytest.mark.parametrize("stage", ["24h", "3h", "overdue"])
def test_compose_always_names_the_task(stage):
    task = {"text": "submit the visa form", "due_iso": "2026-08-14T17:00:00"}
    msg = _compose(task, stage)
    assert "submit the visa form" in msg
    assert "sir" in msg  # persona holds in scheduler-generated speech too


def test_compose_overdue_says_overdue():
    task = {"text": "submit the visa form", "due_iso": "2026-08-14T17:00:00"}
    assert "overdue" in _compose(task, "overdue")
