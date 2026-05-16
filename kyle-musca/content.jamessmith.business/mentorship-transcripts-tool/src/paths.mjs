/** Same rules as member-only-youtube-transcripts-tool sanitizeTitle */
const INVALID_FS_CHARS = /[\x00-\x1f<>:"/\\|?*]/g;

export function sanitizeTitle(title, maxLength = 120) {
  let s = title.replace(INVALID_FS_CHARS, "_");
  s = s.split(/\s+/).join(" ").trim();
  if (!s) s = "untitled";
  if (s.length > maxLength) {
    s = s.slice(0, maxLength).replace(/[_. ]+$/, "");
  }
  return s || "untitled";
}

export function buildLessonOutputFilename(title, lessonId) {
  return `${sanitizeTitle(title)}__${lessonId}.txt`;
}

/** Safe directory name under OUT_DIR for a hub course / category. */
export function categoryOutputDirName(categoryName) {
  return sanitizeTitle((categoryName || "").trim() || "untitled", 120);
}

export const LEAD_MAGNET_CATEGORY = "Lead Magnet Mastery";

export function leadMagnetRollupFilename() {
  return "lead-magnet-mastery-transcripts.txt";
}

export function contentRollupFilename() {
  return "content-transcripts.txt";
}
