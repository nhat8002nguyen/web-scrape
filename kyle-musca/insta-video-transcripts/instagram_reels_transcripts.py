#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import random
import signal
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlparse

import requests

INVALID_FS_CHARS_RE = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
OUTPUT_ID_RE = re.compile(r"__(\d+)\.txt$")


@dataclass
class ReelVideo:
    mediaid: str
    shortcode: str
    title: str
    video_url: str
    post_url: str
    date_utc: str


@dataclass
class ProcessItemOutcome:
    outcome: str  # transcribed | skipped | failed
    downloaded: bool = False


class ProxyPool:
    def __init__(self, proxy_urls: list[str], mode: str) -> None:
        clean = [x.strip() for x in proxy_urls if x.strip()]
        self._urls = clean
        self._mode = mode
        self._cycler = cycle(self._urls) if self._urls else None

    def next_url(self) -> str | None:
        if not self._urls:
            return None
        if self._mode == "single":
            return self._urls[0]
        if self._cycler is None:
            return self._urls[0]
        return next(self._cycler)

    @staticmethod
    def as_requests_proxies(proxy_url: str | None) -> dict[str, str] | None:
        if not proxy_url:
            return None
        return {"http": proxy_url, "https": proxy_url}


def load_env_files() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    script_env = Path(__file__).resolve().parent / ".env"
    cwd_env = Path.cwd() / ".env"
    seen: set[Path] = set()

    if script_env.is_file():
        load_dotenv(script_env)
        seen.add(script_env.resolve())
    if cwd_env.is_file() and cwd_env.resolve() not in seen:
        load_dotenv(cwd_env, override=True)

    _sync_hf_hub_token_env()


