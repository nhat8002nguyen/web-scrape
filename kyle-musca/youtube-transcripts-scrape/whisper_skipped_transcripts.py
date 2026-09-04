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
DEFAULT_MAX_DURATION_MINUTES = 30
DEFAULT_MAX_DURATION_SECONDS = DEFAULT_MAX_DURATION_MINUTES * 60


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


def _yt_dlp_auth_opts(
    *,
    quiet: bool = True,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    proxy_url: str | None = None,
) -> dict:
    opts: dict = {
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": quiet,
        "js_runtimes": {"node": {}},
        "remote_components": {"ejs:github"},
    }
    browser = (cookies_from_browser or "").strip()
    cookie_path = (cookies_file or "").strip()
    if browser and cookie_path:
        raise ValueError("Use only one of cookies_from_browser or cookies_file.")
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    elif cookie_path:
        opts["cookiefile"] = str(Path(cookie_path).expanduser().resolve())
    proxy = (proxy_url or "").strip()
    if proxy:
        opts["proxy"] = proxy
    return opts


def resolve_yt_dlp_proxy_url(args: argparse.Namespace | None = None) -> str | None:
    """
    Proxy for yt-dlp downloads: --proxy, else TRANSCRIPT_PROXY, else Webshare
    username/password as http://USER:PASS@p.webshare.io:80/.
    """
    if args is not None:
        cli = (getattr(args, "proxy", None) or "").strip()
        if cli:
            return cli
    for key in ("TRANSCRIPT_PROXY",):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    user = (
        (os.environ.get("WEBSHARE_PROXY_USERNAME") or "").strip()
        or (os.environ.get("WEBSHARE_USER") or "").strip()
    )
    password = (
        (os.environ.get("WEBSHARE_PROXY_PASSWORD") or "").strip()
        or (os.environ.get("WEBSHARE_PASSWORD") or "").strip()
    )
    if user and password:
        from urllib.parse import quote

        host = (os.environ.get("WEBSHARE_PROXY_HOST") or "p.webshare.io").strip()
        port = (os.environ.get("WEBSHARE_PROXY_PORT") or "80").strip()
        return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    return None


def probe_youtube_duration_seconds(
    video_id: str,
    *,
    quiet: bool = True,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    proxy_url: str | None = None,
) -> float | None:
    """Return video duration in seconds via yt-dlp metadata, or None if unknown."""
    opts = _yt_dlp_auth_opts(
        quiet=quiet,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        proxy_url=proxy_url,
    )
    opts["skip_download"] = True
    url = youtube_watch_url(video_id)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        return None
    duration = info.get("duration")
    if duration is None:
        return None
    return float(duration)


