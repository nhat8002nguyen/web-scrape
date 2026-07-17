from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from whisper_skipped_transcripts import (
    DEFAULT_WHISPER_REASONS,
    filter_entries_by_reason,
    load_skipped_entries,
    main,
    parse_args,
    process_skipped_video,
    resolve_downloaded_media_path,
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


def test_resolve_downloaded_media_path_finds_file(tmp_path: Path):
    media = tmp_path / "abc12345678.m4a"
    media.write_bytes(b"x")
    found = resolve_downloaded_media_path(tmp_path, "abc12345678")
    assert found == media


def test_resolve_downloaded_media_path_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_downloaded_media_path(tmp_path, "abc12345678")


def test_resolve_downloaded_media_path_ignores_partial_files(tmp_path: Path):
    (tmp_path / "abc12345678.part").write_bytes(b"x")
    (tmp_path / "abc12345678.ytdl").write_bytes(b"x")
    media = tmp_path / "abc12345678.webm"
    media.write_bytes(b"x")
    assert resolve_downloaded_media_path(tmp_path, "abc12345678") == media


def test_process_skipped_video_skipped_existing(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    dest = out_dir / "Title__abc12345678.txt"
    dest.write_text("existing\n", encoding="utf-8")
    args = SimpleNamespace(resume=True, format="lines", verbose=False, keep_media=False)
    outcome = process_skipped_video(
        video_id="abc12345678",
        title="Title",
        out_dir=out_dir,
        download_dir=tmp_path / "dl",
        whisper_model=object(),
        args=args,
        fail_log_handle=open(tmp_path / "fail.jsonl", "w"),
        fail_seen=set(),
    )
    assert outcome == "skipped_existing"


def test_process_skipped_video_transcribed_deletes_media(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "out"
    download_dir = tmp_path / "dl"
    download_dir.mkdir()
    media = download_dir / "abc12345678.m4a"
    media.write_bytes(b"audio")

    def fake_download(video_id, dest_dir, *, quiet=True):
        return media

    def fake_transcribe(model, media_path, args):
        return [{"start": 0.0, "end": 1.0, "text": "hello"}]

    monkeypatch.setattr(
        "whisper_skipped_transcripts.download_youtube_media", fake_download
    )
    monkeypatch.setattr(
        "whisper_skipped_transcripts.transcribe_segments", fake_transcribe
    )

    args = SimpleNamespace(
        resume=False, format="lines", verbose=False, keep_media=False
    )
    fail_path = tmp_path / "fail.jsonl"
    with fail_path.open("w") as fail_log:
        outcome = process_skipped_video(
            video_id="abc12345678",
            title="Title",
            out_dir=out_dir,
            download_dir=download_dir,
            whisper_model=object(),
            args=args,
            fail_log_handle=fail_log,
            fail_seen=set(),
        )
    assert outcome == "transcribed"
    dest = out_dir / "Title__abc12345678.txt"
    assert dest.read_text(encoding="utf-8") == "hello\n"
    assert not media.is_file()


def test_process_skipped_video_failed_keeps_media(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "out"
    download_dir = tmp_path / "dl"
    download_dir.mkdir()
    media = download_dir / "abc12345678.m4a"
    media.write_bytes(b"audio")

    def fake_download(video_id, dest_dir, *, quiet=True):
        return media

    def fake_transcribe(model, media_path, args):
        return []

    monkeypatch.setattr(
        "whisper_skipped_transcripts.download_youtube_media", fake_download
    )
    monkeypatch.setattr(
        "whisper_skipped_transcripts.transcribe_segments", fake_transcribe
    )

    args = SimpleNamespace(
        resume=False, format="lines", verbose=False, keep_media=False
    )
    fail_path = tmp_path / "fail.jsonl"
    with fail_path.open("w") as fail_log:
        outcome = process_skipped_video(
            video_id="abc12345678",
            title="Title",
            out_dir=out_dir,
            download_dir=download_dir,
            whisper_model=object(),
            args=args,
            fail_log_handle=fail_log,
            fail_seen=set(),
        )
    assert outcome == "failed"
    assert media.is_file()
    fail_lines = fail_path.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(fail_lines[0])["reason"] == "whisper_no_speech"


def test_parse_args_uses_whisper_cli_defaults():
    args = parse_args(["--skip-log", "skipped.jsonl"])

    assert args.out == "transcripts"
    assert args.download_dir == "videos"
    assert args.model_size == "large-v3"
    assert args.vad_filter is True
    assert args.format == "lines"


def test_main_dry_run_filters_to_whisper_reasons(capsys):
    status = main(["--skip-log", str(FIXTURE), "--dry-run"])

    captured = capsys.readouterr()
    assert status == 0
    assert "p4kM2Z81C4c" in captured.out
    assert "Ouo7Se6zpfM" not in captured.out
    assert "dry-run count=3" in captured.out
