#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "instagram_reels_transcripts",
    ROOT / "instagram_reels_transcripts.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class CaptionAsTitleTests(unittest.TestCase):
    def test_collapses_newlines_and_spaces(self) -> None:
        raw = "Line one\nLine two\n\n  Line three  "
        self.assertEqual(mod.caption_as_title(raw), "Line one Line two Line three")

    def test_empty(self) -> None:
        self.assertEqual(mod.caption_as_title(""), "")
        self.assertEqual(mod.caption_as_title("   \n  "), "")


class EnrichReelCaptionTests(unittest.TestCase):
    def test_keeps_existing_caption(self) -> None:
        item = mod.ReelVideo(
            mediaid="1",
            shortcode="AbC",
            title="already",
            video_url="http://x",
            post_url="http://y",
            date_utc="",
            caption="already full",
        )
        out = mod.enrich_reel_caption(MagicMock(), item)
        self.assertIs(out, item)

    def test_bypass_when_fetch_returns_none(self) -> None:
        item = mod.ReelVideo(
            mediaid="1",
            shortcode="AbC",
            title="reel_AbC",
            video_url="http://x",
            post_url="http://y",
            date_utc="",
            caption="",
        )
        with patch.object(mod, "fetch_reel_caption_with_proxy_fallback", return_value=None):
            out = mod.enrich_reel_caption(MagicMock(), item, proxy_url="http://user:pass@proxy:80")
        self.assertEqual(out.title, "reel_AbC")
        self.assertEqual(out.caption, "")

    def test_sets_caption_and_title_when_found(self) -> None:
        item = mod.ReelVideo(
            mediaid="1",
            shortcode="AbC",
            title="reel_AbC",
            video_url="http://x",
            post_url="http://y",
            date_utc="",
            caption="",
        )
        with patch.object(
            mod, "fetch_reel_caption_with_proxy_fallback", return_value="Hello\nWorld"
        ):
            out = mod.enrich_reel_caption(MagicMock(), item, proxy_url=None)
        self.assertEqual(out.caption, "Hello\nWorld")
        self.assertEqual(out.title, "Hello World")


class ProxyFallbackTests(unittest.TestCase):
    def test_falls_back_to_direct_when_proxy_fetch_raises(self) -> None:
        loader = MagicMock()
        loader.context._session.proxies = {}

        def fetch_side_effect(ldr, _sc: str) -> str:
            if ldr.context._session.proxies:
                raise OSError("proxy failed")
            return "from direct"

        with patch.object(mod, "_fetch_reel_caption_or_raise", side_effect=fetch_side_effect):
            text = mod.fetch_reel_caption_with_proxy_fallback(
                loader, "AbC", "http://user:pass@p.webshare.io:80"
            )
        self.assertEqual(text, "from direct")
        self.assertEqual(loader.context._session.proxies, {})

    def test_empty_caption_on_proxy_does_not_retry_direct(self) -> None:
        loader = MagicMock()
        loader.context._session.proxies = {"http": "x"}
        with patch.object(
            mod, "_fetch_reel_caption_or_raise", side_effect=LookupError("empty caption")
        ) as mocked:
            text = mod.fetch_reel_caption_with_proxy_fallback(
                loader, "AbC", "http://user:pass@p.webshare.io:80"
            )
        self.assertIsNone(text)
        mocked.assert_called_once()

    def test_no_proxy_uses_direct_only(self) -> None:
        loader = MagicMock()
        loader.context._session.proxies = {}
        with patch.object(mod, "_fetch_reel_caption_or_raise", return_value="plain") as mocked:
            text = mod.fetch_reel_caption_with_proxy_fallback(loader, "AbC", None)
        self.assertEqual(text, "plain")
        mocked.assert_called_once()
