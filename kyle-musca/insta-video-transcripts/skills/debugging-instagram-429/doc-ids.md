# Extract and probe Instagram GraphQL doc_ids

Use this only after the failing URL is `graphql/query` or listing is empty for a reason other than 429.

## Extract from Instagram web JS

Load `cookies.json` into `requests`, GET `https://www.instagram.com/`, download each `static.cdninstagram.com` script.

Relay operations look like:

```js
__d("PolarisProfilePageContentQuery_instagramRelayOperation",[],(function(t,n,r,o,a,i){a.exports="28036671149327607"}),null);
```

Regex that works:

```python
import re
pat = re.compile(r'__d\("([A-Za-z0-9_]+)_instagramRelayOperation".{0,180}?"(\d{15,20})"')
```

Names that matter for this repo:

| Relay name | Used for |
|---|---|
| `PolarisProfilePageContentQuery` | `INSTAGRAM_PROFILE_PAGE_DOC_ID` / `_obtain_metadata` |
| `PolarisPostRootQuery` | `INSTAGRAM_POST_ROOT_DOC_ID` / post metadata |
| `PolarisProfilePostsQuery` | timeline posts (not reels clips) |
| Reels tab / `xdt_api__v1__clips__user__connection_v2` | `INSTAGRAM_CLIPS_USER_DOC_ID` (often lazy-loaded; may be absent from homepage JS) |

Homepage bundles may not include the profile **reels tab** query. If missing, keep the last **probed-good** clips `doc_id` (`27234427476213202` as of the last working run).

## Probe before writing constants

Reuse project patches and cookies:

```python
from pathlib import Path
import instagram_reels_transcripts as m
import instaloader

m.patch_instaloader()
loader = instaloader.Instaloader(
    save_metadata=False, download_comments=False, download_geotags=False, compress_json=False
)
m.load_cookies_from_browser_extension_json(
    loader, Path("cookies.json"), verbose=True, session_username_fallback=None
)
profile = instaloader.Profile.from_username(loader.context, "TARGET_USERNAME")
print(profile.username, profile.userid)

raw = loader.context.doc_id_graphql_query(
    "CANDIDATE_DOC_ID",
    {"id": str(profile.userid), "enable_integrity_filters": True},
)
print(raw.get("status"), raw.get("data") is not None, raw.get("errors"))
```

Clips probe:

```python
raw = loader.context.doc_id_graphql_query(
    m.INSTAGRAM_CLIPS_USER_DOC_ID,
    {"data": {"page_size": 3, "include_feed_video": True, "target_user_id": str(profile.userid)}},
)
conn = (raw.get("data") or {}).get("xdt_api__v1__clips__user__connection_v2") or {}
edges = conn.get("edges") or []
print("edges", len(edges))
if edges:
    media = (edges[0].get("node") or {}).get("media") or {}
    print(sorted(media.keys()))
    print("code", media.get("code"), "video_versions", bool(media.get("video_versions")))
```

Video URL fallback when the list omits `video_versions`:

```python
info = loader.context.get_json(f"api/v1/media/{media['pk']}/info/", params={})
print((info.get("items") or [{}])[0].get("video_versions"))
```

Keep a candidate only if `data` is present **and** the expected field exists.
