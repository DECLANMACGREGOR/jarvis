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
