#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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


def load_backfill_module():
    backfill_spec = importlib.util.spec_from_file_location(
        "backfill_reel_captions",
        ROOT / "backfill_reel_captions.py",
    )
    backfill_mod = importlib.util.module_from_spec(backfill_spec)
    assert backfill_spec.loader is not None
    sys.modules[backfill_spec.name] = backfill_mod
    backfill_spec.loader.exec_module(backfill_mod)
    return backfill_mod


class CaptionAsTitleTests(unittest.TestCase):
    def test_collapses_newlines_and_spaces(self) -> None:
        raw = "Line one\nLine two\n\n  Line three  "
        self.assertEqual(mod.caption_as_title(raw), "Line one Line two Line three")

    def test_empty(self) -> None:
        self.assertEqual(mod.caption_as_title(""), "")
        self.assertEqual(mod.caption_as_title("   \n  "), "")


class ClipsMediaTests(unittest.TestCase):
    def test_missing_caption_still_builds_reel(self) -> None:
        media = {
            "media_type": 2,
            "video_versions": [{"url": "http://video"}],
            "code": "AbC123xyz",
            "pk": "42",
            "taken_at": 1700000000,
        }
        item = mod.reel_video_from_clips_media(media)
        assert item is not None
        self.assertEqual(item.title, "reel_AbC123xyz")
        self.assertEqual(item.caption, "")


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


class AuthenticatedLoaderTests(unittest.TestCase):
    def test_builds_loader_and_reuses_cookie_auth_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cookies_path = Path(tmp) / "cookies.json"
            cookies_path.write_text("[]", encoding="utf-8")
            args = SimpleNamespace(
                cookies_json=str(cookies_path),
                sessionfile=None,
                session_username="session-owner",
                instagram_user=None,
                instagram_password=None,
                user_agent="Browser UA",
                verbose=True,
            )
            loader = MagicMock()
            fake_instaloader = SimpleNamespace(Instaloader=MagicMock(return_value=loader))

            with (
                patch.dict(os.environ, {}, clear=True),
                patch.dict(sys.modules, {"instaloader": fake_instaloader}),
                patch.object(mod, "patch_instaloader") as patch_instaloader,
                patch.object(mod, "apply_user_agent") as apply_user_agent,
                patch.object(
                    mod,
                    "load_cookies_from_browser_extension_json",
                ) as load_cookies,
            ):
                result = mod.build_authenticated_loader(
                    args,
                    dirname_pattern="/tmp/videos",
                    session_username_fallback="target-user",
                )

            self.assertIs(result, loader)
            fake_instaloader.Instaloader.assert_called_once_with(
                dirname_pattern="/tmp/videos",
                save_metadata=False,
                download_comments=False,
                download_geotags=False,
                compress_json=False,
                post_metadata_txt_pattern="",
            )
            patch_instaloader.assert_called_once_with()
            apply_user_agent.assert_called_once_with(loader, "Browser UA")
            load_cookies.assert_called_once_with(
                loader,
                cookies_path.resolve(),
                verbose=True,
                session_username_fallback="session-owner",
            )


class BackfillOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backfill = load_backfill_module()

    def test_dry_run_reports_update_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "123.json"
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            transcript_path = transcript_dir / "reel_AbC__123.txt"
            metadata_path.write_text(
                json.dumps(
                    {
                        "mediaid": "123",
                        "shortcode": "AbC",
                        "title": "reel_AbC",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            transcript_path.write_text(
                "Title: reel_AbC\nMedia ID: 123\n\nbody\n",
                encoding="utf-8",
            )
            original_metadata = metadata_path.read_text(encoding="utf-8")
            original_transcript = transcript_path.read_text(encoding="utf-8")
            loader = MagicMock()

            with patch.object(
                self.backfill.irt,
                "fetch_reel_caption_with_proxy_fallback",
                return_value="Full\ncaption",
            ) as fetch:
                outcome = self.backfill.backfill_one_metadata_file(
                    metadata_path,
                    transcript_dir,
                    loader=loader,
                    proxy_url="http://user:pass@proxy:80",
                    dry_run=True,
                )

            self.assertEqual(outcome, "updated")
            fetch.assert_called_once_with(loader, "AbC", "http://user:pass@proxy:80")
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), original_metadata)
            self.assertEqual(transcript_path.read_text(encoding="utf-8"), original_transcript)

    def test_missing_caption_bypasses_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "123.json"
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            metadata_path.write_text(
                '{"mediaid": "123", "shortcode": "AbC", "title": "reel_AbC"}\n',
                encoding="utf-8",
            )
            original_metadata = metadata_path.read_text(encoding="utf-8")

            with patch.object(
                self.backfill.irt,
                "fetch_reel_caption_with_proxy_fallback",
                return_value=None,
            ):
                outcome = self.backfill.backfill_one_metadata_file(
                    metadata_path,
                    transcript_dir,
                    loader=MagicMock(),
                    proxy_url=None,
                    dry_run=False,
                )

            self.assertEqual(outcome, "skipped_no_caption")
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), original_metadata)

    def test_updates_metadata_and_existing_transcript_without_renaming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "123.json"
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            transcript_path = transcript_dir / "reel_AbC__123.txt"
            metadata_path.write_text(
                '{"mediaid": "123", "shortcode": "AbC", "title": "reel_AbC"}\n',
                encoding="utf-8",
            )
            transcript_path.write_text(
                "Title: reel_AbC\nMedia ID: 123\n\nbody\n",
                encoding="utf-8",
            )

            with patch.object(
                self.backfill.irt,
                "fetch_reel_caption_with_proxy_fallback",
                return_value="Full\ncaption",
            ):
                outcome = self.backfill.backfill_one_metadata_file(
                    metadata_path,
                    transcript_dir,
                    loader=MagicMock(),
                    proxy_url=None,
                    dry_run=False,
                )

            self.assertEqual(outcome, "updated")
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(data["caption"], "Full\ncaption")
            self.assertEqual(data["title"], "Full caption")
            self.assertEqual(transcript_path.name, "reel_AbC__123.txt")
            self.assertTrue(
                transcript_path.read_text(encoding="utf-8").startswith(
                    "Title: Full caption\n"
                )
            )

    def test_existing_matching_caption_and_title_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "123.json"
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            metadata_path.write_text(
                json.dumps(
                    {
                        "mediaid": "123",
                        "shortcode": "AbC",
                        "caption": "Full\ncaption",
                        "title": "Full caption",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (transcript_dir / "reel_AbC__123.txt").write_text(
                "Title: Full caption\nMedia ID: 123\n\nbody\n",
                encoding="utf-8",
            )

            with patch.object(
                self.backfill.irt,
                "fetch_reel_caption_with_proxy_fallback",
            ) as fetch:
                outcome = self.backfill.backfill_one_metadata_file(
                    metadata_path,
                    transcript_dir,
                    loader=MagicMock(),
                    proxy_url=None,
                    dry_run=False,
                )

            self.assertEqual(outcome, "skipped_has_caption")
            fetch.assert_not_called()

    def test_missing_transcript_still_updates_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "123.json"
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            metadata_path.write_text(
                '{"mediaid": "123", "shortcode": "AbC", "title": "reel_AbC"}\n',
                encoding="utf-8",
            )

            with patch.object(
                self.backfill.irt,
                "fetch_reel_caption_with_proxy_fallback",
                return_value="Full caption",
            ):
                outcome = self.backfill.backfill_one_metadata_file(
                    metadata_path,
                    transcript_dir,
                    loader=MagicMock(),
                    proxy_url=None,
                    dry_run=False,
                )

            self.assertEqual(outcome, "missing_transcript")
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(data["caption"], "Full caption")
            self.assertEqual(data["title"], "Full caption")

    def test_existing_transcript_patch_failure_is_not_missing_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "123.json"
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            transcript_path = transcript_dir / "reel_AbC__123.txt"
            metadata_path.write_text(
                '{"mediaid": "123", "shortcode": "AbC", "title": "reel_AbC"}\n',
                encoding="utf-8",
            )
            transcript_path.write_text("No Title header\n\nbody\n", encoding="utf-8")

            with (
                patch.object(
                    self.backfill.irt,
                    "fetch_reel_caption_with_proxy_fallback",
                    return_value="Full caption",
                ),
                patch.object(
                    self.backfill.irt,
                    "patch_transcript_title",
                    return_value=False,
                ) as patch_title,
            ):
                outcome = self.backfill.backfill_one_metadata_file(
                    metadata_path,
                    transcript_dir,
                    loader=MagicMock(),
                    proxy_url=None,
                    dry_run=False,
                )

            self.assertEqual(outcome, "skipped_error")
            self.assertNotEqual(outcome, "missing_transcript")
            patch_title.assert_called_once()
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(data["caption"], "Full caption")
            self.assertEqual(data["title"], "Full caption")

    def test_requires_shortcode_and_mediaid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "123.json"
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            metadata_path.write_text('{"shortcode": "AbC"}\n', encoding="utf-8")

            outcome = self.backfill.backfill_one_metadata_file(
                metadata_path,
                transcript_dir,
                loader=MagicMock(),
                proxy_url=None,
                dry_run=False,
            )

            self.assertEqual(outcome, "skipped_error")


class BackfillLocalDepsTests(unittest.TestCase):
    def test_requirements_only_include_lightweight_runtime_packages(self) -> None:
        requirements = (
            (ROOT / "requirements-backfill.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        self.assertEqual(
            requirements,
            [
                "instaloader>=4.14",
                "requests>=2.31.0",
                "python-dotenv>=1.0.1",
            ],
        )

    def test_backfill_source_avoids_whisper_redis_pyannote(self) -> None:
        src = (ROOT / "backfill_reel_captions.py").read_text(encoding="utf-8")
        for banned in (
            "faster_whisper",
            "pyannote",
            "redis",
            "load_whisper_model",
            "WhisperModel",
        ):
            self.assertNotIn(banned, src)
