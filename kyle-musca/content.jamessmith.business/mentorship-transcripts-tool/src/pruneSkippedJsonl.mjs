#!/usr/bin/env node
/**
 * Rewrite transcripts/skipped.jsonl:
 * - Drop rows whose lessonId now has a per-lesson transcript file (*__{id}.txt).
 * - For lessonIds still missing a transcript, keep only the latest row (by `at`).
 *
 * Usage:
 *   node src/pruneSkippedJsonl.mjs [OUT_DIR]
 *   node src/pruneSkippedJsonl.mjs --dry-run [OUT_DIR]
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

/**
 * @param {string} outDir
 * @param {string} lessonId
 */
function transcriptExistsForLesson(outDir, lessonId) {
  const suffix = `__${lessonId}.txt`;
  try {
    const entries = fs.readdirSync(outDir, { withFileTypes: true });
    for (const e of entries) {
      if (e.isFile() && e.name.endsWith(".txt") && e.name.endsWith(suffix)) {
        return true;
      }
      if (e.isDirectory()) {
        let sub;
        try {
          sub = fs.readdirSync(path.join(outDir, e.name));
        } catch {
          continue;
        }
        if (sub.some((n) => n.endsWith(".txt") && n.endsWith(suffix))) {
          return true;
        }
      }
    }
    return false;
  } catch {
    return false;
  }
}

function parseArgs(argv) {
  let dryRun = false;
  const rest = [];
  for (const a of argv) {
    if (a === "--dry-run") dryRun = true;
    else rest.push(a);
  }
  const outDir = path.resolve(process.cwd(), rest[0] || "transcripts");
  return { dryRun, outDir };
}

function main() {
  const { dryRun, outDir } = parseArgs(process.argv.slice(2));
  const skipPath = path.join(outDir, "skipped.jsonl");

  if (!fs.existsSync(skipPath)) {
    console.error(`error: missing ${skipPath}`);
    process.exit(1);
  }

  const raw = fs.readFileSync(skipPath, "utf-8");
  const lines = raw.split(/\n/).filter((l) => l.trim() !== "");

  /** @type {Array<{ line: string; lessonId: string; at: string }>} */
  const parsed = [];
  let bad = 0;
  for (const line of lines) {
    try {
      const o = JSON.parse(line);
      const lessonId = typeof o.lessonId === "string" ? o.lessonId : "";
      const at = typeof o.at === "string" ? o.at : "";
      if (!lessonId) {
        bad += 1;
        continue;
      }
      parsed.push({ line, lessonId, at });
    } catch {
      bad += 1;
    }
  }

  const resolved = parsed.filter((r) =>
    transcriptExistsForLesson(outDir, r.lessonId),
  );
  const unresolved = parsed.filter(
    (r) => !transcriptExistsForLesson(outDir, r.lessonId),
  );

  /** @type {Map<string, { line: string; lessonId: string; at: string }>} */
  const latestById = new Map();
  for (const row of unresolved) {
    const prev = latestById.get(row.lessonId);
    if (!prev || row.at >= prev.at) {
      latestById.set(row.lessonId, row);
    }
  }

  const dedupedDropped = unresolved.length - latestById.size;

  const outLines = [...latestById.values()]
    .sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0))
    .map((r) => r.line);

  const body = outLines.length ? `${outLines.join("\n")}\n` : "";

  console.log(
    `pruneSkippedJsonl: outDir=${outDir}\n` +
      `  input lines=${lines.length} parse_ok=${parsed.length} parse_bad=${bad}\n` +
      `  dropped (transcript exists now)=${resolved.length}\n` +
      `  dropped (older duplicate failures)=${dedupedDropped}\n` +
      `  output lines=${outLines.length}`,
  );

  if (dryRun) {
    console.log("  (--dry-run: did not write)");
    return;
  }

  const tmp = `${skipPath}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, body, "utf-8");
  fs.renameSync(tmp, skipPath);
}

main();