def _sync_hf_hub_token_env() -> None:
    """huggingface_hub (faster-whisper downloads) reads HF_TOKEN / HUGGING_FACE_HUB_TOKEN."""
    if (os.environ.get("HF_TOKEN") or "").strip():
        return
    if (os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip():
        return
    legacy = (os.environ.get("HUGGINGFACE_TOKEN") or "").strip()
    if legacy:
        os.environ["HF_TOKEN"] = legacy


def _env_optional_int(name: str) -> int | None:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_proxy_file_contents(text: str) -> list[str]:
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


def sanitize_title(title: str, max_length: int = 120) -> str:
    s = INVALID_FS_CHARS_RE.sub("_", title or "")
    s = " ".join(s.split())
    if not s:
        s = "untitled"
    if len(s) > max_length:
        s = s[:max_length].rstrip(" _.")
    return s or "untitled"


def build_output_filename(title: str, mediaid: str) -> str:
    return f"{sanitize_title(title)}__{mediaid}.txt"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class JobTimeoutError(RuntimeError):
    """Raised when --item-timeout-seconds elapses during download/transcribe (Unix SIGALRM)."""


@contextlib.contextmanager
def item_timeout_section(seconds: int | None) -> Iterable[None]:
    """Best-effort wall clock for one item; may not interrupt low-level C/GPU work immediately."""
    if seconds is None or int(seconds) <= 0:
        yield
        return
    sec = int(seconds)
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _handler(_signum: int, _frame: object) -> None:  # noqa: ARG001
        raise JobTimeoutError(f"exceeded {sec}s (--item-timeout-seconds)")

    previous = signal.signal(signal.SIGALRM, _handler)
    try:
        signal.alarm(sec)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def extract_username(target: str) -> str:
    raw = target.strip()
    if not raw:
        raise ValueError("target must not be empty")
    if "://" not in raw:
        return raw.lstrip("@")
    parsed = urlparse(raw)
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        raise ValueError(f"Cannot infer username from target: {target}")
    if parts[0] == "reels" and len(parts) > 1:
        return parts[1]
    return parts[0].lstrip("@")


def build_webshare_proxy_url(
    username: str,
    password: str,
    host: str,
    port: int,
) -> str:
    u = quote(username.strip(), safe="")
    p = quote(password.strip(), safe="")
    return f"http://{u}:{p}@{host.strip()}:{int(port)}"


def mask_proxy_url(proxy_url: str) -> str:
    parsed = urlparse(proxy_url)
    netloc = parsed.netloc
    if "@" in netloc:
        auth, host = netloc.rsplit("@", 1)
        if ":" in auth:
            user = auth.split(":", 1)[0]
            netloc = f"{user}:***@{host}"
        else:
            netloc = f"{auth}:***@{host}"
    return parsed._replace(netloc=netloc).geturl()


def resolve_proxy_urls(args: argparse.Namespace) -> list[str]:
    if getattr(args, "no_proxy", False):
        return []
    if args.proxy_url and args.proxy_file:
        raise ValueError("Use either --proxy-url or --proxy-file, not both.")

    ws_user = (args.webshare_user or "").strip() or (
        os.environ.get("WEBSHARE_PROXY_USERNAME") or ""
    ).strip()
    ws_password = (args.webshare_password or "").strip() or (
        os.environ.get("WEBSHARE_PROXY_PASSWORD") or ""
    ).strip()
    ws_host = (args.webshare_host or "").strip() or (
        os.environ.get("WEBSHARE_PROXY_HOST") or "p.webshare.io"
    ).strip()
    ws_port_raw = (str(args.webshare_port) if args.webshare_port else "").strip() or (
        os.environ.get("WEBSHARE_PROXY_PORT") or "80"
    ).strip()

    if (ws_user and not ws_password) or (ws_password and not ws_user):
        raise ValueError(
            "Webshare credentials require both username and password "
            "(--webshare-user + --webshare-password or env WEBSHARE_PROXY_*)."
        )

    if ws_user and ws_password:
        return [
            build_webshare_proxy_url(
                username=ws_user,
                password=ws_password,
                host=ws_host,
                port=int(ws_port_raw),
            )
        ]

    if args.proxy_url:
        return [args.proxy_url.strip()]

    if args.proxy_file:
        proxy_file = Path(args.proxy_file).expanduser().resolve()
        if not proxy_file.is_file():
            raise ValueError(f"Proxy file not found: {proxy_file}")
        urls = parse_proxy_file_contents(
            proxy_file.read_text(encoding="utf-8"))
        if not urls:
            raise ValueError(
                "Proxy file has no valid entries. Expected URL or host:port:user:pass per line."
            )
        return urls

    env_proxy = (os.environ.get("TRANSCRIPT_PROXY") or "").strip()
    if env_proxy:
        return [env_proxy]
    return []


def resolve_simplepush_key(args: argparse.Namespace) -> str | None:
    return (
        (args.simplepush_key or "").strip()
        or (os.environ.get("SIMPLEPUSH_KEY") or "").strip()
        or (os.environ.get("56F6LP") or "").strip()
        or None
    )


def notify_simplepush(key: str | None, title: str, message: str, event: str | None) -> None:
    if not key:
        return
    try:
        from simplepush import send

        kwargs: dict[str, object] = {
            "title": title, "ignore_connection_errors": False}
        if event:
            kwargs["event"] = event
        send(key, message, **kwargs)
    except Exception as exc:
        print(
            f"warning: Simplepush notification failed: {exc}", file=sys.stderr)


def append_jsonl(path: Path, obj: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_checkpoint(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"processed_mediaids": [], "last_mediaid": None, "updated_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed_mediaids": [], "last_mediaid": None, "updated_at": None}
    if not isinstance(data, dict):
        return {"processed_mediaids": [], "last_mediaid": None, "updated_at": None}
    processed = data.get("processed_mediaids")
    if not isinstance(processed, list):
        processed = []
    return {
        "processed_mediaids": [str(x) for x in processed if str(x).strip()],
        "last_mediaid": data.get("last_mediaid"),
        "updated_at": data.get("updated_at"),
    }


def save_checkpoint(path: Path, processed_mediaids: set[str], last_mediaid: str | None) -> None:
    payload = {
        "processed_mediaids": sorted(processed_mediaids),
        "last_mediaid": last_mediaid,
        "updated_at": timestamp_now(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False,
                    indent=2) + "\n", encoding="utf-8")


def load_existing_transcript_mediaids(transcript_dir: Path) -> set[str]:
    seen: set[str] = set()
    if not transcript_dir.is_dir():
        return seen
    for entry in transcript_dir.glob("*.txt"):
        m = OUTPUT_ID_RE.search(entry.name)
        if m:
            seen.add(m.group(1))
    return seen


def sleep_jitter(min_seconds: float, max_seconds: float) -> None:
    lo = max(0.0, min_seconds)
    hi = max(lo, max_seconds)
    time.sleep(random.uniform(lo, hi))


def exponential_backoff(attempt: int, base: float, max_seconds: float) -> float:
    return min(max_seconds, base ** max(1, attempt))


def post_title(post) -> str:
    caption = (post.caption or "").strip()
    if caption:
        first_line = caption.splitlines()[0].strip()
        if first_line:
            return first_line
    return f"reel_{post.shortcode}"


def post_url(post) -> str:
    if post.is_video:
        return f"https://www.instagram.com/reel/{post.shortcode}/"
    return f"https://www.instagram.com/p/{post.shortcode}/"


def reel_video_from_clips_media(media: dict, context=None) -> ReelVideo | None:
    if media.get("media_type") != 2 and media.get("product_type") != "clips":
        return None
    shortcode = str(media.get("code") or "").strip()
    mediaid = str(media.get("pk") or "").strip()
    if not mediaid and media.get("id"):
        mediaid = str(media["id"]).split("_", 1)[0]
    if not shortcode or not mediaid:
        return None
    video_versions = media.get("video_versions") or []
    video_url = str(video_versions[-1]["url"]) if video_versions else ""
    if not video_url and context is not None:
        try:
            raw = context.get_json(f"api/v1/media/{mediaid}/info/", params={})
            items = (raw or {}).get("items") or []
            versions = (items[0].get("video_versions") or []) if items else []
            if versions:
                video_url = str(versions[-1]["url"])
        except Exception:
            pass
    caption = media.get("caption")
    caption_text = caption.get("text") if isinstance(caption, dict) else None
    if caption_text and str(caption_text).strip():
        title = str(caption_text).strip().splitlines()[0].strip()
    else:
        title = f"reel_{shortcode}"
    taken_at = media.get("taken_at") or media.get("device_timestamp")
    if taken_at is not None:
        date_utc = str(dt.datetime.utcfromtimestamp(int(taken_at)))
    else:
        date_utc = ""
    return ReelVideo(
        mediaid=mediaid,
        shortcode=shortcode,
        title=title,
        video_url=video_url,
        post_url=f"https://www.instagram.com/reel/{shortcode}/",
        date_utc=date_utc,
    )


def iter_clips_reel_videos(profile) -> Iterable[ReelVideo]:
    from instaloader.nodeiterator import NodeIterator

    iterator = NodeIterator(
        context=profile._context,
        edge_extractor=lambda d: d["data"]["xdt_api__v1__clips__user__connection_v2"],
        node_wrapper=lambda n: reel_video_from_clips_media(
            n.get("media") or {}, context=profile._context
        ),
        query_variables={
            "data": {
                "page_size": 12,
                "include_feed_video": True,
                "target_user_id": str(profile.userid),
            }
        },
        query_referer=f"https://www.instagram.com/{profile.username}/",
        is_first=None,
        doc_id=INSTAGRAM_CLIPS_USER_DOC_ID,
        query_hash=None,
    )
    for item in iterator:
        if item is not None:
            yield item


def iter_reel_candidates(
    loader,
    username: str,
    mode: str,
    *,
    start_after_mediaid: str | None,
    limit: int | None,
    max_items_per_run: int | None,
    request_delay_min: float,
    request_delay_max: float,
    verbose: bool,
) -> Iterable[ReelVideo]:
    import instaloader

    patch_instaloader()
    profile = instaloader.Profile.from_username(loader.context, username)

    iterator: Iterable
    if mode == "reels" and hasattr(profile, "get_reels"):
        try:
            iterator = iter_clips_reel_videos(profile)
        except Exception:
            try:
                iterator = profile.get_reels()
            except Exception:
                iterator = profile.get_posts()
    else:
        iterator = profile.get_posts()

    seen: set[str] = set()
    skip_until_found = start_after_mediaid is not None

    if limit is not None and max_items_per_run is not None:
        cap = min(limit, max_items_per_run)
    else:
        cap = limit if limit is not None else max_items_per_run

    n_collected = 0
    for post in iterator:
        sleep_jitter(request_delay_min, request_delay_max)
        if isinstance(post, ReelVideo):
            item = post
            if not item.mediaid:
                continue
        else:
            if not getattr(post, "is_video", False):
                continue
            item = ReelVideo(
                mediaid=str(post.mediaid),
                shortcode=str(post.shortcode),
                title=post_title(post),
                video_url=str(post.video_url),
                post_url=post_url(post),
                date_utc=str(post.date_utc),
            )
        mediaid = item.mediaid
        if mediaid in seen:
            continue
        seen.add(mediaid)

        if skip_until_found:
            if mediaid == str(start_after_mediaid):
                skip_until_found = False
            continue

        n_collected += 1
        if verbose:
            print(
                f"queued: {item.mediaid} {item.shortcode} {sanitize_title(item.title)}",
                file=sys.stderr,
                flush=True,
            )
        yield item

        if cap is not None and n_collected >= cap:
            break


def fetch_reel_candidates(
    loader,
    username: str,
    mode: str,
    *,
    start_after_mediaid: str | None,
    limit: int | None,
    max_items_per_run: int | None,
    request_delay_min: float,
    request_delay_max: float,
    verbose: bool,
) -> list[ReelVideo]:
    return list(
        iter_reel_candidates(
            loader,
            username,
            mode,
            start_after_mediaid=start_after_mediaid,
            limit=limit,
            max_items_per_run=max_items_per_run,
            request_delay_min=request_delay_min,
            request_delay_max=request_delay_max,
            verbose=verbose,
        )
    )


def download_video(
    item: ReelVideo,
    video_path: Path,
    *,
    proxy_url: str | None,
    timeout_seconds: int,
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
    verbose: bool,
) -> None:
    proxies = ProxyPool.as_requests_proxies(proxy_url)
    for attempt in range(1, max_retries + 2):
        try:
            with requests.get(
                item.video_url,
                stream=True,
                timeout=timeout_seconds,
                proxies=proxies,
            ) as response:
                response.raise_for_status()
                with video_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            handle.write(chunk)
            return
        except Exception:
            if attempt >= max_retries + 1:
                raise
            wait = exponential_backoff(attempt, backoff_base, backoff_max)
            if verbose:
                print(
                    f"retry download {item.mediaid} attempt {attempt}/{max_retries + 1} wait={wait:.1f}s",
                    file=sys.stderr,
                )
            time.sleep(wait)


def write_sidecar_metadata(path: Path, item: ReelVideo, video_path: Path) -> None:
    payload = {
        "mediaid": item.mediaid,
        "shortcode": item.shortcode,
        "title": item.title,
        "post_url": item.post_url,
        "video_url": item.video_url,
        "date_utc": item.date_utc,
        "video_file": str(video_path),
        "captured_at": timestamp_now(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False,
                    indent=2) + "\n", encoding="utf-8")


def huggingface_cache_hub_dir() -> str:
    hf_home = os.environ.get("HF_HOME", "").strip() or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface"
    )
    return os.path.join(os.path.expanduser(hf_home), "hub")


def _whisper_heartbeat(stop: threading.Event, label: str, hub_dir: str) -> None:
    """Periodic stderr lines so long first-time downloads do not look hung."""
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
    """
    Load faster-whisper model. First run may download several GB into Hugging Face cache.
    """
    # Progress bars: respect user disabling, otherwise show Hub transfer progress when supported.
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
        f"Loading Whisper model {args.model_size!r} (device={device}, compute_type={compute_type})…",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  Hugging Face hub cache: {hub_dir}",
        file=sys.stderr,
        flush=True,
    )
    print(
        "  First-time `large-v3` is ~2.5–4 GB over the network; expect on the order of "
        "5–40+ minutes depending on bandwidth, then CPU/GPU load time. "
        "You may see Hugging Face progress bars below; if not, watch that folder’s size "
        "(e.g. `du -sh ~/.cache/huggingface/hub`).",
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


def transcribe_segments(model, video_path: Path, args: argparse.Namespace) -> list[dict[str, object]]:
    segments, _ = model.transcribe(
        str(video_path),
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


def _diarization_load_failed_reason(exc: BaseException) -> str:
    msg = str(exc).strip()
    repos_mentioned = list(dict.fromkeys(
        re.findall(r"pyannote/[A-Za-z0-9._-]+", msg)))
    try:
        from huggingface_hub.errors import GatedRepoError

        if isinstance(exc, GatedRepoError):
            gated_msg = (
                "Hugging Face returned 403 (gated repo). "
                "speaker-diarization-3.1 pulls extra models; accept terms (while logged in) on each of: "
                "https://huggingface.co/pyannote/speaker-diarization-3.1 · "
                "https://huggingface.co/pyannote/segmentation-3.0 · "
                "https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM · "
                "https://huggingface.co/pyannote/speaker-diarization-community-1 — "
                "then use a read token for that same account (HF_TOKEN / --hf-token)."
            )
            if repos_mentioned:
                gated_msg += f" Error mentioned: {', '.join(repos_mentioned)}."
            return gated_msg
    except ImportError:
        pass
    if "403" in msg and "gated" in msg.lower():
        return (
            "Hugging Face blocked a pyannote dependency (gated repo). "
            "Accept terms for speaker-diarization-3.1, segmentation-3.0, wespeaker-voxceleb-resnet34-LM, "
            "and speaker-diarization-community-1; use the same account’s read token."
        )
    return f"{type(exc).__name__}: {msg}"


def load_diarization_pipeline(args: argparse.Namespace):
    if args.disable_diarization:
        return None
    hf_token = (args.hf_token or "").strip()
    if not hf_token:
        hf_token = (os.environ.get("HF_TOKEN") or "").strip()
    if not hf_token:
        hf_token = (os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if not hf_token:
        hf_token = (os.environ.get("HUGGINGFACE_TOKEN") or "").strip()
    if not hf_token:
        return None
    try:
        from pyannote.audio import Pipeline
    except Exception:
        return None

    model_id = "pyannote/speaker-diarization-3.1"
    try:
        try:
            pipeline = Pipeline.from_pretrained(model_id, token=hf_token)
        except TypeError:
            # Older pyannote / huggingface_hub
            pipeline = Pipeline.from_pretrained(
                model_id, use_auth_token=hf_token)
    except Exception as exc:
        print(
            f"warning: pyannote diarization disabled — {_diarization_load_failed_reason(exc)} "
            "Continuing with full Whisper segments.",
            file=sys.stderr,
            flush=True,
        )
        return None

    if args.device == "cuda":
        try:
            import torch

            pipeline.to(torch.device("cuda"))
        except Exception:
            pass
    return pipeline


def _diarization_to_annotation(diarization):
    """pyannote 4.x returns DiarizeOutput; 3.x returned Annotation directly."""
    speaker_ann = getattr(diarization, "speaker_diarization", None)
    if speaker_ann is not None:
        return speaker_ann
    return diarization


def dominant_speaker_ranges(diarization) -> list[tuple[float, float]]:
    ann = _diarization_to_annotation(diarization)
    if not hasattr(ann, "itertracks"):
        return []
    durations: dict[str, float] = {}
    by_speaker: dict[str, list[tuple[float, float]]] = {}
    for turn, _, speaker in ann.itertracks(yield_label=True):
        start = float(turn.start)
        end = float(turn.end)
        if end <= start:
            continue
        durations[speaker] = durations.get(speaker, 0.0) + (end - start)
        by_speaker.setdefault(speaker, []).append((start, end))
    if not durations:
        return []
    dominant = max(durations.items(), key=lambda kv: kv[1])[0]
    return by_speaker.get(dominant, [])


def overlap_duration(a_start: float, a_end: float, spans: list[tuple[float, float]]) -> float:
    total = 0.0
    for b_start, b_end in spans:
        start = max(a_start, b_start)
        end = min(a_end, b_end)
        if end > start:
            total += end - start
    return total


def _ffmpeg_wav_mono_16k(video_path: Path, wav_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip() or "no stderr"
        raise RuntimeError(f"ffmpeg failed ({result.returncode}): {err}")


def keep_dominant_speaker_segments(
    segments: list[dict[str, object]],
    diarization_pipeline,
    video_path: Path,
    overlap_threshold: float,
    *,
    verbose: bool = False,
) -> list[dict[str, object]]:
    if diarization_pipeline is None:
        return segments

    wav_path: Path | None = None
    try:
        media_for_pyannote = str(video_path)
        if video_path.suffix.lower() != ".wav" and shutil.which("ffmpeg"):
            fd, wav_str = tempfile.mkstemp(prefix="pyannote_", suffix=".wav")
            os.close(fd)
            wav_path = Path(wav_str)
            if verbose:
                print(
                    f"diarization: extracting 16 kHz mono wav via ffmpeg ({video_path.name})…",
                    file=sys.stderr,
                    flush=True,
                )
            _ffmpeg_wav_mono_16k(video_path, wav_path)
            media_for_pyannote = str(wav_path)
        elif video_path.suffix.lower() != ".wav" and verbose:
            print(
                "warning: ffmpeg not on PATH; pyannote reads the video file directly "
                "(may raise sample-length errors on some MP4s).",
                file=sys.stderr,
                flush=True,
            )

        diarization = diarization_pipeline(media_for_pyannote)
    except Exception as exc:
        print(
            f"warning: diarization failed ({type(exc).__name__}: {exc}); using full Whisper segments.",
            file=sys.stderr,
            flush=True,
        )
        return segments
    finally:
        if wav_path is not None:
            try:
                if wav_path.is_file():
                    wav_path.unlink()
            except OSError:
                pass

    dominant_ranges = dominant_speaker_ranges(diarization)
    if not dominant_ranges:
        return segments

    kept: list[dict[str, object]] = []
    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        seg_len = max(0.001, end - start)
        ratio = overlap_duration(start, end, dominant_ranges) / seg_len
        if ratio >= overlap_threshold:
            kept.append(seg)
    if kept:
        return kept
    return segments


def reel_video_job_dict(item: ReelVideo) -> dict[str, str]:
    return {
        "mediaid": item.mediaid,
        "shortcode": item.shortcode,
        "title": item.title,
        "video_url": item.video_url,
        "post_url": item.post_url,
        "date_utc": item.date_utc,
    }


def reel_video_from_job_dict(d: dict[str, object]) -> ReelVideo:
    return ReelVideo(
        mediaid=str(d["mediaid"]),
        shortcode=str(d["shortcode"]),
        title=str(d.get("title") or ""),
        video_url=str(d["video_url"]),
        post_url=str(d.get("post_url") or ""),
        date_utc=str(d.get("date_utc") or ""),
    )


def reel_video_from_metadata_file(path: Path) -> ReelVideo | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    vu = str(data.get("video_url") or "").strip()
    if not vu:
        return None
    try:
        return reel_video_from_job_dict(data)
    except Exception:
        return None


def process_queue_item(
    item: ReelVideo,
    *,
    label: str,
    args: argparse.Namespace,
    whisper_model,
    diarization_pipeline,
    proxy_pool: ProxyPool,
    video_dir: Path,
    transcript_dir: Path,
    metadata_dir: Path,
    checkpoint_path: Path,
    processed_mediaids: set[str],
    skip_log_path: Path,
) -> ProcessItemOutcome:
    title_sanitized = sanitize_title(item.title)
    transcript_name = build_output_filename(item.title, item.mediaid)
    transcript_path = transcript_dir / transcript_name
    video_path = video_dir / f"{item.mediaid}.mp4"
    meta_path = metadata_dir / f"{item.mediaid}.json"

    if args.resume and (item.mediaid in processed_mediaids or transcript_path.exists()):
        processed_mediaids.add(item.mediaid)
        save_checkpoint(checkpoint_path, processed_mediaids, item.mediaid)
        if args.verbose:
            print(f"{label} skip resume mediaid={item.mediaid}", file=sys.stderr)
        else:
            print(
                f"{label} skip resume mediaid={item.mediaid} url={item.post_url}",
                file=sys.stderr,
                flush=True,
            )
        return ProcessItemOutcome(outcome="skipped", downloaded=False)

    if args.no_proxy or args.bypass_proxy_downloads:
        proxy_url = None
    else:
        proxy_url = proxy_pool.next_url()
    if args.verbose:
        proxy_msg = mask_proxy_url(proxy_url) if proxy_url else "direct"
        print(
            f"{label} mediaid={item.mediaid} title={title_sanitized} url={item.post_url} proxy={proxy_msg}",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(
            f"{label} mediaid={item.mediaid} url={item.post_url}",
            file=sys.stderr,
            flush=True,
        )

    try:
        with item_timeout_section(args.item_timeout_seconds):
            downloaded = False
            if not video_path.exists():
                download_video(
                    item,
                    video_path,
                    proxy_url=proxy_url,
                    timeout_seconds=args.timeout_seconds,
                    max_retries=args.max_retries,
                    backoff_base=args.retry_backoff_base,
                    backoff_max=args.retry_backoff_max,
                    verbose=args.verbose,
                )
                downloaded = True
            write_sidecar_metadata(meta_path, item, video_path)

            raw_segments = transcribe_segments(whisper_model, video_path, args)
            if not raw_segments:
                append_jsonl(
                    skip_log_path,
                    {
                        "ts": timestamp_now(),
                        "mediaid": item.mediaid,
                        "shortcode": item.shortcode,
                        "title": item.title,
                        "reason": "NoSpeech",
                        "detail": "transcription returned no segments",
                    },
                )
                if args.verbose:
                    print(
                        f"{label} no speech detected mediaid={item.mediaid}",
                        file=sys.stderr,
                        flush=True,
                    )
                transcript_text = build_transcript_text(item, [])
                transcript_path.write_text(transcript_text, encoding="utf-8")
                processed_mediaids.add(item.mediaid)
                save_checkpoint(checkpoint_path, processed_mediaids, item.mediaid)
                if args.delay > 0:
                    time.sleep(args.delay)
                return ProcessItemOutcome(outcome="transcribed", downloaded=downloaded)
            kept_segments = keep_dominant_speaker_segments(
                raw_segments,
                diarization_pipeline,
                video_path,
                overlap_threshold=max(
                    0.0, min(1.0, args.speaker_overlap_threshold)),
                verbose=args.verbose,
            )

            transcript_text = build_transcript_text(item, kept_segments)
            transcript_path.write_text(transcript_text, encoding="utf-8")

            processed_mediaids.add(item.mediaid)
            save_checkpoint(checkpoint_path, processed_mediaids, item.mediaid)

            if args.delay > 0:
                time.sleep(args.delay)

            return ProcessItemOutcome(outcome="transcribed", downloaded=downloaded)
    except JobTimeoutError as exc:
        append_jsonl(
            skip_log_path,
            {
                "ts": timestamp_now(),
                "mediaid": item.mediaid,
                "shortcode": item.shortcode,
                "title": item.title,
                "reason": "JobTimeout",
                "detail": str(exc),
            },
        )
        print(
            f"error {label} mediaid={item.mediaid} reason=JobTimeout: {exc}",
            file=sys.stderr,
        )
        return ProcessItemOutcome(outcome="failed", downloaded=False)
    except Exception as exc:
        append_jsonl(
            skip_log_path,
            {
                "ts": timestamp_now(),
                "mediaid": item.mediaid,
                "shortcode": item.shortcode,
                "title": item.title,
                "reason": type(exc).__name__,
                "detail": str(exc),
            },
        )
        print(
            f"error {label} mediaid={item.mediaid} reason={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return ProcessItemOutcome(outcome="failed", downloaded=False)


def make_redis_client(url: str, *, block_ms: int | None = None):
    """
    Create a redis-py client. For XREADGROUP BLOCK, socket_timeout must exceed
    block_ms (redis-py defaults to 5s, which breaks 30s blocking reads).
    """
    import redis

    kwargs: dict[str, object] = {"decode_responses": True}
    if block_ms is not None:
        kwargs["socket_timeout"] = max(60.0, (block_ms / 1000.0) + 15.0)
    return redis.Redis.from_url(url, **kwargs)


def run_redis_producer(
    args: argparse.Namespace,
    queue: Iterable[ReelVideo],
    *,
    transcript_dir: Path,
    processed_mediaids: set[str],
) -> int:
    try:
        import redis
    except Exception as exc:
        print(
            f"error: redis package not installed ({exc}). pip install redis", file=sys.stderr)
        return 2
    from redis.exceptions import RedisError

    url = (args.redis_url or os.environ.get("REDIS_URL") or "").strip()
    if not url:
        print(
            "error: --redis-url or REDIS_URL required for redis producer", file=sys.stderr)
        return 2
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
    except RedisError as exc:
        print(f"error: Redis connection failed: {exc}", file=sys.stderr)
        return 2

    stream = (args.redis_stream or "insta:reel:jobs").strip()
    dedupe_key = f"{stream}:enqueued" if args.redis_producer_dedupe else None
    enqueued = 0
    skipped = 0
    for item in queue:
        transcript_name = build_output_filename(item.title, item.mediaid)
        transcript_path = transcript_dir / transcript_name
        if args.resume and (item.mediaid in processed_mediaids or transcript_path.exists()):
            skipped += 1
            continue
        if dedupe_key:
            if client.sadd(dedupe_key, item.mediaid) == 0:
                if args.verbose:
                    print(
                        f"redis producer skip (already in {dedupe_key}) mediaid={item.mediaid}",
                        file=sys.stderr,
                    )
                skipped += 1
                continue
        payload = json.dumps(reel_video_job_dict(item), ensure_ascii=False)
        client.xadd(stream, {"job": payload})
        enqueued += 1
        if args.verbose:
            print(
                f"redis XADD {stream} mediaid={item.mediaid}",
                file=sys.stderr,
                flush=True,
            )

    print(
        f"Redis producer: stream={stream} enqueued={enqueued} skipped={skipped} "
        f"(consumer group '{args.redis_group}' is created by the first worker). "
        f"Jobs were pushed incrementally as Instaloader enumerated reels.",
        file=sys.stderr,
    )
    return 0


def run_redis_requeue_skipped(
    args: argparse.Namespace,
    *,
    metadata_dir: Path,
    transcript_dir: Path,
    skip_log_path: Path,
    processed_mediaids: set[str],
) -> int:
    try:
        import redis
    except Exception as exc:
        print(
            f"error: redis package not installed ({exc}). pip install redis", file=sys.stderr)
        return 2
    from redis.exceptions import RedisError

    if not skip_log_path.is_file():
        print(
            f"requeue-skipped: no file at {skip_log_path} (nothing to do).",
            file=sys.stderr,
        )
        return 0

    filt = (args.requeue_reason_contains or "").strip()
    ordered_mids: list[str] = []
    seen: set[str] = set()
    bad_lines = 0
    try:
        for raw_line in skip_log_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                bad_lines += 1
                continue
            if not isinstance(row, dict):
                bad_lines += 1
                continue
            mid = str(row.get("mediaid") or "").strip()
            if not mid:
                bad_lines += 1
                continue
            if filt and filt not in str(row.get("reason") or ""):
                continue
            if mid in seen:
                continue
            seen.add(mid)
            ordered_mids.append(mid)
    except OSError as exc:
        print(f"error: could not read skip log: {exc}", file=sys.stderr)
        return 1

    queue: list[ReelVideo] = []
    missing_meta: list[str] = []
    for mid in ordered_mids:
        item = reel_video_from_metadata_file(metadata_dir / f"{mid}.json")
        if item is None:
            missing_meta.append(mid)
            continue
        queue.append(item)

    if args.dry_run:
        print(f"requeue-skipped dry-run: candidates from log={len(ordered_mids)}", file=sys.stderr)
        if filt:
            print(f"  filter reason contains: {filt!r}", file=sys.stderr)
        if bad_lines:
            print(f"  unparseable lines skipped: {bad_lines}", file=sys.stderr)
        print(f"  would enqueue (have metadata + video_url): {len(queue)}", file=sys.stderr)
        print(f"  missing metadata or video_url: {len(missing_meta)}", file=sys.stderr)
        for item in queue:
            print(f"{item.mediaid} {item.shortcode} {sanitize_title(item.title)}")
        if missing_meta and args.verbose:
            for mid in missing_meta[:50]:
                print(f"missing_meta {mid}", file=sys.stderr)
        return 0

    url = (args.redis_url or os.environ.get("REDIS_URL") or "").strip()
    if not url:
        print(
            "error: --redis-url or REDIS_URL required for requeue-skipped", file=sys.stderr)
        return 2
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
    except RedisError as exc:
        print(f"error: Redis connection failed: {exc}", file=sys.stderr)
        return 2

    stream = (args.redis_stream or "insta:reel:jobs").strip()
    dedupe_key = f"{stream}:enqueued" if args.redis_producer_dedupe else None
    enqueued = 0
    skipped = 0
    for item in queue:
        transcript_name = build_output_filename(item.title, item.mediaid)
        transcript_path = transcript_dir / transcript_name
        if args.resume and (item.mediaid in processed_mediaids or transcript_path.exists()):
            skipped += 1
            continue
        if dedupe_key:
            if client.sadd(dedupe_key, item.mediaid) == 0:
                if args.verbose:
                    print(
                        f"requeue-skipped skip (already in {dedupe_key}) mediaid={item.mediaid}",
                        file=sys.stderr,
                    )
                skipped += 1
                continue
        payload = json.dumps(reel_video_job_dict(item), ensure_ascii=False)
        client.xadd(stream, {"job": payload})
        enqueued += 1
        if args.verbose:
            print(
                f"requeue-skipped XADD {stream} mediaid={item.mediaid}",
                file=sys.stderr,
            )

    print(
        f"requeue-skipped: stream={stream} enqueued={enqueued} skipped={skipped} "
        f"log_entries={len(ordered_mids)} missing_metadata={len(missing_meta)} "
        f"bad_lines={bad_lines}",
        file=sys.stderr,
    )
    if missing_meta:
        preview = ", ".join(missing_meta[:12])
        more = " …" if len(missing_meta) > 12 else ""
        print(
            f"requeue-skipped: {len(missing_meta)} mediaid(s) have no usable "
            f"{metadata_dir.name}/*.json (e.g. failed before sidecar). "
            f"Preview: {preview}{more}",
            file=sys.stderr,
        )
    return 0


def run_redis_worker(
    args: argparse.Namespace,
    *,
    simplepush_key: str | None,
    out_dir: Path,
    video_dir: Path,
    transcript_dir: Path,
    metadata_dir: Path,
    checkpoint_path: Path,
    skip_log_path: Path,
    processed_mediaids: set[str],
    proxy_pool: ProxyPool,
    whisper_model,
    diarization_pipeline,
) -> int:
    try:
        import redis
    except Exception as exc:
        print(
            f"error: redis package not installed ({exc}). pip install redis", file=sys.stderr)
        return 2
    from redis.exceptions import RedisError, ResponseError

    url = (args.redis_url or os.environ.get("REDIS_URL") or "").strip()
    if not url:
        print("error: --redis-url or REDIS_URL required for redis worker",
              file=sys.stderr)
        return 2
    stream = (args.redis_stream or "insta:reel:jobs").strip()
    group = (args.redis_group or "transcribers").strip()
    consumer = (args.redis_consumer_name or "").strip(
    ) or f"{socket.gethostname()}:{os.getpid()}"

    block_ms = max(500, int(args.redis_block_ms))

    try:
        client = make_redis_client(url, block_ms=block_ms)
        client.ping()
    except RedisError as exc:
        err_msg = (
            f"Redis connection failed: {exc}. "
            f"stream={stream!r} group={group!r} consumer={consumer!r}."
        )
        print(f"error: Redis connection failed: {exc}", file=sys.stderr)
        notify_simplepush(
            simplepush_key,
            f"{args.simplepush_title} - worker error",
            err_msg,
            args.simplepush_event or None,
        )
        return 2

    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    idle_exit = args.redis_idle_exit_seconds
    max_jobs = args.redis_max_jobs
    idle_rounds_limit: int | None = None
    if idle_exit is not None and idle_exit > 0:
        idle_rounds_limit = max(1, int((float(idle_exit) * 1000) / block_ms))

    idle_notify_sec = args.redis_idle_notify_seconds
    idle_notify_rounds_limit: int | None = None
    if idle_notify_sec is not None and idle_notify_sec > 0:
        idle_notify_rounds_limit = max(
            1, int((float(idle_notify_sec) * 1000) / block_ms))

    consecutive_errors = 0
    stats = {"transcribed": 0, "skipped": 0, "failed": 0, "downloaded": 0}
    jobs_done = 0
    idle_rounds = 0
    idle_notify_rounds = 0
    exited_for_idle = False

    if args.verbose:
        print(
            f"redis worker: stream={stream} group={group} consumer={consumer} "
            f"block_ms={block_ms}",
            file=sys.stderr,
            flush=True,
        )

    while True:
        try:
            resp = client.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=1,
                block=block_ms,
            )
        except RedisError as exc:
            err_msg = (
                f"Redis XREADGROUP failed: {exc}. "
                f"stream={stream!r} group={group!r} consumer={consumer!r}. "
                f"Jobs processed so far: {jobs_done}."
            )
            print(f"error: Redis XREADGROUP: {exc}", file=sys.stderr)
            notify_simplepush(
                simplepush_key,
                f"{args.simplepush_title} - worker error",
                err_msg,
                args.simplepush_event or None,
            )
            return 1

        if not resp:
            if idle_rounds_limit is not None:
                idle_rounds += 1
                if idle_rounds >= idle_rounds_limit:
                    exited_for_idle = True
                    if args.verbose:
                        print(
                            f"redis worker: idle ~{idle_exit}s with no jobs; exiting.",
                            file=sys.stderr,
                            flush=True,
                        )
                    break
            if idle_notify_rounds_limit is not None:
                idle_notify_rounds += 1
                if idle_notify_rounds >= idle_notify_rounds_limit:
                    approx_sec = int(
                        (idle_notify_rounds_limit * block_ms) / 1000)
                    note = (
                        f"No Redis stream messages for ~{approx_sec}s "
                        f"(stream={stream!r} group={group!r} consumer={consumer!r}). "
                        f"Jobs processed so far: {jobs_done}."
                    )
                    print(f"redis worker: {note}", file=sys.stderr, flush=True)
                    notify_simplepush(
                        simplepush_key,
                        f"{args.simplepush_title} - worker idle",
                        note,
                        args.simplepush_event or None,
                    )
                    idle_notify_rounds = 0
            continue

        idle_rounds = 0
        idle_notify_rounds = 0
        for _sname, messages in resp:
            for msg_id, fields in messages:
                raw = fields.get("job") if isinstance(fields, dict) else None
                if not raw:
                    try:
                        client.xack(stream, group, msg_id)
                    except RedisError:
                        pass
                    continue
                try:
                    item = reel_video_from_job_dict(json.loads(raw))
                except Exception as exc:
                    print(
                        f"error: invalid job {msg_id}: {exc}", file=sys.stderr)
                    try:
                        client.xack(stream, group, msg_id)
                    except RedisError:
                        pass
                    continue

                label = f"[redis {msg_id}]"
                res = process_queue_item(
                    item,
                    label=label,
                    args=args,
                    whisper_model=whisper_model,
                    diarization_pipeline=diarization_pipeline,
                    proxy_pool=proxy_pool,
                    video_dir=video_dir,
                    transcript_dir=transcript_dir,
                    metadata_dir=metadata_dir,
                    checkpoint_path=checkpoint_path,
                    processed_mediaids=processed_mediaids,
                    skip_log_path=skip_log_path,
                )

                try:
                    client.xack(stream, group, msg_id)
                except RedisError as exc:
                    print(
                        f"warning: XACK failed for {msg_id}: {exc}", file=sys.stderr)

                jobs_done += 1
                if res.outcome == "transcribed":
                    stats["transcribed"] += 1
                    if res.downloaded:
                        stats["downloaded"] += 1
                    consecutive_errors = 0
                elif res.outcome == "skipped":
                    stats["skipped"] += 1
                    consecutive_errors = 0
                else:
                    stats["failed"] += 1
                    consecutive_errors += 1
                    backoff_sleep = exponential_backoff(
                        consecutive_errors,
                        args.retry_backoff_base,
                        args.retry_backoff_max,
                    )
                    time.sleep(backoff_sleep)

                if max_jobs is not None and jobs_done >= max_jobs:
                    if args.verbose:
                        print(
                            f"redis worker: --redis-max-jobs={max_jobs} reached; exiting.", file=sys.stderr)
                    summary = (
                        f"Worker done. transcribed={stats['transcribed']} skipped={stats['skipped']} "
                        f"failed={stats['failed']} downloaded={stats['downloaded']} jobs_processed={jobs_done}"
                    )
                    print(summary)
                    notify_simplepush(
                        simplepush_key, f"{args.simplepush_title} - worker", summary, args.simplepush_event or None)
                    return 0 if stats["failed"] == 0 else 1

                if (
                    args.max_consecutive_errors > 0
                    and consecutive_errors >= args.max_consecutive_errors
                ):
                    stop_msg = (
                        f"Redis worker stopping after {consecutive_errors} consecutive errors."
                    )
                    print(stop_msg, file=sys.stderr)
                    notify_simplepush(
                        simplepush_key,
                        args.simplepush_title,
                        stop_msg,
                        args.simplepush_event or None,
                    )
                    return 1

    if exited_for_idle:
        summary = (
            f"Redis worker exited after ~{idle_exit}s idle (no new stream messages). "
            f"stream={stream} group={group} consumer={consumer}. "
            f"jobs_processed={jobs_done} transcribed={stats['transcribed']} "
            f"skipped={stats['skipped']} failed={stats['failed']} "
            f"downloaded={stats['downloaded']}"
        )
    else:
        summary = (
            f"Worker done. transcribed={stats['transcribed']} skipped={stats['skipped']} "
            f"failed={stats['failed']} downloaded={stats['downloaded']} jobs_processed={jobs_done}"
        )
    print(summary)
    notify_simplepush(
        simplepush_key, f"{args.simplepush_title} - worker", summary, args.simplepush_event or None)
    return 0 if stats["failed"] == 0 else 1


def instagram_enumeration_hints(exc: BaseException, *, username: str, used_proxy: bool) -> str:
    """
    Instaloader often reports 'Profile X does not exist' after a 403/blocked GraphQL response.
    Explain that case and suggest fixes.
    """
    msg = str(exc).lower()
    chain = getattr(exc, "__cause__", None)
    if chain is not None:
        msg = f"{msg} {chain}".lower()

    blocked_markers = (
        "403",
        "forbidden",
        "graphql",
        "429",
        "challenge",
        "login",
        "feedback_required",
        "checkpoint",
        "rate",
        "temporarily blocked",
    )
    looks_blocked = any(m in msg for m in blocked_markers)
    misleading_profile = "does not exist" in msg and username.lower() in msg

    lines: list[str] = []
    if looks_blocked or misleading_profile:
        lines.append(
            "Instagram likely blocked or challenged this request (not necessarily that the profile is missing)."
        )
        if used_proxy:
            lines.append(
                "You are using a proxy: datacenter or flagged IPs often get 403 on graphql/query. "
                "Try: (1) residential proxy with country close to the account, "
                "(2) build a session on a clean IP then pass --sessionfile, "
                "(3) use --instagram-user + INSTAGRAM_PASSWORD after accepting any browser checkpoint."
            )
        else:
            lines.append(
                "Try: slow down (--request-delay-*), use --sessionfile from a logged-in Instaloader session, "
                "or log in with --instagram-user + INSTAGRAM_PASSWORD."
            )
    if not lines:
        lines.append(
            "If you saw 403/Forbidden in the logs above, treat it as an access block, not proof the profile is gone."
        )
    return "\n".join(lines)


# Profile PolarisProfilePageContentQuery: 27937681195819736 still returns data.
# Live web JS now also ships 28036671149327607, but that id currently errors.
INSTAGRAM_PROFILE_PAGE_DOC_ID = "27937681195819736"
# Post PolarisPostRootQuery (both this and live 29326377470285825 currently error).
INSTAGRAM_POST_ROOT_DOC_ID = "27128499623469141"
# Clips xdt_api__v1__clips__user__connection_v2 (replaces 7845543455542541).
INSTAGRAM_CLIPS_USER_DOC_ID = "27234427476213202"

_INSTALOADER_TEST_LOGIN_PATCHED = False
_INSTALOADER_FROM_USERNAME_PATCHED = False


def cookie_jar_dict_from_loader(loader) -> dict[str, str]:
    return requests.utils.dict_from_cookiejar(loader.context._session.cookies)


def sync_instaloader_context_user_id_from_cookies(loader) -> None:
    ds_user_id = (cookie_jar_dict_from_loader(loader).get("ds_user_id") or "").strip()
    if not ds_user_id:
        return
    try:
        loader.context.user_id = ds_user_id
    except Exception:
        pass


def patch_instaloader_test_login() -> None:
    """
    Instaloader 4.15.x test_login() uses a retired graphql query_hash
    (d6f4427fbe92d846298cf93df0b937d3) that often returns 401 even when
    session cookies are valid. Try the mobile current_user endpoint first.
    """
    global _INSTALOADER_TEST_LOGIN_PATCHED
    if _INSTALOADER_TEST_LOGIN_PATCHED:
        return
    try:
        from instaloader.instaloadercontext import InstaloaderContext
    except Exception:
        return

    _orig_test_login = InstaloaderContext.test_login

    def _test_login_patched(self):  # type: ignore[no-untyped-def]
        jar = requests.utils.dict_from_cookiejar(self._session.cookies)
        sessionid = (jar.get("sessionid") or "").strip()
        if not sessionid:
            return None
        ds_user_id = (jar.get("ds_user_id") or "").strip()
        if ds_user_id and not getattr(self, "user_id", None):
            try:
                self.user_id = ds_user_id
            except Exception:
                pass

        try:
            resp = self.get_iphone_json(
                "api/v1/accounts/current_user/", {"edit": "true"}
            )
            user = resp.get("user") if isinstance(resp, dict) else None
            username = user.get("username") if isinstance(user, dict) else None
            if username:
                return str(username)
        except Exception:
            pass

        return _orig_test_login(self)

    InstaloaderContext.test_login = _test_login_patched  # type: ignore[method-assign]
    _INSTALOADER_TEST_LOGIN_PATCHED = True


def patch_instaloader_profile_from_username() -> None:
    """
    Instaloader 4.15.3 Profile.from_username() hits web_profile_info first,
    which currently 429s. Resolve the user via topsearch instead.
    """
    global _INSTALOADER_FROM_USERNAME_PATCHED
    if _INSTALOADER_FROM_USERNAME_PATCHED:
        return
    try:
        from instaloader.structures import Profile, TopSearchResults
    except Exception:
        return

    _orig_from_username = Profile.from_username

    @classmethod
    def _from_username_patched(cls, context, username: str):
        uname = (username or "").strip().lstrip("@").lower()
        if uname:
            try:
                for profile in TopSearchResults(context, uname).get_profiles():
                    if str(getattr(profile, "username", "")).lower() == uname:
                        return profile
            except Exception:
                pass
        return _orig_from_username(context, username)

    Profile.from_username = _from_username_patched  # type: ignore[method-assign]
    _INSTALOADER_FROM_USERNAME_PATCHED = True


_INSTALOADER_PROFILE_GRAPHQL_PATCHED = False


def patch_instaloader_profile_graphql() -> None:
    """
    Instaloader 4.15.x profile GraphQL doc_id goes stale when Instagram rotates
    PolarisProfilePageContentQuery. Use the live web JS doc_id.
    """
    global _INSTALOADER_PROFILE_GRAPHQL_PATCHED
    if _INSTALOADER_PROFILE_GRAPHQL_PATCHED:
        return
    try:
        from instaloader.exceptions import ProfileNotExistsException, QueryReturnedNotFoundException
        from instaloader.structures import Profile, TopSearchResults
    except Exception:
        return

    def _obtain_metadata_patched(self: Profile) -> None:
        try:
            if not self._has_full_metadata:
                user_id = self._node.get("id") or self._node.get("pk")
                variables = {
                    "id": str(user_id),
                    "render_surface": "PROFILE",
                    "__relay_internal__pv__PolarisCannesGuardianExperienceEnabledrelayprovider": True,
                    "__relay_internal__pv__PolarisCASB976ProfileEnabledrelayprovider": False,
                    "__relay_internal__pv__PolarisRepostsConsumptionEnabledrelayprovider": False,
                    "__relay_internal__pv__PolarisWebSchoolsEnabledrelayprovider": False,
                    "enable_integrity_filters": True,
                }
                data = self._context.doc_id_graphql_query(
                    INSTAGRAM_PROFILE_PAGE_DOC_ID, variables
                )
                if data is None:
                    raise QueryReturnedNotFoundException(
                        "GraphQL query returned None"
                    )
                user_data = data.get("data", {}).get("user")
                if user_data is None:
                    raise ProfileNotExistsException(
                        f"Profile {self.username} does not exist."
                    )
                self._node = self._normalize_profile_data(user_data)
                self._has_full_metadata = True
        except (QueryReturnedNotFoundException, KeyError) as err:
            top_search_results = TopSearchResults(self._context, self.username)
            similar_profiles = [
                profile.username for profile in top_search_results.get_profiles()
            ]
            if similar_profiles:
                if self.username in similar_profiles:
                    raise ProfileNotExistsException(
                        f"Profile {self.username} seems to exist, but could not be loaded."
                    ) from err
                raise ProfileNotExistsException(
                    "Profile {} does not exist.\nThe most similar profile{}: {}.".format(
                        self.username,
                        "s are" if len(similar_profiles) > 1 else " is",
                        ", ".join(similar_profiles[0:5]),
                    )
                ) from err
            raise ProfileNotExistsException(
                f"Profile {self.username} does not exist."
            ) from err

    Profile._obtain_metadata = _obtain_metadata_patched  # type: ignore[method-assign]
    _INSTALOADER_PROFILE_GRAPHQL_PATCHED = True


_INSTALOADER_POST_METADATA_PATCHED = False


def patch_instaloader_post_metadata() -> None:
    """
    Instaloader 4.15.x uses a retired post GraphQL doc_id (8845758582119845),
    which returns execution error / null data. Use the current doc_id/response
    mapping until upstream ships a fix (https://github.com/instaloader/instaloader/pull/2706).
    """
    global _INSTALOADER_POST_METADATA_PATCHED
    if _INSTALOADER_POST_METADATA_PATCHED:
        return
    try:
        from instaloader.exceptions import BadResponseException, PostChangedException
        from instaloader.structures import Post
    except Exception:
        return

    def _obtain_metadata_patched(self: Post) -> None:
        if not self._full_metadata_dict:
            media_types = {1: "GraphImage", 2: "GraphVideo", 8: "GraphSidecar"}
            resp = self._context.doc_id_graphql_query(
                INSTAGRAM_POST_ROOT_DOC_ID,
                {
                    "shortcode": self.shortcode,
                    "__relay_internal__pv__PolarisAIGMMediaWebLabelEnabledrelayprovider": False,
                },
            )
            web_info = (resp.get("data") or {}).get(
                "xdt_api__v1__media__shortcode__web_info"
            ) or {}
            items = web_info.get("items")
            if not items:
                raise BadResponseException("Fetching Post metadata failed.")
            media = items[0]
            media_type = media.get("media_type")
            typename = media_types.get(media_type)
            if not typename:
                raise BadResponseException(
                    f"Unknown media_type in metadata: {media_type}."
                )
            pic_json: dict[str, object] = {
                "shortcode": media["code"],
                "id": media["pk"],
                "__typename": typename,
                "is_video": media_type == 2,
                "taken_at_timestamp": media["taken_at"],
                "owner": {
                    "id": media["user"]["pk"],
                    "username": media["user"].get("username", ""),
                    "full_name": media["user"].get("full_name", ""),
                },
            }
            candidates = (media.get("image_versions2") or {}).get("candidates") or []
            if candidates:
                pic_json["display_url"] = candidates[0]["url"]
            video_versions = media.get("video_versions") or []
            if video_versions:
                pic_json["video_url"] = video_versions[0]["url"]
            if media.get("video_duration") is not None:
                pic_json["video_duration"] = media["video_duration"]
            if media.get("view_count") is not None:
                pic_json["video_view_count"] = media["view_count"]
            if media.get("play_count") is not None:
                pic_json["video_play_count"] = media["play_count"]
            caption = media.get("caption")
            caption_text = caption.get("text") if isinstance(caption, dict) else None
            pic_json["edge_media_to_caption"] = (
                {"edges": [{"node": {"text": caption_text}}]}
                if caption_text is not None
                else {"edges": []}
            )
            pic_json["edge_media_preview_like"] = {
                "count": media.get("like_count") or 0
            }
            pic_json["edge_media_to_parent_comment"] = {
                "count": media.get("comment_count") or 0,
                "edges": [],
            }
            if media.get("has_liked") is not None:
                pic_json["viewer_has_liked"] = media["has_liked"]
            if media.get("accessibility_caption") is not None:
                pic_json["accessibility_caption"] = media["accessibility_caption"]
            if media.get("location"):
                pic_json["location"] = media["location"]
            carousel = media.get("carousel_media") or []
            if carousel:
                carousel_nodes = []
                for item in carousel:
                    item_type = item.get("media_type", 1)
                    node: dict[str, object] = {
                        "shortcode": item.get("code", ""),
                        "__typename": media_types.get(item_type, "GraphImage"),
                        "is_video": item_type == 2,
                    }
                    item_candidates = (item.get("image_versions2") or {}).get(
                        "candidates"
                    ) or []
                    node["display_url"] = (
                        item_candidates[0]["url"] if item_candidates else ""
                    )
                    item_videos = item.get("video_versions") or []
                    node["video_url"] = item_videos[0]["url"] if item_videos else None
                    if item.get("accessibility_caption") is not None:
                        node["accessibility_caption"] = item["accessibility_caption"]
                    carousel_nodes.append({"node": node})
                pic_json["edge_sidecar_to_children"] = {"edges": carousel_nodes}
            tagged = (media.get("usertags") or {}).get("in") or []
            if tagged:
                pic_json["edge_media_to_tagged_user"] = {
                    "edges": [
                        {"node": {"user": {"username": t["user"]["username"].lower()}}}
                        for t in tagged
                        if (t.get("user") or {}).get("username")
                    ]
                }
            self._full_metadata_dict = pic_json
            if self.shortcode != self._full_metadata_dict["shortcode"]:
                self._node.update(self._full_metadata_dict)
                raise PostChangedException

    Post._obtain_metadata = _obtain_metadata_patched  # type: ignore[method-assign]
    _INSTALOADER_POST_METADATA_PATCHED = True


def patch_instaloader() -> None:
    patch_instaloader_test_login()
    patch_instaloader_profile_from_username()
    patch_instaloader_profile_graphql()
    patch_instaloader_post_metadata()


def apply_user_agent(loader, user_agent: str | None) -> None:
    if not (user_agent or "").strip():
        return
    try:
        loader.context.user_agent = user_agent.strip()
    except Exception:
        try:
            loader.context._session.headers["User-Agent"] = user_agent.strip()
        except Exception:
            pass


def maybe_instagram_login(loader, username: str | None, password: str | None, verbose: bool) -> None:
    if not username or not password:
        return
    try:
        loader.login(username, password)
        if verbose:
            print(f"Instagram: logged in as {username}", file=sys.stderr)
    except Exception as exc:
        raise RuntimeError(
            f"Instagram login failed for {username}: {exc}. "
            "Complete any browser checkpoint, then retry or use --sessionfile from instaloader -l USER."
        ) from exc


def apply_instaloader_logged_in_headers(loader, *, verbose: bool) -> None:
    """
    Instaloader's own load_session() applies full browser-like headers plus X-CSRFToken
    from the csrftoken cookie. Cookie JSON import only merged cookies into the anonymous
    session, which can leave POST graphql (doc_id) failing with 403 while test_login (GET) works.
    """
    sess = loader.context._session
    sess.headers.update(loader.context._default_http_header())
    jar_dict = requests.utils.dict_from_cookiejar(sess.cookies)
    csrf = jar_dict.get("csrftoken")
    if csrf:
        sess.headers["X-CSRFToken"] = csrf
        if verbose:
            print("Instagram: synced X-CSRFToken from csrftoken cookie",
                  file=sys.stderr)
    elif verbose:
        print(
            "warning: no csrftoken in cookie jar; GraphQL POST may fail. "
            "Re-export cookies from the browser or use instaloader -l session.",
            file=sys.stderr,
        )


def load_cookies_from_browser_extension_json(
    loader,
    path: Path,
    *,
    verbose: bool,
    session_username_fallback: str | None = None,
) -> str:
    """
    Load Instagram cookies from a JSON list export (e.g. EditThisCookie, Cookie-Editor).
    Validates with Instaloader.test_login() (patched to prefer mobile current_user API).
    """
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(
            "cookies JSON must be a list of objects (typical browser extension export)."
        )
    session = loader.context._session
    count = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        domain = item.get("domain")
        if name is None or value is None or domain is None:
            continue
        if "instagram.com" not in str(domain).lower():
            continue
        cpath = item.get("path") or "/"
        exp = item.get("expirationDate")
        expires: int | None = None
        if isinstance(exp, (int, float)):
            expires = int(exp)
        kwargs: dict[str, object] = {
            "domain": str(domain),
            "path": str(cpath),
            "secure": bool(item.get("secure")),
        }
        if expires is not None:
            kwargs["expires"] = expires
        try:
            session.cookies.set(str(name), str(value), **kwargs)
        except TypeError:
            session.cookies.set(str(name), str(value))
        except Exception:
            session.cookies.set(str(name), str(value))
        count += 1

    if count == 0:
        raise ValueError(f"No instagram.com cookies found in {path}")

    if verbose:
        print(f"loaded {count} Instagram cookie(s) from {path}",
              file=sys.stderr)

    sync_instaloader_context_user_id_from_cookies(loader)
    apply_instaloader_logged_in_headers(loader, verbose=verbose)

    logged_in_as = loader.test_login()
    if logged_in_as:
        try:
            loader.context.username = logged_in_as
        except Exception:
            pass
        if verbose:
            print(
                f"Instagram session verified as @{logged_in_as}", file=sys.stderr)
        return logged_in_as

    jar = cookie_jar_dict_from_loader(loader)
    if not (jar.get("sessionid") or "").strip():
        raise RuntimeError(
            "Instagram cookie login failed: export is missing a non-empty sessionid cookie. "
            "Re-export cookies from your browser while logged in to instagram.com."
        )

    fallback = (session_username_fallback or "").strip()
    if fallback:
        if verbose:
            print(
                "warning: Instagram API could not verify cookie session (often rate-limit or "
                f"IP mismatch); continuing with --session-username / INSTALOADER_SESSION_USERNAME "
                f"= @{fallback}. Re-export cookies or use --proxy-downloads-only if listing fails.",
                file=sys.stderr,
            )
        try:
            loader.context.username = fallback
        except Exception:
            pass
        return fallback

    raise RuntimeError(
        "Instagram cookie login failed: sessionid is present but Instagram rejected the session. "
        "Re-export cookies while logged in, set --user-agent to match your browser, and when using "
        "a proxy with cookies pass --proxy-downloads-only (crawl on direct IP). "
        "If the API is rate-limiting, set --session-username (or INSTALOADER_SESSION_USERNAME) "
        "to your logged-in account and retry."
    )


def build_transcript_text(item: ReelVideo, segments: list[dict[str, object]]) -> str:
    lines = [str(seg["text"]).strip()
             for seg in segments if str(seg["text"]).strip()]
    body = "\n".join(lines).strip()
    header = [
        f"Title: {item.title}",
        f"Media ID: {item.mediaid}",
        f"Shortcode: {item.shortcode}",
        f"URL: {item.post_url}",
        f"Date UTC: {item.date_utc}",
        "",
    ]
    if body:
        return "\n".join(header) + body + "\n"
    return "\n".join(header) + "\n"


def _env_redis_mode_default() -> str:
    raw = (os.environ.get("REDIS_MODE") or "local").strip().lower()
    return raw if raw in ("local", "producer", "worker", "requeue-skipped") else "local"


def _env_disable_diarization_default() -> bool:
    v = (os.environ.get("DISABLE_DIARIZATION") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _env_max_consecutive_errors_default() -> int:
    raw = (os.environ.get("MAX_CONSECUTIVE_ERRORS") or "").strip()
    if not raw:
        return 12
    try:
        return int(raw)
    except ValueError:
        return 12


def _env_transcript_no_proxy_default() -> bool:
    v = (os.environ.get("TRANSCRIPT_NO_PROXY") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _env_bypass_proxy_downloads_default() -> bool:
    """Video file downloads use the host's direct IP unless opted in via --with-proxy-downloads."""
    v = (os.environ.get("DIRECT_INSTAGRAM_DOWNLOADS") or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Instagram reels and create Whisper transcripts.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help=(
            "Instagram username or profile/reels URL (required for local/producer crawl). "
            "Also: --target or env INSTAGRAM_TARGET. Not used for --redis-mode worker."
        ),
    )
    parser.add_argument(
        "--target",
        dest="target_opt",
        default=None,
        help="Target username or URL (overrides positional; env INSTAGRAM_TARGET if unset).",
    )
    parser.add_argument("--mode", choices=("reels", "posts"), default="reels")

    parser.add_argument("--out", "-o", default="output",
                        help="Root output directory.")
    parser.add_argument("--download-dir", default="videos",
                        help="Video folder (absolute or relative to --out).")
    parser.add_argument(
        "--transcript-dir",
        default="transcripts",
        help="Transcript folder (absolute or relative to --out).",
    )
    parser.add_argument(
        "--metadata-dir",
        default="metadata",
        help="Metadata folder (absolute or relative to --out).",
    )
    parser.add_argument("--checkpoint-file", default="checkpoint.json")
    parser.add_argument("--skip-log", default="skipped.jsonl")

    parser.add_argument("--delay", type=float, default=3.0,
                        help="Seconds between successful video processes.")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-processed media IDs.")
    parser.add_argument("-n", "--limit", "--first",
                        dest="limit", type=int, default=None)
    parser.add_argument("--max-items-per-run", type=int, default=None)
    parser.add_argument("--start-after-mediaid", default=None)
    parser.add_argument("--sessionfile", default=None,
                        help="Instaloader session filename for authenticated access.")
    parser.add_argument(
        "--session-username",
        default=None,
        help=(
            "Instagram username that OWNS the session file (the account you used with instaloader -l). "
            "Not the profile you scrape. Env: INSTALOADER_SESSION_USERNAME."
        ),
    )
    parser.add_argument(
        "--instagram-user",
        default=None,
        help="Instagram username for login when not using a session file (password via INSTAGRAM_PASSWORD).",
    )
    parser.add_argument(
        "--instagram-password",
        default=None,
        help="Instagram password (prefer env INSTAGRAM_PASSWORD to avoid shell history).",
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Override HTTP User-Agent for Instaloader (optional; may help with some proxies).",
    )
    parser.add_argument(
        "--cookies-json",
        default=None,
        metavar="PATH",
        help=(
            "Path to browser cookie export JSON (EditThisCookie / similar). "
            "Conflicts with --sessionfile. Env: COOKIES_JSON."
        ),
    )
    parser.add_argument("--verbose", "-V", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="List queue and exit without download/transcribe.")

    parser.add_argument("--request-delay-min", type=float, default=1.5)
    parser.add_argument("--request-delay-max", type=float, default=4.5)
    parser.add_argument("--cooldown-every", type=int, default=50)
    parser.add_argument("--cooldown-seconds", type=float, default=90.0)
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=_env_max_consecutive_errors_default(),
        help=(
            "Stop after N consecutive job failures (default: 12, env: MAX_CONSECUTIVE_ERRORS). "
            "Use 0 to disable the limit (worker keeps running). "
            "Silent/no-speech videos are logged as NoSpeech and do not count as failures."
        ),
    )

    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-backoff-base", type=float, default=2.0)
    parser.add_argument("--retry-backoff-max", type=float, default=120.0)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--item-timeout-seconds",
        type=int,
        default=None,
        help=(
            "Optional wall-clock limit per item (download + transcribe + sidecars on disk). "
            "Unix: uses SIGALRM (best-effort; may not abort C/GPU immediately). "
            "Timeouts are logged as JobTimeout in skipped.jsonl and count as failed; "
            "Redis worker still XACKs. Omit for no limit."
        ),
    )

    parser.add_argument("--simplepush-key", default=None)
    parser.add_argument("--simplepush-title", default="Instagram transcripts")
    parser.add_argument("--simplepush-event", default="")
    parser.add_argument("--test-simplepush", action="store_true")

    parser.add_argument("--proxy-mode", choices=("rotating",
                        "single"), default="rotating")
    parser.add_argument("--proxy-url", default=None,
                        help="Explicit HTTP(S) proxy URL.")
    parser.add_argument("--proxy-file", default=None,
                        help="Proxy list file (URL or host:port:user:pass entries).")
    parser.add_argument("--webshare-user", default=None)
    parser.add_argument("--webshare-password", default=None)
    parser.add_argument("--webshare-host", default="p.webshare.io")
    parser.add_argument("--webshare-port", type=int, default=80)
    parser.add_argument(
        "--proxy-downloads-only",
        action="store_true",
        help=(
            "Do not use HTTP proxy for Instaloader (profile listing / GraphQL). "
            "Use proxy for binary video downloads (implies --with-proxy-downloads). "
            "Use with --cookies-json when cookies were exported from your normal browser IP."
        ),
    )

    parser.set_defaults(no_proxy=_env_transcript_no_proxy_default())
    parser.set_defaults(
        bypass_proxy_downloads=_env_bypass_proxy_downloads_default()
    )
    parser.add_argument(
        "--bypass-proxy",
        dest="no_proxy",
        action="store_true",
        help=(
            "Do not use Webshare, --proxy-url, --proxy-file, or TRANSCRIPT_PROXY anywhere "
            "(Instaloader and downloads). Env default: TRANSCRIPT_NO_PROXY=1."
        ),
    )
    parser.add_argument(
        "--with-proxy",
        dest="no_proxy",
        action="store_false",
        help="Use configured proxies for Instaloader (overrides TRANSCRIPT_NO_PROXY for this run).",
    )
    parser.add_argument(
        "--with-proxy-downloads",
        dest="bypass_proxy_downloads",
        action="store_false",
        help=(
            "Route video file downloads through Webshare/proxy. "
            "Default is direct download from this host's IP (saves proxy bandwidth on Cloud Run)."
        ),
    )
    parser.add_argument(
        "--bypass-proxy-downloads",
        dest="bypass_proxy_downloads",
        action="store_true",
        help=(
            "Download video files without proxy (default). "
            "Env default: DIRECT_INSTAGRAM_DOWNLOADS=1."
        ),
    )

    parser.add_argument("--model-size", default="large-v3")
    parser.add_argument("--device", default="auto",
                        choices=("auto", "cpu", "cuda"))
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--vad-filter", action=argparse.BooleanOptionalAction, default=True)

    parser.add_argument("--hf-token", default=None,
                        help="Hugging Face token for pyannote diarization.")
    parser.add_argument(
        "--disable-diarization",
        action=argparse.BooleanOptionalAction,
        default=_env_disable_diarization_default(),
        help=(
            "Skip pyannote diarization; transcript uses all Whisper segments. "
            "Env: DISABLE_DIARIZATION=1. Use --no-disable-diarization to override env."
        ),
    )
    parser.add_argument("--speaker-overlap-threshold", type=float, default=0.5)

    parser.add_argument(
        "--redis-mode",
        choices=("local", "producer", "worker", "requeue-skipped"),
        default=_env_redis_mode_default(),
        help=(
            "local: run crawl+transcribe. producer: enqueue to Redis. worker: consume stream. "
            "requeue-skipped: read skipped.jsonl + metadata JSON and XADD jobs again (no Instaloader)."
        ),
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL"),
        help="Redis URL (redis://host:6379/0 or rediss:// for TLS). Env: REDIS_URL.",
    )
    parser.add_argument(
        "--redis-stream",
        default=os.environ.get("REDIS_STREAM") or "insta:reel:jobs",
        help="Redis stream name for XADD/XREADGROUP (default: insta:reel:jobs).",
    )
    parser.add_argument(
        "--redis-group",
        default=os.environ.get("REDIS_GROUP") or "transcribers",
        help="Consumer group name (workers must share this). Default: transcribers.",
    )
    parser.add_argument(
        "--redis-consumer-name",
        default=os.environ.get("REDIS_CONSUMER_NAME"),
        help="Consumer name in the group (default: hostname:pid).",
    )
    parser.add_argument(
        "--redis-block-ms",
        type=int,
        default=int(os.environ.get("REDIS_BLOCK_MS") or 30000),
        help="XREADGROUP BLOCK milliseconds (default: 30000).",
    )
    parser.add_argument(
        "--redis-idle-exit-seconds",
        type=int,
        default=_env_optional_int("REDIS_IDLE_EXIT_SECONDS"),
        help=(
            "Worker exits after this many seconds with no new stream messages (optional). "
            "Sends Simplepush on exit if a key is configured (same as end-of-run summary). "
            "Env: REDIS_IDLE_EXIT_SECONDS."
        ),
    )
    parser.add_argument(
        "--redis-idle-notify-seconds",
        type=int,
        default=_env_optional_int("REDIS_IDLE_NOTIFY_SECONDS"),
        help=(
            "Worker: send Simplepush when no jobs arrive for this many seconds (requires "
            "--simplepush-key or SIMPLEPUSH_KEY). Repeats after each idle streak; worker keeps running. "
            "Use e.g. 1800 for 30 minutes. Independent of --redis-idle-exit-seconds. "
            "Env: REDIS_IDLE_NOTIFY_SECONDS."
        ),
    )
    parser.add_argument(
        "--redis-max-jobs",
        type=int,
        default=None,
        help="Worker processes at most N jobs then exits (optional; for testing).",
    )
    parser.add_argument(
        "--redis-producer-dedupe",
        action="store_true",
        help="Producer: use Redis SET stream:enqueued to avoid re-enqueueing the same mediaid.",
    )
    parser.add_argument(
        "--requeue-reason-contains",
        default=None,
        metavar="SUBSTRING",
        help=(
            "requeue-skipped only: enqueue lines whose skipped.jsonl 'reason' contains this substring "
            "(case-sensitive), e.g. JobTimeout."
        ),
    )
    args = parser.parse_args(argv)
    if args.proxy_downloads_only:
        args.bypass_proxy_downloads = False
    return args


def resolve_dir_arg(raw: str, out_dir: Path) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (out_dir / p).resolve()


def main(argv: list[str]) -> int:
    load_env_files()
    args = parse_args(argv)

    target = (
        (args.target_opt or "").strip()
        or (args.target or "").strip()
        or (os.environ.get("INSTAGRAM_TARGET") or "").strip()
    )
    cookies_json_arg = (
        (args.cookies_json or "").strip()
        or (os.environ.get("COOKIES_JSON") or "").strip()
    )
    if args.sessionfile and cookies_json_arg:
        print(
            "error: use either --sessionfile or --cookies-json, not both.",
            file=sys.stderr,
        )
        return 2
    if args.limit is not None and args.limit < 1:
        print("error: --limit must be >= 1", file=sys.stderr)
        return 2
    if args.max_items_per_run is not None and args.max_items_per_run < 1:
        print("error: --max-items-per-run must be >= 1", file=sys.stderr)
        return 2
    if args.request_delay_min < 0 or args.request_delay_max < 0:
        print("error: request delays must be non-negative", file=sys.stderr)
        return 2
    if args.request_delay_max < args.request_delay_min:
        print("error: --request-delay-max must be >= --request-delay-min",
              file=sys.stderr)
        return 2

    simplepush_key = resolve_simplepush_key(args)
    if args.test_simplepush:
        if not simplepush_key:
            print("error: no Simplepush key provided.", file=sys.stderr)
            return 2
        notify_simplepush(
            simplepush_key,
            args.simplepush_title,
            "Test notification from instagram_reels_transcripts.py",
            args.simplepush_event or None,
        )
        print("Simplepush test sent.")
        return 0

    out_dir = ensure_dir(Path(args.out).expanduser().resolve())
    video_dir = ensure_dir(resolve_dir_arg(args.download_dir, out_dir))
    transcript_dir = ensure_dir(resolve_dir_arg(args.transcript_dir, out_dir))
    metadata_dir = ensure_dir(resolve_dir_arg(args.metadata_dir, out_dir))

    checkpoint_path = Path(args.checkpoint_file).expanduser()
    if not checkpoint_path.is_absolute():
        checkpoint_path = out_dir / checkpoint_path
    checkpoint_path = checkpoint_path.resolve()
    skip_log_path = Path(args.skip_log).expanduser()
    if not skip_log_path.is_absolute():
        skip_log_path = out_dir / skip_log_path
    skip_log_path = skip_log_path.resolve()

    checkpoint = load_checkpoint(checkpoint_path)
    processed_mediaids = set(str(x)
                             for x in checkpoint.get("processed_mediaids", []))
    if args.resume:
        processed_mediaids |= load_existing_transcript_mediaids(transcript_dir)

    try:
        proxy_urls = resolve_proxy_urls(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    proxy_pool = ProxyPool(proxy_urls, mode=args.proxy_mode)
    if args.verbose and proxy_urls:
        masked = ", ".join(mask_proxy_url(x) for x in proxy_urls[:3])
        suffix = " ..." if len(proxy_urls) > 3 else ""
        print(
            f"proxy mode={args.proxy_mode} urls={len(proxy_urls)} sample={masked}{suffix}",
            file=sys.stderr,
        )

    cookies_auto_direct = (
        os.environ.get("COOKIES_AUTO_DIRECT_CRAWL", "1").strip().lower()
        not in ("0", "false", "no", "off")
    )
    if (
        cookies_json_arg
        and proxy_urls
        and not args.proxy_downloads_only
        and cookies_auto_direct
    ):
        args.proxy_downloads_only = True
        print(
            "info: --cookies-json with proxy configured; Instaloader crawl uses direct IP "
            "(auto --proxy-downloads-only). Set COOKIES_AUTO_DIRECT_CRAWL=0 to disable.",
            file=sys.stderr,
        )

    if args.redis_mode == "requeue-skipped":
        return run_redis_requeue_skipped(
            args,
            metadata_dir=metadata_dir,
            transcript_dir=transcript_dir,
            skip_log_path=skip_log_path,
            processed_mediaids=processed_mediaids,
        )

    if args.redis_mode == "worker":
        if args.dry_run:
            print(
                "error: --redis-mode worker cannot be combined with --dry-run", file=sys.stderr)
            return 2
        url = (args.redis_url or os.environ.get("REDIS_URL") or "").strip()
        if not url:
            print(
                "error: --redis-mode worker requires --redis-url or REDIS_URL", file=sys.stderr)
            return 2
        try:
            whisper_model = load_whisper_model(args)
            print("Whisper model ready.", file=sys.stderr, flush=True)
        except Exception as exc:
            print(
                f"error: failed to load Whisper model '{args.model_size}': {exc}", file=sys.stderr)
            return 1
        diarization_pipeline = None
        if not args.disable_diarization:
            if args.verbose:
                print("Loading speaker diarization (pyannote, optional)…",
                      file=sys.stderr)
            diarization_pipeline = load_diarization_pipeline(args)
            if args.verbose:
                if diarization_pipeline is None:
                    print(
                        "Diarization unavailable; transcripts use all Whisper segments "
                        "(missing token, gated model, or dependency issue — see any warning above).",
                        file=sys.stderr,
                    )
                else:
                    print("Diarization pipeline ready.", file=sys.stderr)
        return run_redis_worker(
            args,
            simplepush_key=simplepush_key,
            out_dir=out_dir,
            video_dir=video_dir,
            transcript_dir=transcript_dir,
            metadata_dir=metadata_dir,
            checkpoint_path=checkpoint_path,
            skip_log_path=skip_log_path,
            processed_mediaids=processed_mediaids,
            proxy_pool=proxy_pool,
            whisper_model=whisper_model,
            diarization_pipeline=diarization_pipeline,
        )

    if not target:
        print(
            "error: Instagram target required for crawl/producer modes "
            "(positional username/URL, --target, or INSTAGRAM_TARGET).",
            file=sys.stderr,
        )
        return 2

    try:
        import instaloader
    except Exception as exc:
        print(f"error: instaloader import failed: {exc}", file=sys.stderr)
        return 2
    patch_instaloader()

    try:
        username = extract_username(target)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    loader = instaloader.Instaloader(
        dirname_pattern=str(video_dir),
        save_metadata=False,
        download_comments=False,
        download_geotags=False,
        compress_json=False,
        post_metadata_txt_pattern="",
    )
    apply_user_agent(loader, args.user_agent)

    ig_password = (
        (args.instagram_password or "").strip()
        or (os.environ.get("INSTAGRAM_PASSWORD") or "").strip()
    )
    ig_login_user = (args.instagram_user or "").strip() or (
        os.environ.get("INSTAGRAM_LOGIN_USER") or os.environ.get(
            "INSTAGRAM_USER") or ""
    ).strip()

    crawl_proxy = proxy_pool.next_url() if proxy_urls else None
    use_proxy_for_instaloader = bool(
        crawl_proxy) and not args.proxy_downloads_only
    if cookies_json_arg and crawl_proxy and not args.proxy_downloads_only:
        print(
            "warning: Webshare (or other) proxy is enabled for Instaloader while using --cookies-json. "
            "GraphQL often returns 403 when the proxy IP does not match the IP where cookies were created. "
            "If that happens, pass --proxy-downloads-only (crawl direct, downloads still use proxy).",
            file=sys.stderr,
        )
    if use_proxy_for_instaloader and crawl_proxy:
        try:
            loader.context._session.proxies = ProxyPool.as_requests_proxies(
                crawl_proxy)
            if args.verbose:
                download_mode = (
                    "direct IP (default)"
                    if args.bypass_proxy_downloads
                    else "proxy"
                )
                print(
                    f"instaloader crawl proxy={mask_proxy_url(crawl_proxy)}; "
                    f"video downloads={download_mode}",
                    file=sys.stderr,
                )
        except Exception:
            pass
    elif args.verbose and proxy_urls:
        if args.bypass_proxy_downloads:
            print(
                "instaloader: no proxy (direct); video downloads use direct IP (default)",
                file=sys.stderr,
            )
        else:
            print(
                "instaloader: no proxy (direct); video downloads use proxy",
                file=sys.stderr,
            )
    elif args.verbose and args.bypass_proxy_downloads:
        print(
            "video downloads: direct IP (no proxy configured)",
            file=sys.stderr,
        )

    if args.sessionfile:
        sessionfile = args.sessionfile
        session_owner = (
            (args.session_username or "").strip()
            or (os.environ.get("INSTALOADER_SESSION_USERNAME") or "").strip()
        )
        if not session_owner:
            session_owner = username
            if args.verbose:
                print(
                    "warning: --session-username not set; using target profile as session owner. "
                    "If loading fails, set INSTALOADER_SESSION_USERNAME to the Instagram account "
                    "you used when creating the session (instaloader -l).",
                    file=sys.stderr,
                )
        try:
            loader.load_session_from_file(
                username=session_owner, filename=sessionfile)
            if args.verbose:
                print(
                    f"loaded instaloader sessionfile={sessionfile} session_owner={session_owner}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                f"warning: could not load sessionfile: {exc}", file=sys.stderr)
    elif cookies_json_arg:
        cookies_path = Path(cookies_json_arg).expanduser()
        if not cookies_path.is_file():
            print(
                f"error: --cookies-json not found: {cookies_path}", file=sys.stderr)
            return 2
        try:
            session_owner = (
                (args.session_username or "").strip()
                or (os.environ.get("INSTALOADER_SESSION_USERNAME") or "").strip()
            )
            load_cookies_from_browser_extension_json(
                loader,
                cookies_path.resolve(),
                verbose=args.verbose,
                session_username_fallback=session_owner or None,
            )
        except Exception as exc:
            print(
                f"error: could not load cookies JSON: {exc}", file=sys.stderr)
            print(
                instagram_enumeration_hints(
                    exc, username=username, used_proxy=bool(proxy_urls)),
                file=sys.stderr,
            )
            return 1
    elif ig_login_user and ig_password:
        try:
            maybe_instagram_login(loader, ig_login_user,
                                  ig_password, args.verbose)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(
                instagram_enumeration_hints(
                    exc, username=username, used_proxy=bool(proxy_urls)),
                file=sys.stderr,
            )
            return 1

    reel_kw = dict(
        loader=loader,
        username=username,
        mode=args.mode,
        start_after_mediaid=args.start_after_mediaid,
        limit=args.limit,
        max_items_per_run=args.max_items_per_run,
        request_delay_min=args.request_delay_min,
        request_delay_max=args.request_delay_max,
        verbose=args.verbose,
    )

    if args.redis_mode == "producer" and not args.dry_run:
        try:
            return run_redis_producer(
                args,
                iter_reel_candidates(**reel_kw),
                transcript_dir=transcript_dir,
                processed_mediaids=processed_mediaids,
            )
        except Exception as exc:
            print(
                f"error: failed to enumerate reels for {username}: {exc}", file=sys.stderr)
            print(
                instagram_enumeration_hints(
                    exc, username=username, used_proxy=bool(proxy_urls)),
                file=sys.stderr,
            )
            if (
                cookies_json_arg
                and proxy_urls
                and not args.proxy_downloads_only
                and ("403" in str(exc).lower() or "forbidden" in str(exc).lower())
            ):
                print(
                    "hint: retry with --proxy-downloads-only so listing uses your direct IP (cookie-consistent) "
                    "and keep the proxy only for video file downloads.",
                    file=sys.stderr,
                )
            return 1
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130

    if args.dry_run and args.redis_mode == "producer":
        try:
            n = 0
            for item in iter_reel_candidates(**reel_kw):
                print(
                    f"{item.mediaid} {item.shortcode} {sanitize_title(item.title)}")
                n += 1
        except Exception as exc:
            print(
                f"error: failed to enumerate reels for {username}: {exc}", file=sys.stderr)
            print(
                instagram_enumeration_hints(
                    exc, username=username, used_proxy=bool(proxy_urls)),
                file=sys.stderr,
            )
            if (
                cookies_json_arg
                and proxy_urls
                and not args.proxy_downloads_only
                and ("403" in str(exc).lower() or "forbidden" in str(exc).lower())
            ):
                print(
                    "hint: retry with --proxy-downloads-only so listing uses your direct IP (cookie-consistent) "
                    "and keep the proxy only for video file downloads.",
                    file=sys.stderr,
                )
            return 1
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130
        if n == 0:
            print("No video posts found.")
        else:
            print(
                f"Listed {n} video(s) for processing (dry-run).", file=sys.stderr)
        return 0

    try:
        queue = fetch_reel_candidates(**reel_kw)
    except Exception as exc:
        print(
            f"error: failed to enumerate reels for {username}: {exc}", file=sys.stderr)
        print(
            instagram_enumeration_hints(
                exc, username=username, used_proxy=bool(proxy_urls)),
            file=sys.stderr,
        )
        if (
            cookies_json_arg
            and proxy_urls
            and not args.proxy_downloads_only
            and ("403" in str(exc).lower() or "forbidden" in str(exc).lower())
        ):
            print(
                "hint: retry with --proxy-downloads-only so listing uses your direct IP (cookie-consistent) "
                "and keep the proxy only for video file downloads.",
                file=sys.stderr,
            )
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130

    if not queue:
        print("No video posts found.")
        return 0
    print(f"Queued {len(queue)} video(s) for processing.")

    if args.dry_run:
        for item in queue:
            print(f"{item.mediaid} {item.shortcode} {sanitize_title(item.title)}")
        return 0

    try:
        whisper_model = load_whisper_model(args)
        print("Whisper model ready.", file=sys.stderr, flush=True)
    except Exception as exc:
        print(
            f"error: failed to load Whisper model '{args.model_size}': {exc}", file=sys.stderr)
        return 1

    diarization_pipeline = None
    if not args.disable_diarization:
        if args.verbose:
            print("Loading speaker diarization (pyannote, optional)…", file=sys.stderr)
        diarization_pipeline = load_diarization_pipeline(args)
        if args.verbose:
            if diarization_pipeline is None:
                print(
                    "Diarization unavailable; transcripts use all Whisper segments "
                    "(missing token, gated model, or dependency issue — see any warning above).",
                    file=sys.stderr,
                )
            else:
                print("Diarization pipeline ready.", file=sys.stderr)

    stats = {
        "downloaded_videos": 0,
        "transcribed": 0,
        "skipped_existing": 0,
        "failed": 0,
    }
    consecutive_errors = 0
    since_cooldown = 0
    q_len = len(queue)
    for index, item in enumerate(queue, start=1):
        label = f"[{index}/{q_len}]"
        res = process_queue_item(
            item,
            label=label,
            args=args,
            whisper_model=whisper_model,
            diarization_pipeline=diarization_pipeline,
            proxy_pool=proxy_pool,
            video_dir=video_dir,
            transcript_dir=transcript_dir,
            metadata_dir=metadata_dir,
            checkpoint_path=checkpoint_path,
            processed_mediaids=processed_mediaids,
            skip_log_path=skip_log_path,
        )
        if res.outcome == "transcribed":
            stats["transcribed"] += 1
            if res.downloaded:
                stats["downloaded_videos"] += 1
            consecutive_errors = 0
            since_cooldown += 1
            if args.cooldown_every > 0 and since_cooldown >= args.cooldown_every:
                print(
                    f"Cooldown reached after {since_cooldown} items. Sleeping {args.cooldown_seconds:.1f}s...",
                    file=sys.stderr,
                )
                time.sleep(max(0.0, args.cooldown_seconds))
                since_cooldown = 0
        elif res.outcome == "skipped":
            stats["skipped_existing"] += 1
            consecutive_errors = 0
        else:
            stats["failed"] += 1
            consecutive_errors += 1
            if (
                args.max_consecutive_errors > 0
                and consecutive_errors >= args.max_consecutive_errors
            ):
                stop_msg = (
                    f"Stopping early after {consecutive_errors} consecutive errors "
                    f"at mediaid {item.mediaid}."
                )
                print(stop_msg, file=sys.stderr)
                notify_simplepush(
                    simplepush_key,
                    args.simplepush_title,
                    stop_msg,
                    args.simplepush_event or None,
                )
                break
            backoff_sleep = exponential_backoff(
                consecutive_errors,
                args.retry_backoff_base,
                args.retry_backoff_max,
            )
            time.sleep(backoff_sleep)

    summary = (
        f"Done. queued={len(queue)} transcribed={stats['transcribed']} "
        f"downloaded_videos={stats['downloaded_videos']} skipped={stats['skipped_existing']} "
        f"failed={stats['failed']} checkpoint={checkpoint_path}"
    )
    print(summary)
    notify_simplepush(
        simplepush_key,
        f"{args.simplepush_title} - finished",
        summary,
        args.simplepush_event or None,
    )
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
