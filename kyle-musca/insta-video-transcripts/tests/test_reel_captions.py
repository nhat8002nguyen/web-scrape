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


class TranscriptAndMetadataTests(unittest.TestCase):
    def test_build_transcript_text_uses_full_caption_title(self) -> None:
        item = mod.ReelVideo(
            mediaid="99",
            shortcode="Zz",
            title="Hello World",
            video_url="http://x",
            post_url="https://www.instagram.com/reel/Zz/",
            date_utc="2026-01-01 00:00:00",
            caption="Hello\nWorld",
        )
        text = mod.build_transcript_text(item, [{"text": "spoken words", "start": 0, "end": 1}])
        self.assertIn("Title: Hello World\n", text)
        self.assertIn("spoken words", text)

    def test_job_dict_round_trip_preserves_caption(self) -> None:
        item = mod.ReelVideo(
            mediaid="99",
            shortcode="Zz",
            title="Hello World",
            video_url="http://x",
            post_url="https://www.instagram.com/reel/Zz/",
            date_utc="",
            caption="Hello\nWorld",
        )
        d = mod.reel_video_job_dict(item)
        self.assertEqual(d["caption"], "Hello\nWorld")
        back = mod.reel_video_from_job_dict(d)
        self.assertEqual(back.caption, "Hello\nWorld")
        self.assertEqual(back.title, "Hello World")

    def test_job_dict_missing_caption_defaults_empty(self) -> None:
        back = mod.reel_video_from_job_dict(
            {
                "mediaid": "1",
                "shortcode": "Ab",
                "title": "reel_Ab",
                "video_url": "http://x",
                "post_url": "",
                "date_utc": "",
            }
        )
        self.assertEqual(back.caption, "")


class PatchTranscriptTitleTests(unittest.TestCase):
    def test_finds_by_mediaid_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            path = tdir / "reel_AbC__123.txt"
            path.write_text(
                "Title: reel_AbC\nMedia ID: 123\nShortcode: AbC\nURL: u\nDate UTC: \n\nbody\n",
                encoding="utf-8",
            )
            found = mod.find_transcript_path_for_mediaid(tdir, "123")
            self.assertEqual(found, path)

    def test_patch_title_keeps_body_and_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reel_AbC__123.txt"
            path.write_text(
                "Title: reel_AbC\nMedia ID: 123\nShortcode: AbC\nURL: u\nDate UTC: \n\nbody line\n",
                encoding="utf-8",
            )
            ok = mod.patch_transcript_title(path, "Full Caption Here")
            self.assertTrue(ok)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("Title: Full Caption Here\n"))
            self.assertIn("body line", text)
            self.assertEqual(path.name, "reel_AbC__123.txt")
