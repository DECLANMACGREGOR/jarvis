"""Tests for voice._split_sentences — the TTS chunker.

Its contract (from voice.py's comments): split on sentence ends for
low-latency streaming, but merge fragments under 20 chars so ElevenLabs
never receives a near-empty input it would garble, and drop a lone shard
under 4 chars entirely rather than synthesize noise.
"""
from voice import _sanitize_for_tts, _split_sentences


def test_two_real_sentences_stay_separate():
    # The normal case: both long enough to synthesize well on their own.
    text = "The weather today is clear and sunny. Your first meeting is at nine thirty."
    assert _split_sentences(text) == [
        "The weather today is clear and sunny.",
        "Your first meeting is at nine thirty.",
    ]


def test_abbreviation_does_not_produce_a_tiny_chunk():
    # "P.M." ends with sentence punctuation, so the splitter cuts after it,
    # leaving two sub-20-char pieces. They must come back merged as one.
    text = "It is now 9:41 P.M. sir, time for bed."
    assert _split_sentences(text) == [text]


def test_short_opener_merges_into_next_sentence():
    # "Understood." alone is 11 chars — under the merge threshold.
    chunks = _split_sentences(
        "Understood. I have the summary of our prior conversation."
    )
    assert len(chunks) == 1


def test_lone_shard_is_dropped_entirely():
    # A stranded "M." has no neighbor to merge into — skip TTS, say nothing.
    assert _split_sentences("M.") == []


def test_four_chars_is_the_keep_boundary():
    # "Yes." is exactly 4 chars: real speech, passes through.
    assert _split_sentences("Yes.") == ["Yes."]


def test_empty_and_whitespace_input_says_nothing():
    assert _split_sentences("") == []
    assert _split_sentences("   ") == []


# ── _sanitize_for_tts: markdown/symbols must never reach the voice ───────────

def test_markdown_bold_and_degree_symbol_become_speech():
    # The exact failure heard live: "**75°F and clear**" was read as
    # "asterisk asterisk seventy-five degree-sign F".
    assert (_sanitize_for_tts("Currently **75°F and clear** out there")
            == "Currently 75 degrees Fahrenheit and clear out there")


def test_percent_after_a_number_is_spoken():
    assert _sanitize_for_tts("just 1% chance of rain") == "just 1 percent chance of rain"


def test_markdown_link_speaks_only_its_label():
    assert _sanitize_for_tts("see [the docs](https://example.com) for more") == "see the docs for more"


def test_plain_prose_passes_through_unchanged():
    text = "Good evening, sir. The forecast is clear."
    assert _sanitize_for_tts(text) == text
