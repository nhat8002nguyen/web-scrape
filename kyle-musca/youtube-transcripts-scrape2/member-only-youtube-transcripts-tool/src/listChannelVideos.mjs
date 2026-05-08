import { spawnSync } from "node:child_process";

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;

/** Port of normalize_channel_uploads_url from download_channel_transcripts.py */
export function normalizeChannelUploadsUrl(url) {
  const raw = url.trim();
  if (!raw) {
    throw new Error("Channel URL must not be empty.");
  }
  const href = raw.includes("://") ? raw : `https://${raw}`;
  let u;
  try {
    u = new URL(href);
  } catch {
    throw new Error("Invalid channel URL.");
  }
  if (u.hostname && !u.hostname.toLowerCase().includes("youtube.com")) {
    throw new Error("Expected a youtube.com URL.");
  }
  const scheme = u.protocol.replace(":", "") || "https";
  const host = u.hostname || "www.youtube.com";
  let path = u.pathname.replace(/\/$/, "");
  const pathLower = path.toLowerCase();
  const uploadsSuffix = "/videos";
  const knownTabs = [
    "/videos",
    "/shorts",
    "/streams",
    "/playlists",
    "/featured",
    "/releases",
    "/community",
    "/about",
  ];
  let newPath;
  if (knownTabs.some((tab) => pathLower.endsWith(tab))) {
    if (pathLower.endsWith("/videos")) {
      newPath = `${path}/`;
    } else if (pathLower.endsWith("/shorts")) {
      const base = path.replace(/\/[^/]+$/, "");
      newPath = `${base}${uploadsSuffix}/`;
    } else {
      const base = path.replace(/\/[^/]+$/, "");
      newPath = `${base}${uploadsSuffix}/`;
    }
  } else {
    newPath = `${path}${uploadsSuffix}/`;
  }
  return `${scheme}://${host}${newPath}`;
}

function walkPlaylistEntries(entries, out) {
  if (!entries) return;
  for (const item of entries) {
    if (!item) continue;
    const nested = item.entries;
    if (nested) {
      walkPlaylistEntries(nested, out);
    } else if (item.id) {
      out.push(item);
    }
  }
}

/**
 * Same mechanism as list_channel_videos: yt-dlp flat playlist JSON.
 * @returns {Array<[string, string]>} [videoId, title]
 */
export function listChannelVideos(channelUrl) {
  const normalized = normalizeChannelUploadsUrl(channelUrl);
  const result = spawnSync(
    "yt-dlp",
    [
      "--flat-playlist",
      "--skip-download",
      "--dump-single-json",
      "--no-warnings",
      "--quiet",
      normalized,
    ],
    {
      encoding: "utf-8",
      maxBuffer: 64 * 1024 * 1024,
    },
  );

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    const errText = (result.stderr || result.stdout || "").trim() || `exit ${result.status}`;
    throw new Error(`yt-dlp failed: ${errText}`);
  }

  let info;
  try {
    info = JSON.parse(result.stdout);
  } catch (e) {
    throw new Error(`yt-dlp returned invalid JSON: ${e.message}`);
  }

  const flat = [];
  if (info) {
    const rootEntries = info.entries;
    if (rootEntries?.length) {
      walkPlaylistEntries(rootEntries, flat);
    } else if (info.id && info._type === "url") {
      flat.push(info);
    }
  }

  const rows = [];
  const seen = new Set();
  for (const entry of flat) {
    const vid = entry.id;
    const title = entry.title || vid || "unknown";
    if (typeof vid === "string" && VIDEO_ID_RE.test(vid) && !seen.has(vid)) {
      seen.add(vid);
      rows.push([vid, title]);
    }
  }
  return rows;
}
