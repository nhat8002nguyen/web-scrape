#!/usr/bin/env node
/**
 * One-shot: move per-lesson *.txt files from OUT_DIR root into OUT_DIR/{category}/.
 * Uses lesson-queue.json for id → categoryName. Leaves rollups, json, jsonl at root.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import { lessonIdFromUrl } from "./discover.mjs";
import { categoryOutputDirName } from "./paths.mjs";

const outDir = path.resolve(process.cwd(), process.argv[2] || "transcripts");
const queuePath = path.join(outDir, "lesson-queue.json");

if (!fs.existsSync(queuePath)) {
  console.error(`error: missing ${queuePath}`);
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(queuePath, "utf-8"));
/** @type {Map<string, string>} */
const idToCategory = new Map();
for (const l of data.lessons || []) {
  if (l && typeof l.url === "string") {
    idToCategory.set(lessonIdFromUrl(l.url), l.categoryName);
  }
}

let moved = 0;
let skipped = 0;

for (const e of fs.readdirSync(outDir, { withFileTypes: true })) {
  if (!e.isFile() || !e.name.endsWith(".txt")) continue;
  const dot = e.name.lastIndexOf(".txt");
  const u = e.name.lastIndexOf("__", dot - 1);
  if (u < 0) continue;

  const id = e.name.slice(u + 2, dot);
  const categoryName = idToCategory.get(id);
  if (!categoryName) {
    console.warn(`skip (no lesson-queue match): ${e.name}`);
    skipped += 1;
    continue;
  }

  const src = path.join(outDir, e.name);
  const destDir = path.join(outDir, categoryOutputDirName(categoryName));
  fs.mkdirSync(destDir, { recursive: true });
  const dest = path.join(destDir, e.name);

  if (path.resolve(src) === path.resolve(dest)) {
    skipped += 1;
    continue;
  }

  if (fs.existsSync(dest)) {
    console.warn(`skip (dest exists): ${e.name} → ${dest}`);
    skipped += 1;
    continue;
  }

  fs.renameSync(src, dest);
  moved += 1;
}

console.log(`migrateLessonsToCategoryDirs: moved=${moved} skipped=${skipped} outDir=${outDir}`);
