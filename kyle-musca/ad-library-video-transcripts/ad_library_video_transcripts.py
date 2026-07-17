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

from ad_library_client import iter_ad_videos_playwright
from ad_library_parser import AdVideo, ad_video_from_job_dict, ad_video_job_dict

INVALID_FS_CHARS_RE = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
OUTPUT_ID_RE = re.compile(r"__(\d+)\.txt$")


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


def download_video(
    item: AdVideo,
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


def write_sidecar_metadata(path: Path, item: AdVideo, video_path: Path) -> None:
    payload = {
        "mediaid": item.mediaid,
        "shortcode": item.shortcode,
        "title": item.title,
        "post_url": item.post_url,
        "video_url": item.video_url,
        "date_utc": item.date_utc,
        "source": "meta_ad_library",
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


def ad_video_from_metadata_file(path: Path) -> AdVideo | None:
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
        return ad_video_from_job_dict(data)
    except Exception:
        return None


def process_queue_item(
    item: AdVideo,
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
    queue: Iterable[AdVideo],
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

    stream = (args.redis_stream or "adlib:video:jobs").strip()
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
        payload = json.dumps(ad_video_job_dict(item), ensure_ascii=False)
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
        f"Jobs were pushed incrementally as Playwright enumerated Ad Library videos.",
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

    queue: list[AdVideo] = []
    missing_meta: list[str] = []
    for mid in ordered_mids:
        item = ad_video_from_metadata_file(metadata_dir / f"{mid}.json")
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

    stream = (args.redis_stream or "adlib:video:jobs").strip()
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
        payload = json.dumps(ad_video_job_dict(item), ensure_ascii=False)
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
    stream = (args.redis_stream or "adlib:video:jobs").strip()
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
                    item = ad_video_from_job_dict(json.loads(raw))
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


def build_transcript_text(item: AdVideo, segments: list[dict[str, object]]) -> str:
    lines = [str(seg["text"]).strip()
             for seg in segments if str(seg["text"]).strip()]
    body = "\n".join(lines).strip()
    header = [
        f"Title: {item.title}",
        f"Library ID: {item.mediaid}",
        f"URL: {item.post_url}",
        f"Date UTC: {item.date_utc}",
        "",
    ]
    if body:
        return "\n".join(header) + body + "\n"
    return "\n".join(header) + "\n"


def _env_page_id_default() -> str:
    return (os.environ.get("AD_LIBRARY_PAGE_ID") or "").strip() or "116482854782233"


def _effective_limit(args: argparse.Namespace) -> int | None:
    if args.limit is not None and args.max_items_per_run is not None:
        return min(args.limit, args.max_items_per_run)
    return args.limit if args.limit is not None else args.max_items_per_run


def iter_ad_video_candidates(
    args: argparse.Namespace,
    *,
    page_id: str,
    ad_library_url_override: str | None,
) -> Iterable[AdVideo]:
    return iter_ad_videos_playwright(
        page_id=page_id,
        limit=_effective_limit(args),
        max_scroll_rounds=args.max_scroll_rounds,
        headless=not args.headed,
        request_delay_min=args.request_delay_min,
        request_delay_max=args.request_delay_max,
        verbose=args.verbose,
        country=args.country,
        active_status=args.active_status,
        media_type=args.media_type,
        start_url=ad_library_url_override,
    )


def fetch_ad_video_candidates(
    args: argparse.Namespace,
    *,
    page_id: str,
    ad_library_url_override: str | None,
) -> list[AdVideo]:
    return list(
        iter_ad_video_candidates(
            args,
            page_id=page_id,
            ad_library_url_override=ad_library_url_override,
        )
    )


def ad_library_enumeration_error(exc: BaseException) -> str:
    return (
        f"Ad Library enumeration failed: {exc}. "
        "Try --headed, increase --max-scroll-rounds, or pass --ad-library-url with a working library URL."
    )


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
        description="Scrape Meta Ad Library videos and create Whisper transcripts.",
    )
    parser.add_argument(
        "--page-id",
        default=_env_page_id_default(),
        help="Facebook Page ID for Ad Library (view_all_page_id). Env: AD_LIBRARY_PAGE_ID.",
    )
    parser.add_argument(
        "--ad-library-url",
        default=(os.environ.get("AD_LIBRARY_URL") or "").strip() or None,
        help="Optional full Ad Library URL override (env: AD_LIBRARY_URL).",
    )
    parser.add_argument("--media-type", default="video",
                        help="Ad Library media_type filter (default: video).")
    parser.add_argument("--country", default="ALL",
                        help="Ad Library country filter (default: ALL).")
    parser.add_argument("--active-status", default="active",
                        help="Ad Library active_status filter (default: active).")
    parser.add_argument(
        "--max-scroll-rounds",
        type=int,
        default=80,
        help="Maximum Playwright scroll rounds when enumerating ads (default: 80).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Playwright in headed (non-headless) mode.",
    )

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
    parser.add_argument("--verbose", "-V", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="List queue and exit without download/transcribe.")

    parser.add_argument("--request-delay-min", type=float, default=1.0)
    parser.add_argument("--request-delay-max", type=float, default=3.0)
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
    parser.add_argument("--simplepush-title", default="Ad Library transcripts")
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

    parser.set_defaults(no_proxy=_env_transcript_no_proxy_default())
    parser.set_defaults(
        bypass_proxy_downloads=_env_bypass_proxy_downloads_default()
    )
    parser.add_argument(
        "--bypass-proxy",
        dest="no_proxy",
        action="store_true",
        help=(
            "Do not use Webshare, --proxy-url, --proxy-file, or TRANSCRIPT_PROXY for downloads. "
            "Env default: TRANSCRIPT_NO_PROXY=1."
        ),
    )
    parser.add_argument(
        "--with-proxy",
        dest="no_proxy",
        action="store_false",
        help="Use configured proxies for video downloads (overrides TRANSCRIPT_NO_PROXY for this run).",
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
            "local: single-machine one-flow (scrape → download → Whisper); no Redis. "
            "producer: enqueue jobs to Redis. worker: consume stream. "
            "requeue-skipped: read skipped.jsonl + metadata JSON and XADD jobs again."
        ),
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL"),
        help="Redis URL (redis://host:6379/0 or rediss:// for TLS). Env: REDIS_URL.",
    )
    parser.add_argument(
        "--redis-stream",
        default=os.environ.get("REDIS_STREAM") or "adlib:video:jobs",
        help="Redis stream name for XADD/XREADGROUP (default: adlib:video:jobs).",
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
    return args


def resolve_dir_arg(raw: str, out_dir: Path) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (out_dir / p).resolve()


def main(argv: list[str]) -> int:
    load_env_files()
    args = parse_args(argv)

    page_id = (args.page_id or "").strip() or _env_page_id_default()
    ad_library_url_override = (args.ad_library_url or "").strip() or None

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
            "Test notification from ad_library_video_transcripts.py",
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

    crawl_kw = dict(
        args=args,
        page_id=page_id,
        ad_library_url_override=ad_library_url_override,
    )

    if args.dry_run:
        if args.redis_mode == "worker":
            print(
                "error: --redis-mode worker cannot be combined with --dry-run",
                file=sys.stderr,
            )
            return 2
        try:
            n = 0
            for item in iter_ad_video_candidates(**crawl_kw):
                print(
                    f"{item.mediaid} {item.shortcode} {sanitize_title(item.title)}")
                n += 1
        except Exception as exc:
            print(
                f"error: failed to enumerate Ad Library videos for page_id={page_id}: {exc}",
                file=sys.stderr,
            )
            print(ad_library_enumeration_error(exc), file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130
        if n == 0:
            print("No video ads found.")
        else:
            print(
                f"Listed {n} video(s) for processing (dry-run).", file=sys.stderr)
        return 0

    if args.redis_mode == "producer":
        try:
            return run_redis_producer(
                args,
                iter_ad_video_candidates(**crawl_kw),
                transcript_dir=transcript_dir,
                processed_mediaids=processed_mediaids,
            )
        except Exception as exc:
            print(
                f"error: failed to enumerate Ad Library videos for page_id={page_id}: {exc}",
                file=sys.stderr,
            )
            print(ad_library_enumeration_error(exc), file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130

    try:
        queue = fetch_ad_video_candidates(**crawl_kw)
    except Exception as exc:
        print(
            f"error: failed to enumerate Ad Library videos for page_id={page_id}: {exc}",
            file=sys.stderr,
        )
        print(ad_library_enumeration_error(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130

    if not queue:
        print("No video ads found.")
        return 0
    print(f"Queued {len(queue)} video(s) for processing.")

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
