from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from whisper_skipped_transcripts import (
    DEFAULT_WHISPER_REASONS,
    filter_entries_by_reason,
    load_skipped_entries,
    segments_to_transcript_text,
    transcribe_segments,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skipped.jsonl"


def test_default_whisper_reasons():
    assert "transcripts_disabled" in DEFAULT_WHISPER_REASONS
    assert "no_matching_transcript" in DEFAULT_WHISPER_REASONS
    assert "proxy_or_network_error" not in DEFAULT_WHISPER_REASONS


def test_load_skipped_entries_skips_invalid_video_id():
    entries = load_skipped_entries(FIXTURE)
    ids = [e["video_id"] for e in entries]
    assert "p4kM2Z81C4c" in ids
    assert "badid" not in ids
    assert len(entries) == 4


def test_filter_default_reasons_excludes_proxy_errors():
    entries = load_skipped_entries(FIXTURE)
    filtered = filter_entries_by_reason(
        entries, reasons=DEFAULT_WHISPER_REASONS, reason_contains=None
    )
    ids = {e["video_id"] for e in filtered}
    assert ids == {"p4kM2Z81C4c", "aAKbKr51jgg", "JU1LP-datLI"}
    assert "Ouo7Se6zpfM" not in ids


def test_filter_all_reasons_when_reasons_none():
    entries = load_skipped_entries(FIXTURE)
    filtered = filter_entries_by_reason(entries, reasons=None, reason_contains=None)
    assert len(filtered) == 4


def test_filter_reason_contains():
    entries = load_skipped_entries(FIXTURE)
    filtered = filter_entries_by_reason(
        entries, reasons=None, reason_contains="proxy"
    )
    assert [e["video_id"] for e in filtered] == ["Ouo7Se6zpfM"]


def test_segments_to_transcript_text_lines():
    segments = [
        {"start": 0.0, "end": 1.0, "text": " Hello "},
        {"start": 1.0, "end": 2.0, "text": "world"},
        {"start": 2.0, "end": 3.0, "text": "  "},
    ]
    text = segments_to_transcript_text(segments, style="lines")
    assert text == "Hello\nworld\n"


def test_segments_to_transcript_text_paragraph():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello"},
        {"start": 1.0, "end": 2.0, "text": "world"},
    ]
    text = segments_to_transcript_text(segments, style="paragraph")
    assert text == "Hello world\n"


class _FakeSeg:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class _FakeModel:
    def transcribe(self, path, beam_size=5, language=None, vad_filter=True):
        assert Path(path).name == "clip.wav"
        return iter([_FakeSeg(0.0, 1.0, " hi "), _FakeSeg(1.0, 2.0, "")]), None


def test_transcribe_segments_strips_empty():
    args = SimpleNamespace(beam_size=5, language="en", vad_filter=True)
    segs = transcribe_segments(_FakeModel(), Path("/tmp/clip.wav"), args)
    assert segs == [{"start": 0.0, "end": 1.0, "text": "hi"}]