def download_youtube_media(
    video_id: str,
    dest_dir: Path,
    *,
    quiet: bool = True,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    proxy_url: str | None = None,
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
    opts = _yt_dlp_auth_opts(
        quiet=quiet,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        proxy_url=proxy_url,
    )
    opts["outtmpl"] = outtmpl
    opts["format"] = "bestaudio/best"
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
    Returns: transcribed | skipped_existing | skipped_duration | failed
    """
    from download_channel_transcripts import write_jsonl_skipped

    filename = build_output_filename(title, video_id)
    dest = out_dir / filename
    if args.resume and dest.is_file():
        return "skipped_existing"

    media_path: Path | None = None
    outcome = "failed"
    cookies_from_browser = getattr(args, "cookies_from_browser", None)
    cookies_file = getattr(args, "cookies", None)
    proxy_url = getattr(args, "proxy_url", None) or resolve_yt_dlp_proxy_url(args)
    max_duration_seconds = float(
        getattr(args, "max_duration_seconds", DEFAULT_MAX_DURATION_SECONDS)
    )
    try:
        duration = probe_youtube_duration_seconds(
            video_id,
            quiet=not args.verbose,
            cookies_from_browser=cookies_from_browser,
            cookies_file=cookies_file,
            proxy_url=proxy_url,
        )
        if duration is not None and duration >= max_duration_seconds:
            minutes = duration / 60.0
            write_jsonl_skipped(
                fail_log_handle,
                {
                    "video_id": video_id,
                    "title": title,
                    "reason": "duration_too_long",
                    "detail": (
                        f"duration={duration:.0f}s ({minutes:.1f}min) "
                        f">= max {max_duration_seconds:.0f}s"
                    ),
                },
                fail_seen,
            )
            print(
                f"  skip duration {minutes:.1f}min "
                f"(max {max_duration_seconds / 60.0:.0f}min)",
                flush=True,
            )
            return "skipped_duration"

        media_path = download_youtube_media(
            video_id,
            download_dir,
            quiet=not args.verbose,
            cookies_from_browser=cookies_from_browser,
            cookies_file=cookies_file,
            proxy_url=proxy_url,
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Whisper-transcribe YouTube videos listed in skipped.jsonl.",
    )
    parser.add_argument(
        "--skip-log",
        required=True,
        metavar="PATH",
        help="Path to the skipped.jsonl file to process.",
    )
    parser.add_argument(
        "--out",
        "-o",
        default="transcripts",
        help="Directory for .txt transcripts (default: ./transcripts).",
    )
    parser.add_argument(
        "--download-dir",
        default="videos",
        metavar="PATH",
        help="Media cache directory; relative paths are resolved under --out.",
    )
    parser.add_argument(
        "--fail-log",
        default="whisper_failed.jsonl",
        metavar="PATH",
        help="Whisper failure log; relative paths are resolved under --out.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip videos whose transcript file already exists in --out.",
    )
    parser.add_argument(
        "--all-reasons",
        action="store_true",
        help="Process every valid row in --skip-log, not only caption-unavailable rows.",
    )
    parser.add_argument(
        "--reason-contains",
        default="",
        metavar="TEXT",
        help="Only process rows whose reason contains this case-insensitive text.",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N matching videos.",
    )
    parser.add_argument(
        "--max-duration-minutes",
        type=float,
        default=DEFAULT_MAX_DURATION_MINUTES,
        metavar="MIN",
        help=(
            "Skip videos whose yt-dlp duration is >= this many minutes "
            f"(default: {DEFAULT_MAX_DURATION_MINUTES}). Use 0 to disable."
        ),
    )
    parser.add_argument(
        "--model-size",
        default="large-v3",
        help="faster-whisper model size (default: large-v3).",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
        help="Whisper device (default: auto).",
    )
    parser.add_argument(
        "--compute-type",
        default="auto",
        help="faster-whisper compute type (default: auto).",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Whisper beam size (default: 5).",
    )
    parser.add_argument(
        "--language",
        default="en",
        help='Whisper language; use "" to auto-detect (default: en).',
    )
    vad_filter = parser.add_mutually_exclusive_group()
    vad_filter.add_argument(
        "--vad-filter",
        dest="vad_filter",
        action="store_true",
        default=True,
        help="Enable voice activity detection filtering (default).",
    )
    vad_filter.add_argument(
        "--no-vad-filter",
        dest="vad_filter",
        action="store_false",
        help="Disable voice activity detection filtering.",
    )
    parser.add_argument(
        "--format",
        choices=("lines", "paragraph"),
        default="lines",
        help="Transcript output format (default: lines).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0,
        help="Sleep seconds after each successful transcription (default: 0).",
    )
    parser.add_argument(
        "--keep-media",
        action="store_true",
        help="Keep downloaded media after a successful transcription.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show yt-dlp output.",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        metavar="BROWSER",
        help=(
            "Pass browser cookies to yt-dlp (e.g. chrome, safari, firefox). "
            "Needed when YouTube returns bot/sign-in challenges."
        ),
    )
    parser.add_argument(
        "--cookies",
        default=None,
        metavar="PATH",
        help=(
            "Netscape cookies.txt for yt-dlp (mutually exclusive with "
            "--cookies-from-browser). Defaults to ./cookies.txt when that file exists."
        ),
    )
    parser.add_argument(
        "--proxy",
        default=None,
        metavar="URL",
        help=(
            "HTTP(S) proxy for yt-dlp (e.g. http://user:pass@p.webshare.io:80/). "
            "If omitted, uses TRANSCRIPT_PROXY or WEBSHARE_PROXY_USERNAME/PASSWORD from .env."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List selected videos without loading Whisper or downloading media.",
    )
    parser.add_argument(
        "--simplepush-key",
        default=None,
        metavar="KEY",
        help="Simplepush key; overrides SIMPLEPUSH_KEY and 56F6LP.",
    )
    parser.add_argument(
        "--simplepush-title",
        default="YouTube Whisper transcripts",
        help="Simplepush notification title.",
    )
    parser.add_argument(
        "--simplepush-event",
        default="",
        help="Optional Simplepush event id.",
    )
    parser.add_argument(
        "--test-simplepush",
        action="store_true",
        help="Send a test Simplepush notification and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    from download_channel_transcripts import (
        load_env_files,
        load_skip_log_video_ids,
        notify_simplepush,
        resolve_simplepush_key,
    )

    load_env_files()
    args = parse_args(argv)

    browser = (args.cookies_from_browser or "").strip()
    cookie_file = (args.cookies or "").strip()
    if not cookie_file and not browser:
        default_cookies = Path.cwd() / "cookies.txt"
        script_cookies = Path(__file__).resolve().parent / "cookies.txt"
        for candidate in (default_cookies, script_cookies):
            if candidate.is_file():
                cookie_file = str(candidate)
                break
    if browser and cookie_file:
        print(
            "error: use either --cookies-from-browser or --cookies, not both.",
            file=sys.stderr,
        )
        return 2
    args.cookies_from_browser = browser or None
    args.cookies = cookie_file or None
    args.proxy_url = resolve_yt_dlp_proxy_url(args)
    max_minutes = float(args.max_duration_minutes)
    if max_minutes <= 0:
        args.max_duration_seconds = float("inf")
    else:
        args.max_duration_seconds = max_minutes * 60.0

    if args.test_simplepush:
        simplepush_key = resolve_simplepush_key(args)
        if not simplepush_key:
            print(
                "error: Simplepush test needs --simplepush-key or "
                "SIMPLEPUSH_KEY / 56F6LP in the environment or .env.",
                file=sys.stderr,
            )
            return 2
        notify_simplepush(
            simplepush_key,
            args.simplepush_title,
            "Test from whisper_skipped_transcripts.py",
            args.simplepush_event or None,
        )
        print("Simplepush: test notification sent.", file=sys.stderr)
        return 0

    skip_path = Path(args.skip_log).expanduser().resolve()
    if not skip_path.is_file():
        print(f"error: --skip-log not found: {skip_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    download_dir = Path(args.download_dir).expanduser()
    if not download_dir.is_absolute():
        download_dir = out_dir / download_dir
    download_dir = download_dir.resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    entries = load_skipped_entries(skip_path)
    entries = filter_entries_by_reason(
        entries,
        reasons=None if args.all_reasons else DEFAULT_WHISPER_REASONS,
        reason_contains=args.reason_contains or None,
    )
    if args.limit is not None:
        entries = entries[: args.limit]

    if not entries:
        print("No matching skipped videos to process.")
        return 0

    if args.dry_run:
        for entry in entries:
            print(
                f"{entry['video_id']}\t{entry.get('reason', '')}\t{entry['title']}"
            )
        print(f"dry-run count={len(entries)}")
        return 0

    if not args.cookies and not args.cookies_from_browser:
        print(
            "warning: no cookies configured. EC2/datacenter IPs usually hit "
            "YouTube bot checks — place cookies.txt in the project dir or pass "
            "--cookies / --cookies-from-browser.",
            file=sys.stderr,
        )
    elif args.cookies:
        print(f"yt-dlp cookies: {args.cookies}", file=sys.stderr)
    if args.proxy_url:
        print("yt-dlp proxy: configured", file=sys.stderr)
    else:
        print(
            "yt-dlp proxy: none (optional: TRANSCRIPT_PROXY or Webshare in .env)",
            file=sys.stderr,
        )

    try:
        whisper_model = load_whisper_model(args)
    except Exception as exc:
        print(f"error: failed to load Whisper model: {exc}", file=sys.stderr)
        return 2

    fail_path = Path(args.fail_log).expanduser()
    if not fail_path.is_absolute():
        fail_path = out_dir / fail_path
    fail_path = fail_path.resolve()
    fail_path.parent.mkdir(parents=True, exist_ok=True)
    fail_seen = load_skip_log_video_ids(fail_path)
    stats = {
        "transcribed": 0,
        "skipped_existing": 0,
        "skipped_duration": 0,
        "failed": 0,
    }

    with fail_path.open("a", encoding="utf-8") as fail_log:
        for index, entry in enumerate(entries, start=1):
            video_id = entry["video_id"]
            title = entry["title"]
            print(f"[{index}/{len(entries)}] {video_id}: {title[:120]}", flush=True)
            outcome = process_skipped_video(
                video_id=video_id,
                title=title,
                out_dir=out_dir,
                download_dir=download_dir,
                whisper_model=whisper_model,
                args=args,
                fail_log_handle=fail_log,
                fail_seen=fail_seen,
            )
            if outcome == "transcribed":
                stats["transcribed"] += 1
                if args.delay > 0:
                    time.sleep(args.delay)
            elif outcome == "skipped_existing":
                stats["skipped_existing"] += 1
            elif outcome == "skipped_duration":
                stats["skipped_duration"] += 1
            elif outcome == "failed":
                stats["failed"] += 1

    print("\nDone.")
    print(f"Transcribed:                  {stats['transcribed']}")
    print(f"Skipped (already on disk):    {stats['skipped_existing']}")
    print(f"Skipped (too long):           {stats['skipped_duration']}")
    print(f"Failed:                       {stats['failed']}")
    print(f"Videos in this run:           {len(entries)}")
    print(f"Output directory:             {out_dir}")
    print(f"Failure log:                  {fail_path}")

    simplepush_key = resolve_simplepush_key(args)
    if simplepush_key:
        notify_simplepush(
            simplepush_key,
            f"{args.simplepush_title} — finished",
            (
                f"Processed {len(entries)} video(s). "
                f"Transcribed: {stats['transcribed']}, "
                f"skipped: {stats['skipped_existing']}, "
                f"too long: {stats['skipped_duration']}, "
                f"failed: {stats['failed']}. Output: {out_dir}"
            ),
            args.simplepush_event or None,
        )

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
