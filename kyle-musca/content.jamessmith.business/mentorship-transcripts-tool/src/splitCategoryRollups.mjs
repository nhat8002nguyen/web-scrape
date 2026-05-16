/**
 * Reads transcripts/content-transcripts.txt and writes one rollup per category
 * at OUT_DIR root (e.g. mentorship-2-0-transcripts.txt). Deduplicates blocks
 * that were appended twice when the scraper was re-run (same category + title).
 *
 * Usage: node src/splitCategoryRollups.mjs [--out transcripts]
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @param {string} category */
function categoryRollupFilename(category) {
  const base = category
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${base}-transcripts.txt`;
}

/**
 * @param {string} text
 * @returns {{ category: string, title: string, body: string }[]}
 */
function parseBlocks(text) {
  const blocks = [];
  const re =
    /\n\n=== (.+?) \/ (.+?) ===\n\n([\s\S]*?)(?=\n\n=== |\s*$)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    blocks.push({
      category: m[1],
      title: m[2],
      body: m[3].replace(/\s+$/, ""),
    });
  }
  return blocks;
}

function parseArgs(argv) {
  let out = path.join(__dirname, "..", "transcripts");
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--out" && argv[i + 1]) {
      out = path.resolve(process.cwd(), argv[i + 1]);
      i += 1;
    }
  }
  return { out };
}

const { out: outDir } = parseArgs(process.argv.slice(2));
const masterPath = path.join(outDir, "content-transcripts.txt");

if (!fs.existsSync(masterPath)) {
  console.error(`missing ${masterPath}`);
  process.exit(1);
}

const text = fs.readFileSync(masterPath, "utf8");
const rawBlocks = parseBlocks(text);

const seen = new Set();
/** @type {Map<string, { category: string, title: string, body: string }[]>} */
const byCategory = new Map();

for (const b of rawBlocks) {
  const key = `${b.category}\0${b.title}`;
  if (seen.has(key)) continue;
  seen.add(key);
  const cat = b.category;
  if (!byCategory.has(cat)) byCategory.set(cat, []);
  byCategory.get(cat).push(b);
}

for (const [category, list] of byCategory) {
  let content = "";
  for (const b of list) {
    content += `\n\n=== ${category} / ${b.title} ===\n\n${b.body.trim()}\n`;
  }
  const name = categoryRollupFilename(category);
  const dest = path.join(outDir, name);
  fs.writeFileSync(dest, content, "utf8");
  console.log(`wrote ${name} (${list.length} lesson(s))`);
}
