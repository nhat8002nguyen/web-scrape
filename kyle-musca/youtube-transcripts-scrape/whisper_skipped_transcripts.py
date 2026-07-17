from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

import yt_dlp
from download_channel_transcripts import (
    build_output_filename,
    youtube_watch_url,
)

_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

DEFAULT_WHISPER_REASONS: frozenset[str] = frozenset(
    {
        "transcripts_disabled",
        "no_matching_transcript",
    }
)


def load_skipped_entries(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        vid = obj.get("video_id")
        if not isinstance(vid, str) or not _YOUTUBE_VIDEO_ID_RE.fullmatch(vid):
            continue
        if vid in seen:
            continue
        seen.add(vid)
        title_o = obj.get("title")
        title = (
            title_o.strip()
            if isinstance(title_o, str) and title_o.strip()
            else vid
        )
        reason = obj.get("reason")
        entry: dict[str, Any] = {
            "video_id": vid,
            "title": title,
            "reason": reason if isinstance(reason, str) else "",
        }
        detail = obj.get("detail")
        if isinstance(detail, str) and detail:
            entry["detail"] = detail
        rows.append(entry)
    return rows


def filter_entries_by_reason(
    entries: list[dict[str, Any]],
    *,
    reasons: frozenset[str] | None,
    reason_contains: str | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    needle = (reason_contains or "").strip().lower()
    for entry in entries:
        reason = str(entry.get("reason") or "")
        if reasons is not None and reason not in reasons:
            continue
        if needle and needle not in reason.lower():
            continue
        out.append(entry)
    return out


def segments_to_transcript_text(
    segments: list[dict[str, object]],
    style: str,
) -> str:
    lines: list[str] = []
    for seg in segments:
        t = str(seg.get("text") or "").replace("\u200b", "").strip()
        if t:
            lines.append(t)
    if not lines:
        return ""
    if style == "paragraph":
        body = " ".join(lines)
    else:
        body = "\n".join(lines)
    if not body.endswith("\n"):
        body += "\n"
    return body


def huggingface_cache_hub_dir() -> str:
    hf_home = os.environ.get("HF_HOME", "").strip() or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface"
    )
    return os.path.join(os.path.expanduser(hf_home), "hub")


def _whisper_heartbeat(stop: threading.Event, label: str, hub_dir: str) -> None:
    start = time.monotonic()
    while not stop.wait(30.0):
        elapsed = int(time.monotonic() - start)
        print(
            f"  {label} still loading ({elapsed}s elapsed). "
            f"If downloading, this folder should grow: {hub_dir}",
            file=sys.stderr,
            flush=True,
        )


def load_whisper_model(args: argparse.Namespace) -> object:
    if os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS", "").strip() != "1":
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "0")

    from faster_whisper import WhisperModel

    device = args.device
    compute_type = args.compute_type
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    hub_dir = huggingface_cache_hub_dir()
    print(
        f"Loading Whisper model {args.model_size!r} "
        f"(device={device}, compute_type={compute_type})…",
        file=sys.stderr,
        flush=True,
    )
    print(f"  Hugging Face hub cache: {hub_dir}", file=sys.stderr, flush=True)
    print(
        "  First-time `large-v3` is ~2.5–4 GB; expect several minutes on first run.",
        file=sys.stderr,
        flush=True,
    )

    stop = threading.Event()
    beat = threading.Thread(
        target=_whisper_heartbeat,
        args=(stop, "Whisper:", hub_dir),
        daemon=True,
    )
    beat.start()
    try:
        model = WhisperModel(
            args.model_size,
            device=device,
            compute_type=compute_type,
        )
    finally:
        stop.set()
    return model


def transcribe_segments(
    model,
    media_path: Path,
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    segments, _ = model.transcribe(
        str(media_path),
        beam_size=args.beam_size,
        language=args.language or None,
        vad_filter=args.vad_filter,
    )
    out: list[dict[str, object]] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        out.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": text,
            }
        )
    return out


def resolve_downloaded_media_path(dest_dir: Path, video_id: str) -> Path:
    matches = sorted(dest_dir.glob(f"{video_id}.*"))
    matches = [
        p
        for p in matches
        if p.is_file()
        and not p.name.endswith(".part")
        and not p.name.endswith(".ytdl")
    ]
    if not matches:
        raise FileNotFoundError(
            f"No downloaded media for {video_id} under {dest_dir}"
        )
    return matches[0]


def download_youtube_media(
    video_id: str,
    dest_dir: Path,
    *,
    quiet: bool = True,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = list(dest_dir.glob(f"{video_id}.*"))
    existing = [
        p
        for p in existing
        if p.is_file() and not p.name.endswith((".part", ".ytdl"))
    ]
    if existing:
        return existing[0]

    outtmpl = str(dest_dir / f"{video_id}.%(ext)s")
    opts: dict = {
        "outtmpl": outtmpl,
        "format": "bestaudio/best",
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": quiet,
    }
    url = youtube_watch_url(video_id)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return resolve_downloaded_media_path(dest_dir, video_id)


def process_skipped_video(
    *,
    video_id: str,
    title: str,
    out_dir: Path,
    download_dir: Path,
    whisper_model,
    args: argparse.Namespace,
    fail_log_handle,
    fail_seen: set[str],
) -> str:
    """
    Returns: transcribed | skipped_existing | failed
    """
    from download_channel_transcripts import write_jsonl_skipped

    filename = build_output_filename(title, video_id)
    dest = out_dir / filename
    if args.resume and dest.is_file():
        return "skipped_existing"

    media_path: Path | None = None
    outcome = "failed"
    try:
        media_path = download_youtube_media(
            video_id, download_dir, quiet=not args.verbose
        )
        segments = transcribe_segments(whisper_model, media_path, args)
        body = segments_to_transcript_text(segments, style=args.format)
        if not body.strip():
            write_jsonl_skipped(
                fail_log_handle,
                {
                    "video_id": video_id,
                    "title": title,
                    "reason": "whisper_no_speech",
                    "detail": "transcription returned no segments",
                },
                fail_seen,
            )
            return "failed"
        out_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        outcome = "transcribed"
        return outcome
    except Exception as exc:
        write_jsonl_skipped(
            fail_log_handle,
            {
                "video_id": video_id,
                "title": title,
                "reason": type(exc).__name__,
                "detail": str(exc),
            },
            fail_seen,
        )
        return "failed"
    finally:
        if (
            outcome == "transcribed"
            and not args.keep_media
            and media_path is not None
            and media_path.is_file()
        ):
            try:
                media_path.unlink()
            except OSError:
                pass
