#!/usr/bin/env python3
"""Backfill reel captions into existing metadata and transcript headers."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import instagram_reels_transcripts as irt


OUTCOMES = (
    "updated",
    "skipped_has_caption",
    "skipped_no_caption",
    "skipped_error",
    "missing_transcript",
)


def backfill_one_metadata_file(
    meta_path: Path,
    transcript_dir: Path,
    *,
    loader,
    proxy_url: str | None,
    dry_run: bool,
) -> str:
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return "skipped_error"
    if not isinstance(data, dict):
        return "skipped_error"

    mediaid = str(data.get("mediaid") or "").strip()
    shortcode = str(data.get("shortcode") or "").strip()
    if not mediaid or not shortcode:
        return "skipped_error"

    existing_caption = str(data.get("caption") or "").strip()
    desired_title = irt.caption_as_title(existing_caption)
    transcript_path = irt.find_transcript_path_for_mediaid(
        transcript_dir,
        mediaid,
    )

    if existing_caption and desired_title:
        metadata_matches = str(data.get("title") or "") == desired_title
        transcript_matches = False
        if transcript_path is not None and transcript_path.is_file():
            try:
                first_line = (
                    transcript_path.read_text(encoding="utf-8").splitlines()[:1]
                )
            except Exception:
                return "skipped_error"
            transcript_matches = bool(
                first_line and first_line[0] == f"Title: {desired_title}"
            )
        if metadata_matches and transcript_matches:
            return "skipped_has_caption"

    try:
        text = irt.fetch_reel_caption_with_proxy_fallback(
            loader,
            shortcode,
            proxy_url,
        )
    except Exception:
        return "skipped_error"
    if not text:
        return "skipped_no_caption"

    title = irt.caption_as_title(text)
    if dry_run:
        return "updated"

    data["caption"] = text
    data["title"] = title
    try:
        meta_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        return "skipped_error"

    if transcript_path is None:
        return "missing_transcript"
    try:
        if not irt.patch_transcript_title(transcript_path, title):
            return "skipped_error"
    except Exception:
        return "skipped_error"
    return "updated"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill Instagram reel captions into metadata JSON and "
            "matching transcript Title headers."
        ),
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        help="Profile output directory containing metadata/ and transcripts/.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--request-delay-min", type=float, default=1.0)
    parser.add_argument("--request-delay-max", type=float, default=2.5)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--cookies-json", default=None)
    parser.add_argument("--sessionfile", default=None)
    parser.add_argument("--session-username", default=None)
    parser.add_argument("--instagram-user", default=None)
    parser.add_argument("--instagram-password", default=None)
    parser.add_argument(
        "--anonymous",
        action="store_true",
        help=(
            "Skip cookies/session and fetch public reel captions anonymously. "
            "Useful when browser cookies hit checkpoint_required."
        ),
    )
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--webshare-user", default=None)
    parser.add_argument("--webshare-password", default=None)
    parser.add_argument("--webshare-host", default="p.webshare.io")
    parser.add_argument("--webshare-port", type=int, default=80)
    parser.add_argument("--proxy-url", default=None)
    parser.add_argument("--proxy-file", default=None)
    parser.add_argument(
        "--proxy-mode",
        choices=("rotating", "single"),
        default="rotating",
    )
    parser.set_defaults(no_proxy=False)
    parser.add_argument(
        "--bypass-proxy",
        dest="no_proxy",
        action="store_true",
        help="Use the direct network only.",
    )
    parser.add_argument(
        "--with-proxy",
        dest="no_proxy",
        action="store_false",
        help="Use configured Webshare credentials or another configured proxy.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    irt.load_env_files()
    args = parse_args(argv)
    if args.limit is not None and args.limit < 1:
        print("error: --limit must be >= 1", file=sys.stderr)
        return 2
    if args.request_delay_min < 0 or args.request_delay_max < 0:
        print("error: request delays must be non-negative", file=sys.stderr)
        return 2
    if args.request_delay_max < args.request_delay_min:
        print(
            "error: --request-delay-max must be >= --request-delay-min",
            file=sys.stderr,
        )
        return 2

    data_dir = args.data_dir.expanduser().resolve()
    metadata_dir = data_dir / "metadata"
    transcript_dir = data_dir / "transcripts"
    if not metadata_dir.is_dir():
        print(f"error: missing {metadata_dir}", file=sys.stderr)
        return 2

    try:
        proxy_urls = irt.resolve_proxy_urls(args)
    except Exception as exc:
        print(f"error: setup failed: {exc}", file=sys.stderr)
        return 2

    if args.anonymous:
        # Ignore COOKIES_JSON / session from .env — checkpointed cookies break public GraphQL.
        args.cookies_json = ""
        args.sessionfile = None
        os.environ.pop("COOKIES_JSON", None)
        try:
            loader = irt.build_authenticated_loader(
                args,
                dirname_pattern=str(data_dir / "videos"),
                require_auth=False,
            )
        except Exception as exc:
            print(f"error: setup failed: {exc}", file=sys.stderr)
            return 2
        if args.verbose:
            print(
                "caption fetch: anonymous Instaloader (no cookies/session)",
                file=sys.stderr,
                flush=True,
            )
    else:
        try:
            loader = irt.build_authenticated_loader(
                args,
                dirname_pattern=str(data_dir / "videos"),
                require_auth=True,
            )
        except Exception as exc:
            print(f"error: setup failed: {exc}", file=sys.stderr)
            return 2

    proxy_pool = irt.ProxyPool(proxy_urls, mode=args.proxy_mode)
    if args.verbose and not args.anonymous:
        if proxy_urls:
            print(
                f"caption fetch proxy={irt.mask_proxy_url(proxy_urls[0])} "
                "(fallback to direct on failure)",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "caption fetch: direct network",
                file=sys.stderr,
                flush=True,
            )

    paths = sorted(metadata_dir.glob("*.json"))
    if args.limit is not None:
        paths = paths[: args.limit]

    counts = {outcome: 0 for outcome in OUTCOMES}
    for meta_path in paths:
        irt.sleep_jitter(args.request_delay_min, args.request_delay_max)
        outcome = backfill_one_metadata_file(
            meta_path,
            transcript_dir,
            loader=loader,
            proxy_url=proxy_pool.next_url(),
            dry_run=args.dry_run,
        )
        counts[outcome] = counts.get(outcome, 0) + 1
        if args.verbose:
            print(f"{meta_path.name} {outcome}", file=sys.stderr, flush=True)

    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
