"""Tests for tools.py's pure safety logic: confirmation-word matching and
vault path sandboxing.

These two functions ARE the permission gate's judgment and the vault's
fence, so each test pins down a specific way they could fail open.
"""
import os

import pytest

import tools
from tools import _matches, _APPROVE_WORDS, _DENY_WORDS


# ── _matches: whole-word yes/no detection ────────────────────────────────────
# Callers lowercase the reply before matching, so inputs here are lowercase.

def test_no_does_not_hide_inside_notepad():
    # The bug this function exists to prevent: substring matching would read
    # "notepad" as a denial.
    assert not _matches("please open notepad", _DENY_WORDS)


def test_know_is_not_no():
    assert not _matches("i know what you mean", _DENY_WORDS)


def test_plain_yes_approves():
    assert _matches("yes", _APPROVE_WORDS)


def test_multiword_phrase_matches_inside_sentence():
    assert _matches("sure go ahead please", _APPROVE_WORDS)


def test_apostrophe_words_still_deny():
    # The word regex includes ' so "don't" survives tokenization intact.
    assert _matches("don't do that", _DENY_WORDS)


def test_conflicted_reply_trips_both_lists():
    # "yes wait no" matches approve AND deny; the gate requires approve and
    # NOT deny, so an ambiguous answer like this denies. Both halves checked.
    reply = "yes wait no"
    assert _matches(reply, _APPROVE_WORDS)
    assert _matches(reply, _DENY_WORDS)


# ── _vault_resolve: the sandbox fence ────────────────────────────────────────

@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Point the vault at a throwaway temp dir for the duration of one test.

    monkeypatch swaps tools.VAULT_PATH and restores it automatically, so
    these tests can never read or write the real vault.
    """
    monkeypatch.setattr(tools, "VAULT_PATH", str(tmp_path))
    return tmp_path


def test_note_inside_vault_resolves(vault):
    full = tools._vault_resolve("notes.md")
    assert full is not None
    assert full.startswith(os.path.realpath(str(vault)))


def test_dotdot_escape_is_refused(vault):
    assert tools._vault_resolve("../outside.md") is None


def test_absolute_path_on_another_drive_is_refused(vault):
    # os.path.commonpath raises ValueError across drives; the fence must
    # treat that as "outside", not crash.
    assert tools._vault_resolve("D:/outside.md") is None


def test_internal_dotdot_that_stays_inside_is_allowed(vault):
    # "sub/../notes.md" normalizes to "notes.md" — inside the fence, fine.
    assert tools._vault_resolve("sub/../notes.md") is not None


def test_unset_vault_path_disables_everything(monkeypatch):
    # VAULT_PATH="" must hard-refuse, never fall back to sandboxing the cwd.
    monkeypatch.setattr(tools, "VAULT_PATH", "")
    assert tools._vault_resolve("notes.md") is None
    assert "disabled" in tools.search_vault("anything")


# ── _spoken_request: what the user hears before approving ────────────────────

LITERAL = "I want to run shell code that begins: del /s /q C:\\project\\*"


def test_summary_is_spoken_instead_of_raw_code():
    spoken = tools._spoken_request(
        {"spoken_summary": "Permanently delete every file in your project folder."},
        LITERAL,
    )
    assert spoken == "I want to permanently delete every file in your project folder"


@pytest.mark.parametrize("summary", ["", "   ", "delete it", "yes"])
def test_missing_or_useless_summary_falls_back_to_the_literal_action(summary):
    # The whole safety argument for this feature is that it can only ever be
    # LESS fluent than the old code readback, never less informative. A model
    # that omits the field or writes "delete it" must not downgrade the gate
    # into "I want to run some code".
    assert tools._spoken_request({"spoken_summary": summary}, LITERAL) == LITERAL


def test_absent_field_entirely_falls_back():
    assert tools._spoken_request({}, LITERAL) == LITERAL


# ── dispatch: the gate still fires, and the log keeps the technical detail ───

@pytest.fixture
def denied_gate(monkeypatch):
    """Capture what _confirm was asked, and deny — so nothing ever executes."""
    seen = {}

    def fake_confirm(spoken, full, channel="voice"):
        seen["spoken"], seen["full"] = spoken, full
        return False

    monkeypatch.setattr(tools, "_confirm", fake_confirm)
    return seen


def test_run_code_speaks_english_but_logs_the_code(denied_gate):
    result = tools.dispatch("run_code", {
        "code": "import shutil; shutil.rmtree(r'C:\\project')",
        "lang": "python",
        "spoken_summary": "Permanently delete your project folder and everything in it.",
    })
    assert "denied" in result  # gate held: the code never ran
    assert denied_gate["spoken"] == (
        "I want to permanently delete your project folder and everything in it"
    )
    # The audit trail keeps the real code even though speech got friendlier.
    assert "shutil.rmtree" in denied_gate["full"]
    assert "run_code[python]" in denied_gate["full"]


def test_every_dangerous_tool_still_passes_through_the_gate(monkeypatch):
    # Deny-by-default must hold for all four, whatever the summary says.
    calls = []
    monkeypatch.setattr(tools, "_confirm", lambda s, f, c="voice": calls.append(f) or False)
    for name, args in [
        ("run_code", {"code": "x", "lang": "python"}),
        ("open_item", {"target": "notepad"}),
        ("write_vault_note", {"path": "a.md", "content": "c", "mode": "append"}),
        ("delete_calendar_event", {"event_id": "abc123"}),
    ]:
        assert "denied" in tools.dispatch(name, {**args, "spoken_summary": "Do the thing to your files."})
    assert len(calls) == 4
