#!/usr/bin/env python3
"""
Enumerate all uploads on a YouTube channel (via yt-dlp) and save each video's
caption transcript to a plain-text file using youtube-transcript-api (same
captions YouTube exposes: manual or auto-generated).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator
from urllib.parse import quote, urlparse, urlunparse

import requests
import yt_dlp
from urllib3.exceptions import MaxRetryError, NewConnectionError
from youtube_transcript_api import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    FetchedTranscript,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptList,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeRequestFailed,
    YouTubeTranscriptApi,
    YouTubeTranscriptApiException,
)
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

INVALID_FS_CHARS_RE = re.compile(r'[\x00-\x1f<>:"/\\\\|?*]')
_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _oserror_is_network_stack(exc: OSError) -> bool:
    """
    urllib3 HTTP/connection errors subclass OSError; they are not local filesystem
    failures (PermissionError, FileNotFoundError, etc.).
    """
    mod = type(exc).__module__
    return mod.startswith(("urllib3", "requests"))


def make_transcript_api(proxy_url: str | None) -> YouTubeTranscriptApi:
    """Optional HTTP(S) proxy helps when YouTube returns IpBlocked for your IP."""
    url = (proxy_url or "").strip()
    if not url:
        return YouTubeTranscriptApi()
    cfg = GenericProxyConfig(http_url=url, https_url=url)
    return YouTubeTranscriptApi(proxy_config=cfg)


def make_webshare_rotating_api(
    username: str,
    password: str,
    *,
    location_codes: list[str],
    retries_when_blocked: int,
) -> YouTubeTranscriptApi:
    """
    Webshare rotating residential pool via p.webshare.io (see youtube-transcript-api docs).
    Requires a Webshare **Residential** subscription, not datacenter static lists.
    """
    cfg = WebshareProxyConfig(
        proxy_username=username,
        proxy_password=password,
        filter_ip_locations=location_codes or None,
        retries_when_blocked=retries_when_blocked,
    )
    return YouTubeTranscriptApi(proxy_config=cfg)


def resolve_webshare_credentials(args: argparse.Namespace) -> tuple[str, str] | None:
    u = (
        (args.webshare_user or "").strip()
        or (os.environ.get("WEBSHARE_PROXY_USERNAME") or "").strip()
        or (os.environ.get("WEBSHARE_USER") or "").strip()
    )
    p = (
        (args.webshare_password or "").strip()
        or (os.environ.get("WEBSHARE_PROXY_PASSWORD") or "").strip()
        or (os.environ.get("WEBSHARE_PASSWORD") or "").strip()
    )
    if u and p:
        return (u, p)
    if u or p:
        raise ValueError(
            "Webshare needs both username and password: --webshare-user and "
            "--webshare-password, or WEBSHARE_PROXY_USERNAME and "
            "WEBSHARE_PROXY_PASSWORD in the environment / .env."
        )
    return None


def effective_transcript_proxy_url(args: argparse.Namespace) -> str | None:
    """
    Single proxy URL for GenericProxyConfig: same string used for HTTP and HTTPS
    (equivalent to requests.get(..., proxies={'http': url, 'https': url})).
    CLI --proxy wins; otherwise TRANSCRIPT_PROXY from the environment / .env.
    """
    for candidate in (
        (args.proxy or "").strip(),
        (os.environ.get("TRANSCRIPT_PROXY") or "").strip(),
    ):
        if candidate:
            return candidate
    return None


def parse_proxy_file_contents(text: str) -> list[str]:
    """
    One proxy per line:
    - host:port:username:password (Webshare / common datacenter list export)
    - or a full URL: http://user:pass@host:port
    """
    urls: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "://" in line:
            urls.append(line)
            continue
        parts = line.split(":")
        if len(parts) < 4:
            continue
        host, port, user = parts[0], parts[1], parts[2]
        password = ":".join(parts[3:])
        u = quote(user, safe="")
        p = quote(password, safe="")
        urls.append(f"http://{u}:{p}@{host}:{port}")
    return urls


def resolve_proxy_file_path(path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if p.is_file():
        return p.resolve()
    if not p.is_absolute():
        cwd_path = (Path.cwd() / p).resolve()
        script_path = (Path(__file__).resolve().parent / p).resolve()
        for candidate in (cwd_path, script_path):
            if candidate.is_file():
                return candidate
        return cwd_path
    return p.resolve()


def normalize_channel_uploads_url(url: str) -> str:
    """Normalize any common channel/profile URL into the uploads tab (/videos)."""
    raw = url.strip()
    if not raw:
        raise ValueError("Channel URL must not be empty.")
    pu = urlparse(raw if "://" in raw else f"https://{raw}")
    if pu.netloc and "youtube.com" not in pu.netloc.lower():
        raise ValueError("Expected a youtube.com URL.")
    scheme = pu.scheme or "https"
    netloc = pu.netloc or "www.youtube.com"
    path = pu.path.rstrip("/")
    path_lower = path.lower()
    uploads_suffix = "/videos"
    known_tabs = (
        "/videos",
        "/shorts",
        "/streams",
        "/playlists",
        "/featured",
        "/releases",
        "/community",
        "/about",
    )
    if any(path_lower.endswith(tab) for tab in known_tabs):
        if path_lower.endswith(uploads_suffix):
            new_path = path + "/"
        elif path_lower.endswith("/shorts"):
            base = path.rsplit("/", 1)[0]
            new_path = base + uploads_suffix + "/"
        else:
            base = path.rsplit("/", 1)[0]
            new_path = base + uploads_suffix + "/"
    else:
        new_path = path + uploads_suffix + "/"
    return urlunparse((scheme, netloc, new_path, "", "", ""))


def walk_playlist_entries(entries: Iterable[dict | None] | None) -> Iterator[dict]:
    if not entries:
        return
    for item in entries:
        if not item:
            continue
        nested = item.get("entries")
        if nested:
            yield from walk_playlist_entries(nested)
        elif item.get("id"):
            yield item


def list_channel_videos(channel_url: str) -> list[tuple[str, str]]:
    """Return (video_id, title) for every resolved upload on the channel tab."""
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    rows: list[tuple[str, str]] = []
    seen: set[str] = set()

    root_entries = []
    if info:
        root_entries = info.get("entries") or []
        # Single-video edge case when URL resolves to one video.
        if not root_entries and info.get("id") and info.get("_type") == "url":
            root_entries = [info]

    for entry in walk_playlist_entries(root_entries):
        vid = entry.get("id")
        title = entry.get("title") or vid or "unknown"
        if isinstance(vid, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) and vid not in seen:
            seen.add(vid)
            rows.append((vid, title))
    return rows


def sanitize_title(title: str, max_length: int = 120) -> str:
    s = INVALID_FS_CHARS_RE.sub("_", title)
    s = " ".join(s.split())
    if not s:
        s = "untitled"
    if len(s) > max_length:
        s = s[:max_length].rstrip("_ .")
    return s or "untitled"


def transcript_to_text(ft: FetchedTranscript, style: str) -> str:
    lines = []
    for snip in ft.snippets:
        t = snip.text.replace("\u200b", "").strip()
        if t:
            lines.append(t)
    if style == "paragraph":
        return " ".join(lines)
    return "\n".join(lines)


def select_transcript(
    transcript_list: TranscriptList,
    languages: tuple[str, ...],
    *,
    strict_lang: bool,
    video_id: str,
) -> object | None:
    """Return a youtube_transcript_api.Transcript to fetch, or None if exhausted."""

    if not isinstance(transcript_list, TranscriptList):
        raise TypeError("Expected TranscriptList from API.")

    langs = list(dict.fromkeys(languages))  # unique, preserve order

    candidates: list[Callable[..., object]] = []
    candidates.append(lambda: transcript_list.find_manually_created_transcript(langs))
    candidates.append(lambda: transcript_list.find_generated_transcript(langs))
    if not strict_lang:
        candidates.append(lambda: transcript_list.find_transcript(langs))

    last_exc: BaseException | None = None
    for getter in candidates:
        try:
            return getter()
        except NoTranscriptFound as exc:
            last_exc = exc
            continue

    if strict_lang:
        return None

    for transcript in transcript_list:
        return transcript

    if last_exc is not None:
        raise last_exc
    raise NoTranscriptFound(video_id, langs, transcript_list)


def fetch_transcript_with_retries(
    api: YouTubeTranscriptApi,
    video_id: str,
    languages: tuple[str, ...],
    strict_lang: bool,
    max_retries: int,
    sleep_secs: Callable[[int], float],
) -> FetchedTranscript:
    transient = (
        RequestBlocked,
        IpBlocked,
        YouTubeRequestFailed,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        MaxRetryError,
        NewConnectionError,
    )

    attempts_total = max(1, max_retries + 1)
    last_error: BaseException | None = None

    for attempt in range(attempts_total):
        try:
            t_list = api.list(video_id)
            transcript = select_transcript(
                t_list,
                languages,
                strict_lang=strict_lang,
                video_id=video_id,
            )
            if transcript is None:
                raise NoTranscriptFound(video_id, languages, t_list)
            return transcript.fetch()
        except transient as exc:
            last_error = exc
            if attempt + 1 >= attempts_total:
                break
            time.sleep(max(0.0, sleep_secs(attempt + 1)))
            continue
    if last_error is not None:
        raise last_error
    raise CouldNotRetrieveTranscript(video_id)


def fetch_transcript_with_ip_ban_waves(
    api: YouTubeTranscriptApi,
    video_id: str,
    languages: tuple[str, ...],
    strict_lang: bool,
    max_retries: int,
    sleep_secs: Callable[[int], float],
    *,
    ip_ban_retries: int,
) -> FetchedTranscript:
    """
    Runs fetch_transcript_with_retries; on IpBlocked/RequestBlocked, repeats the
    whole attempt (including inner max-retries) up to ip_ban_retries more times
    with longer sleeps between waves.
    """
    waves = max(1, int(ip_ban_retries) + 1)
    last_ban: BaseException | None = None
    for wave in range(waves):
        try:
            return fetch_transcript_with_retries(
                api,
                video_id,
                languages,
                strict_lang=strict_lang,
                max_retries=max_retries,
                sleep_secs=sleep_secs,
            )
        except (IpBlocked, RequestBlocked) as exc:
            last_ban = exc
            if wave + 1 >= waves:
                raise
            delay = min(180.0, 20.0 * (2.0**wave))
            print(
                f"  {type(exc).__name__}: IP-ban retry {wave + 1}/{ip_ban_retries} "
                f"(waiting {delay:.0f}s, then full fetch again)…",
                file=sys.stderr,
            )
            time.sleep(delay)
    if last_ban is not None:
        raise last_ban
    raise CouldNotRetrieveTranscript(video_id)


def load_skip_log_video_ids(path: Path) -> set[str]:
    """Existing video_ids in skipped.jsonl so we do not append duplicates."""
    seen: set[str] = set()
    if not path.is_file():
        return seen
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return seen
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid = obj.get("video_id")
        if isinstance(vid, str) and vid:
            seen.add(vid)
    return seen


def load_retry_videos_from_skip_log(path: Path) -> list[tuple[str, str]]:
    """Build (video_id, title) pairs from skipped.jsonl for --retry-from-skip-log."""
    rows: list[tuple[str, str]] = []
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
        rows.append((vid, title))
    return rows


def write_jsonl_skipped(
    handle,
    obj: dict,
    seen_video_ids: set[str],
) -> None:
    vid = obj.get("video_id")
    if isinstance(vid, str) and vid in seen_video_ids:
        return
    handle.write(json.dumps(obj, ensure_ascii=False) + "\n")
    handle.flush()
    if isinstance(vid, str) and vid:
        seen_video_ids.add(vid)


def build_output_filename(title: str, video_id: str) -> str:
    stem = sanitize_title(title)
    return f"{stem}__{video_id}.txt"


# Excel (xlsx) single-cell character limit when opening in Microsoft Excel.
_EXCEL_MAX_CELL_CHARS = 32767


def clip_text_for_excel_cell(text: str) -> str:
    if len(text) <= _EXCEL_MAX_CELL_CHARS:
        return text
    suffix = "\n… [truncated for Excel 32,767 character cell limit]"
    return text[: _EXCEL_MAX_CELL_CHARS - len(suffix)] + suffix


def notify_simplepush(
    key: str | None,
    title: str,
    message: str,
    event: str | None,
) -> None:
    if not key:
        return
    try:
        from simplepush import send

        kwargs: dict = {"title": title, "ignore_connection_errors": False}
        ev = (event or "").strip()
        if ev:
            kwargs["event"] = ev
        send(key, message, **kwargs)
    except Exception as exc:
        print(f"warning: Simplepush notification failed: {exc}", file=sys.stderr)


def load_env_files() -> None:
    """Load `.env` next to this script, then cwd if different (cwd overrides)."""
    from dotenv import load_dotenv

    script_env = Path(__file__).resolve().parent / ".env"
    cwd_env = Path.cwd() / ".env"
    seen: set[Path] = set()
    if script_env.is_file():
        load_dotenv(script_env)
        seen.add(script_env.resolve())
    if cwd_env.is_file() and cwd_env.resolve() not in seen:
        load_dotenv(cwd_env, override=True)


def resolve_simplepush_key(args: argparse.Namespace) -> str | None:
    return (
        (args.simplepush_key or "").strip()
        or (os.environ.get("SIMPLEPUSH_KEY") or "").strip()
        or (os.environ.get("56F6LP") or "").strip()
        or None
    )


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def resolve_xlsx_output_path(xlsx_arg: str, out_dir: Path) -> Path:
    p = Path(xlsx_arg).expanduser()
    if not p.is_absolute():
        p = out_dir / p
    return p.resolve()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download transcripts for every upload on a YouTube channel.",
    )
    parser.add_argument(
        "channel",
        nargs="?",
        help="Full YouTube channel URL (handles @name, /channel/UC..., /c/...).",
    )
    parser.add_argument(
        "--channel",
        "-c",
        dest="channel_opt",
        metavar="URL",
        help="Channel URL if you prefer a flag instead of positional.",
    )
    parser.add_argument(
        "--out",
        "-o",
        default="transcripts",
        help="Directory to write .txt transcripts (default: ./transcripts)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Sleep seconds between successful transcript downloads (default: 5)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Retries on transient youtube-transcript-api errors (default: 3)",
    )
    parser.add_argument(
        "--ip-ban-retries",
        type=int,
        default=3,
        metavar="N",
        help=(
            "After inner --max-retries on a video, if IpBlocked/RequestBlocked persists, "
            "retry the full transcript fetch up to N more times with longer waits "
            "between waves (default: 3). Use 0 to rely on --max-retries only."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip videos whose transcript file already exists in --out.",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        default=["en"],
        metavar="CODE",
        help="Preferred subtitle languages in priority order (default: en)",
    )
    parser.add_argument(
        "--strict-lang",
        action="store_true",
        help="Only use captions matching --lang list (no unrelated fallbacks)",
    )
    parser.add_argument(
        "--format",
        choices=("lines", "paragraph"),
        default="lines",
        help="How segments are joined into .txt output (default: lines)",
    )
    parser.add_argument(
        "--skip-log",
        default="skipped.jsonl",
        metavar="FILENAME",
        help="JSONL skip/fail reasons inside output dir (default: skipped.jsonl)",
    )
    parser.add_argument(
        "--retry-from-skip-log",
        default=None,
        metavar="PATH",
        help=(
            "Retry downloads for video_id rows in a skipped.jsonl-style file "
            "(do not pass a channel URL when using this). Uses title from each line "
            "for filenames; combined with --resume to skip IDs that already have a .txt in --out."
        ),
    )
    parser.add_argument(
        "--proxy",
        default=None,
        metavar="URL",
        help=(
            "HTTP/HTTPS proxy for transcript requests (same URL for both), e.g. "
            "http://user:pass@p.webshare.io:80/ — same as requests proxies for http+https. "
            "If omitted, TRANSCRIPT_PROXY from the environment / .env is used. "
            "Ignored if --proxy-file or Webshare rotating is set."
        ),
    )
    parser.add_argument(
        "--proxy-file",
        default=None,
        metavar="PATH",
        help=(
            "Text file: one proxy per line as host:port:user:pass (Webshare export) "
            "or http://user:pass@host:port. Proxies rotate round-robin per video. "
            "Not used with --webshare-user/--webshare-password (rotating residential)."
        ),
    )
    parser.add_argument(
        "--webshare-user",
        default=None,
        metavar="NAME",
        help=(
            "Webshare **rotating residential** proxy username (from "
            "dashboard.webshare.io proxy settings). Pair with --webshare-password or "
            "WEBSHARE_PROXY_USERNAME / WEBSHARE_PROXY_PASSWORD. "
            "Conflicts with --proxy and --proxy-file."
        ),
    )
    parser.add_argument(
        "--webshare-password",
        default=None,
        metavar="PASS",
        help="Webshare proxy password (rotating residential; see --webshare-user).",
    )
    parser.add_argument(
        "--webshare-locations",
        default="",
        metavar="CC,...",
        help=(
            "Optional comma-separated ISO country codes to limit the residential IP pool "
            "(e.g. US,DE). **Omit or leave empty to allow all available locations** "
            "(Webshare’s full pool). See Webshare proxy locations documentation."
        ),
    )
    parser.add_argument(
        "--webshare-retries-when-blocked",
        type=int,
        default=10,
        metavar="N",
        help=(
            "429 retries for Webshare rotating mode (default 10); helps rotate to a "
            "new IP after a blocked request."
        ),
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Process at most N videos from the enumerated upload list "
            "(default: all). Order is whatever yt-dlp returns for this channel."
        ),
    )
    parser.add_argument(
        "--no-xlsx",
        action="store_true",
        help="Do not write the summary .xlsx workbook (plain .txt files only).",
    )
    parser.add_argument(
        "--xlsx",
        default="transcripts.xlsx",
        metavar="PATH",
        help=(
            "Path for the Excel workbook (.xlsx): real title, sanitized filename, "
            "video id, transcript (default: transcripts.xlsx inside --out)."
        ),
    )
    parser.add_argument(
        "--simplepush-key",
        default=None,
        metavar="KEY",
        help=(
            "Simplepush key for notifications (IP-ban stop and when the full run "
            "finishes); overrides SIMPLEPUSH_KEY and .env variable 56F6LP. "
            "Env SIMPLEPUSH_KEY or 56F6LP also work."
        ),
    )
    parser.add_argument(
        "--simplepush-title",
        default="YouTube transcripts",
        help="Simplepush notification title (default: YouTube transcripts)",
    )
    parser.add_argument(
        "--simplepush-event",
        default="",
        help=(
            "Optional Simplepush event id — must match an event in your Simplepush app; "
            "if omitted, a default notification is used."
        ),
    )
    parser.add_argument(
        "--test-simplepush",
        action="store_true",
        help="Send one test Simplepush message and exit (use to verify .env key and API).",
    )
    parser.add_argument(
        "--continue-on-ip-ban",
        action="store_true",
        help=(
            "Do not stop when IpBlocked/RequestBlocked; keep going like before "
            "(default: exit as soon as an IP ban is hit after retries)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    load_env_files()
    args = parse_args(argv)

    if args.test_simplepush:
        sk = resolve_simplepush_key(args)
        if not sk:
            print(
                "error: Simplepush test needs a key: use --simplepush-key, or set "
                "SIMPLEPUSH_KEY / 56F6LP in the environment or a .env file "
                f"next to this script ({Path(__file__).resolve().parent}) or in cwd ({Path.cwd()}).",
                file=sys.stderr,
            )
            return 2
        print("Simplepush: sending test notification…", file=sys.stderr)
        notify_simplepush(
            sk,
            args.simplepush_title,
            "Test from download_channel_transcripts.py",
            args.simplepush_event or None,
        )
        print("Simplepush: done — check your device (errors print above as warnings).", file=sys.stderr)
        return 0

    retry_skip_raw = (args.retry_from_skip_log or "").strip()
    channel_raw = args.channel or args.channel_opt

    if retry_skip_raw and channel_raw:
        print(
            "error: use either a channel URL or --retry-from-skip-log, not both.",
            file=sys.stderr,
        )
        return 2

    if not retry_skip_raw and not channel_raw:
        print(
            "error: provide a channel URL (positional or --channel), or "
            "--retry-from-skip-log PATH",
            file=sys.stderr,
        )
        return 2

    langs = tuple(str(x).strip() for x in args.lang if str(x).strip())
    if not langs:
        print("error: at least one --lang code required", file=sys.stderr)
        return 2

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    skip_path = out_dir / args.skip_log

    if retry_skip_raw:
        retry_path = Path(retry_skip_raw).expanduser()
        if not retry_path.is_file():
            print(
                f"error: --retry-from-skip-log not found: {retry_path.resolve()}",
                file=sys.stderr,
            )
            return 2
        videos = load_retry_videos_from_skip_log(retry_path.resolve())
        if not videos:
            print(
                "error: no rows with a valid 11-character video_id in that file.",
                file=sys.stderr,
            )
            return 2
        listed_total = len(videos)
        if args.limit is not None:
            if args.limit < 1:
                print("error: --limit must be a positive integer", file=sys.stderr)
                return 2
            videos = videos[: args.limit]
            print(
                f"Retrying {len(videos)} of {listed_total} video(s) from {retry_path.resolve()}",
            )
        else:
            print(f"Retrying {listed_total} video(s) from {retry_path.resolve()}")
    else:
        normalized = normalize_channel_uploads_url(channel_raw)
        print(f"Resolving uploads from: {normalized}")
        videos = list_channel_videos(normalized)
        if not videos:
            print(
                "No videos found — check URL (use /videos tab for full uploads).\n",
                file=sys.stderr,
            )
            return 1

        listed_total = len(videos)
        if args.limit is not None:
            if args.limit < 1:
                print("error: --limit must be a positive integer", file=sys.stderr)
                return 2
            videos = videos[: args.limit]
            print(
                f"Processing first {len(videos)} video(s) of {listed_total} listed on the channel.",
            )

    stats = {
        "downloaded": 0,
        "skipped_existing": 0,
        "skipped_no_transcript": 0,
        "failed_ip_block": 0,
        "failed": 0,
    }

    try:
        ws_creds = resolve_webshare_credentials(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    use_webshare = ws_creds is not None
    cli_proxy = (args.proxy or "").strip()
    if use_webshare and (cli_proxy or args.proxy_file):
        print(
            "error: Webshare rotating residential (--webshare-user + --webshare-password "
            "or WEBSHARE_PROXY_*) cannot be combined with --proxy or --proxy-file.",
            file=sys.stderr,
        )
        return 2

    env_transcript_proxy = (os.environ.get("TRANSCRIPT_PROXY") or "").strip()
    if use_webshare and env_transcript_proxy and not cli_proxy:
        print(
            "warning: TRANSCRIPT_PROXY is set in the environment or .env, but Webshare "
            "rotating mode is in use — that generic proxy URL is ignored. "
            "Unset TRANSCRIPT_PROXY to silence this message.",
            file=sys.stderr,
        )

    single_proxy_url = (
        None if use_webshare else effective_transcript_proxy_url(args)
    )

    proxy_urls: list[str] = []
    if not use_webshare and args.proxy_file:
        proxy_path = resolve_proxy_file_path(args.proxy_file)
        if not proxy_path.is_file():
            print(f"error: --proxy-file not found: {proxy_path}", file=sys.stderr)
            return 2
        proxy_urls = parse_proxy_file_contents(proxy_path.read_text(encoding="utf-8"))
        if not proxy_urls:
            print(
                "error: --proxy-file has no valid proxy lines "
                "(expected host:port:user:pass or an http(s) URL per line).",
                file=sys.stderr,
            )
            return 2
        print(
            f"Using {len(proxy_urls)} proxy/proxies from {proxy_path} (round-robin per video).",
            file=sys.stderr,
        )
        if single_proxy_url:
            print(
                "warning: --proxy / TRANSCRIPT_PROXY is ignored when --proxy-file is set.",
                file=sys.stderr,
            )

    if use_webshare:
        ws_user, ws_pass = ws_creds
        loc_raw = (args.webshare_locations or "").strip()
        location_codes = [
            p.strip().upper()
            for p in loc_raw.replace(" ", "").split(",")
            if p.strip()
        ]
        shared_api = make_webshare_rotating_api(
            ws_user,
            ws_pass,
            location_codes=location_codes,
            retries_when_blocked=args.webshare_retries_when_blocked,
        )
        print(
            "Transcript API: Webshare rotating residential proxy (p.webshare.io). "
            "Use a Webshare Residential plan (not static datacenter IP lists).",
            file=sys.stderr,
        )
        if location_codes:
            print(
                f"  Webshare country filter: {', '.join(location_codes)}",
                file=sys.stderr,
            )
    else:
        shared_api = make_transcript_api(
            single_proxy_url if not proxy_urls else None
        )
        if single_proxy_url and not proxy_urls:
            src = "--proxy" if (args.proxy or "").strip() else "TRANSCRIPT_PROXY"
            print(
                f"Transcript API: HTTP+HTTPS proxy via {src} (p.webshare.io-style URL supported).",
                file=sys.stderr,
            )

    simplepush_key = resolve_simplepush_key(args)
    if simplepush_key:
        print("Simplepush: key loaded — notifications on IP ban and on full run complete.", file=sys.stderr)

    def backoff(attempt_no: int) -> float:
        return min(60.0, 2.0**attempt_no)

    xlsx_out: Path | None = None
    xlsx_ws = None
    if not args.no_xlsx:
        xlsx_out = resolve_xlsx_output_path(args.xlsx, out_dir)
        from openpyxl import Workbook

        xlsx_wb = Workbook(write_only=True)
        xlsx_ws = xlsx_wb.create_sheet(title="Transcripts")
        xlsx_ws.append(
            ["Real title", "Filename", "Video ID", "Video URL", "Transcript"]
        )
    else:
        xlsx_wb = None

    def append_xlsx_row(
        real_title: str,
        file_name: str,
        vid: str,
        video_url: str,
        transcript: str,
    ) -> None:
        if xlsx_ws is None:
            return
        xlsx_ws.append(
            [
                real_title,
                file_name,
                vid,
                video_url,
                clip_text_for_excel_cell(transcript),
            ]
        )

    stopped_for_ip_ban = False
    skip_log_seen = load_skip_log_video_ids(skip_path)
    with skip_path.open("a", encoding="utf-8") as skip_f:
        for index, (video_id, title) in enumerate(videos, start=1):
            if proxy_urls:
                api = make_transcript_api(proxy_urls[(index - 1) % len(proxy_urls)])
            else:
                api = shared_api

            filename = build_output_filename(title, video_id)
            dest = out_dir / filename
            transcript_for_sheet = ""
            stop_after_ban = False
            ban_notice = ""

            if args.resume and dest.exists():
                stats["skipped_existing"] += 1
                print(f"[{index}/{len(videos)}] SKIP (resume) {video_id} -> {filename}")
                try:
                    transcript_for_sheet = dest.read_text(encoding="utf-8")
                except OSError:
                    transcript_for_sheet = ""
                append_xlsx_row(
                    title,
                    filename,
                    video_id,
                    youtube_watch_url(video_id),
                    transcript_for_sheet,
                )
                continue

            display_title = title if len(title) <= 120 else title[:117] + "..."
            print(f"[{index}/{len(videos)}] {video_id}: {display_title}")

            try:
                ft = fetch_transcript_with_ip_ban_waves(
                    api,
                    video_id,
                    langs,
                    strict_lang=args.strict_lang,
                    max_retries=args.max_retries,
                    sleep_secs=backoff,
                    ip_ban_retries=max(0, args.ip_ban_retries),
                )
                body = transcript_to_text(ft, args.format)
                if body and not body.endswith("\n"):
                    body += "\n"
                dest.write_text(body, encoding="utf-8")
                stats["downloaded"] += 1
                transcript_for_sheet = body
                time.sleep(max(0.0, args.delay))
            except NoTranscriptFound:
                stats["skipped_no_transcript"] += 1
                write_jsonl_skipped(
                    skip_f,
                    {
                        "video_id": video_id,
                        "title": title,
                        "reason": "no_matching_transcript",
                    },
                    skip_log_seen,
                )
            except TranscriptsDisabled:
                stats["skipped_no_transcript"] += 1
                write_jsonl_skipped(
                    skip_f,
                    {"video_id": video_id, "title": title, "reason": "transcripts_disabled"},
                    skip_log_seen,
                )
            except (VideoUnavailable, VideoUnplayable, AgeRestricted) as exc:
                stats["skipped_no_transcript"] += 1
                write_jsonl_skipped(
                    skip_f,
                    {
                        "video_id": video_id,
                        "title": title,
                        "reason": type(exc).__name__,
                    },
                    skip_log_seen,
                )
            except (IpBlocked, RequestBlocked) as exc:
                stats["failed_ip_block"] += 1
                write_jsonl_skipped(
                    skip_f,
                    {
                        "video_id": video_id,
                        "title": title,
                        "reason": type(exc).__name__,
                        "detail": str(exc),
                    },
                    skip_log_seen,
                )
                ban_notice = (
                    f"Stopping: {type(exc).__name__} at {index}/{len(videos)} "
                    f"— {video_id}"
                )
                notify_simplepush(
                    simplepush_key,
                    args.simplepush_title,
                    f"{ban_notice}\n{title[:300]}",
                    args.simplepush_event or None,
                )
                if not simplepush_key:
                    print(
                        "Simplepush: no key configured; no push sent. "
                        "Set SIMPLEPUSH_KEY or 56F6LP in .env, then run with --test-simplepush.",
                        file=sys.stderr,
                    )
                if not args.continue_on_ip_ban:
                    stop_after_ban = True
            except YouTubeTranscriptApiException as exc:
                stats["failed"] += 1
                write_jsonl_skipped(
                    skip_f,
                    {
                        "video_id": video_id,
                        "title": title,
                        "reason": type(exc).__name__,
                        "detail": str(exc),
                    },
                    skip_log_seen,
                )
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                stats["failed"] += 1
                write_jsonl_skipped(
                    skip_f,
                    {
                        "video_id": video_id,
                        "title": title,
                        "reason": "proxy_or_network_error",
                        "detail": str(exc),
                    },
                    skip_log_seen,
                )
            except OSError as exc:
                stats["failed"] += 1
                write_jsonl_skipped(
                    skip_f,
                    {
                        "video_id": video_id,
                        "title": title,
                        "reason": (
                            "proxy_or_network_error"
                            if _oserror_is_network_stack(exc)
                            else "filesystem_error"
                        ),
                        "detail": str(exc),
                    },
                    skip_log_seen,
                )
            append_xlsx_row(
                title,
                filename,
                video_id,
                youtube_watch_url(video_id),
                transcript_for_sheet,
            )
            if stop_after_ban:
                print(f"\n{ban_notice}", file=sys.stderr)
                stopped_for_ip_ban = True
                break

    if xlsx_wb is not None and xlsx_out is not None:
        xlsx_out.parent.mkdir(parents=True, exist_ok=True)
        xlsx_wb.save(str(xlsx_out))

    if not stopped_for_ip_ban and simplepush_key and len(videos) > 0:
        done_title = f"{args.simplepush_title} — finished"
        done_body = (
            f"Processed all {len(videos)} video(s) in this run. "
            f"Downloaded: {stats['downloaded']}, "
            f"skipped (already on disk): {stats['skipped_existing']}, "
            f"skipped (no captions/unavailable): {stats['skipped_no_transcript']}, "
            f"failed: {stats['failed'] + stats['failed_ip_block']}. "
            f"Output: {out_dir}"
        )
        notify_simplepush(
            simplepush_key,
            done_title,
            done_body,
            args.simplepush_event or None,
        )

    print("\nDone.")
    if stopped_for_ip_ban:
        print("Run ended early: IP ban (IpBlocked/RequestBlocked) after retries.")
    print(f"Downloaded now:               {stats['downloaded']}")
    print(f"Skipped (already on disk):    {stats['skipped_existing']}")
    print(f"Skipped (no captions/other):  {stats['skipped_no_transcript']}")
    print(f"Failed (IP blocked):        {stats['failed_ip_block']}")
    print(f"Failed (other errors):        {stats['failed']}")
    if retry_skip_raw:
        print(f"Videos from retry list:       {listed_total}")
    else:
        print(f"Videos listed (channel):      {listed_total}")
    print(f"Videos in this run:           {len(videos)}")
    print(f"Output directory:             {out_dir}")
    print(f"Skip/fail log:                {skip_path}")
    if xlsx_out is not None:
        print(f"Excel workbook:               {xlsx_out}")
    total_fail = stats["failed"] + stats["failed_ip_block"]
    if stats["failed_ip_block"] > 0 and not stopped_for_ip_ban:
        print(
            "\nIpBlocked / RequestBlocked: YouTube is rejecting transcript requests "
            "from your network IP. Channel listing still works (yt-dlp), but captions "
            "use a different endpoint. Try: wait and rerun with a higher --delay, "
            "use another network/VPN exit, or pass --proxy with a residential proxy "
            "(see youtube-transcript-api README).",
            file=sys.stderr,
        )
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
