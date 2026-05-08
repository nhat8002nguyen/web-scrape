const INVALID_FS_CHARS = /[\x00-\x1f<>:"/\\|?*]/g;

/** Same rules as download_channel_transcripts.sanitize_title */
export function sanitizeTitle(title, maxLength = 120) {
  let s = title.replace(INVALID_FS_CHARS, "_");
  s = s.split(/\s+/).join(" ").trim();
  if (!s) s = "untitled";
  if (s.length > maxLength) {
    s = s.slice(0, maxLength).replace(/[_. ]+$/, "");
  }
  return s || "untitled";
}

export function buildOutputFilename(title, videoId) {
  return `${sanitizeTitle(title)}__${videoId}.txt`;
}

export function youtubeWatchUrl(videoId) {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

/** Line-per-segment body, trailing newline like Python write */
export function formatTranscriptBody(lines) {
  const body = lines.join("\n");
  if (!body) return "\n";
  return body.endsWith("\n") ? body : `${body}\n`;
}
