import fs from "node:fs";
import path from "node:path";

export const LESSON_QUEUE_FILENAME = "lesson-queue.json";

const CACHE_VERSION = 1;

/**
 * @param {string} outDir absolute transcripts directory
 */
export function defaultLessonCachePath(outDir) {
  return path.join(outDir, LESSON_QUEUE_FILENAME);
}

/**
 * @param {string} cachePath absolute path
 * @param {string} startUrl hub URL this run uses (must match cache)
 * @returns {Array<{ categoryName: string; url: string }>|null}
 */
export function loadLessonCache(cachePath, startUrl) {
  if (!fs.existsSync(cachePath)) return null;
  try {
    const raw = fs.readFileSync(cachePath, "utf-8");
    const data = JSON.parse(raw);
    if (typeof data.startUrl === "string" && data.startUrl !== startUrl) {
      return null;
    }
    if (!Array.isArray(data.lessons)) return null;
    /** @type {Array<{ categoryName: string; url: string }>} */
    const lessons = [];
    for (const row of data.lessons) {
      if (
        row &&
        typeof row.url === "string" &&
        typeof row.categoryName === "string"
      ) {
        lessons.push({ categoryName: row.categoryName, url: row.url });
      }
    }
    return lessons.length > 0 ? lessons : null;
  } catch {
    return null;
  }
}

/**
 * @param {string} cachePath absolute path
 * @param {string} startUrl
 * @param {Array<{ categoryName: string; url: string }>} lessons
 */
export function saveLessonCache(cachePath, startUrl, lessons) {
  const payload = {
    version: CACHE_VERSION,
    startUrl,
    savedAt: new Date().toISOString(),
    lessonCount: lessons.length,
    lessons,
  };
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}
