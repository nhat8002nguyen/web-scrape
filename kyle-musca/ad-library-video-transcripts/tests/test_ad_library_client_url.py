from ad_library_client import build_ad_library_url


def test_build_ad_library_url_contains_page_and_video_filter():
    url = build_ad_library_url(page_id="116482854782233")
    assert "view_all_page_id=116482854782233" in url
    assert "media_type=video" in url
    assert "country=ALL" in url
    assert "active_status=active" in url
    assert "search_type=page" in url
