from __future__ import annotations

import json
from pathlib import Path

from ad_library_parser import (
    AdVideo,
    ad_video_from_job_dict,
    ad_video_job_dict,
    iter_videos_from_search_payload,
    parse_ad_node,
    parse_page_info,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ad_node_prefers_hd_url():
    node = json.loads((FIXTURES / "sample_ad_node.json").read_text(encoding="utf-8"))
    item = parse_ad_node(node)
    assert item is not None
    assert item.mediaid == "1295034249373689"
    assert item.shortcode == "1295034249373689"
    assert item.video_url.endswith("example-hd.mp4")
    assert item.post_url == "https://www.facebook.com/ads/library/?id=1295034249373689"
    assert "Scaling Roadmap" in item.title
    assert item.date_utc.startswith("2024-")


def test_parse_ad_node_skips_image_only():
    node = {
        "ad_archive_id": "1",
        "snapshot": {"title": "x", "videos": []},
    }
    assert parse_ad_node(node) is None


def test_iter_videos_from_search_payload_skips_non_video():
    payload = json.loads((FIXTURES / "sample_search_response.json").read_text(encoding="utf-8"))
    items = list(iter_videos_from_search_payload(payload))
    assert len(items) == 1
    assert items[0].mediaid == "1295034249373689"


def test_parse_page_info():
    payload = json.loads((FIXTURES / "sample_search_response.json").read_text(encoding="utf-8"))
    info = parse_page_info(payload)
    assert info["has_next_page"] is True
    assert info["end_cursor"] == "CURSOR_ABC"


def test_job_dict_roundtrip_matches_instagram_keys():
    item = AdVideo(
        mediaid="1295034249373689",
        shortcode="1295034249373689",
        title="Hello",
        video_url="https://video.xx.fbcdn.net/a.mp4",
        post_url="https://www.facebook.com/ads/library/?id=1295034249373689",
        date_utc="2024-06-22 00:00:00",
    )
    d = ad_video_job_dict(item)
    assert set(d.keys()) == {
        "mediaid",
        "shortcode",
        "title",
        "video_url",
        "post_url",
        "date_utc",
    }
    assert ad_video_from_job_dict(d).mediaid == item.mediaid
