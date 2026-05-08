#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as XLSX from 'xlsx';

const PKG_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_DIR_A = path.join(PKG_ROOT, 'MatthewRyder');
const DEFAULT_DIR_B = path.join(PKG_ROOT, 'transcripts');
const DEFAULT_MERGED = path.join(PKG_ROOT, 'merged-transcripts');
const DEFAULT_XLSX = path.join(PKG_ROOT, 'transcripts-catalog.xlsx');
const MEMBER_TIER_LABEL = 'Level 2 member-only';

/** basename: Title__VIDEOID.txt */
function parseTranscriptBasename(basename) {
  const base = basename.replace(/\.txt$/i, '');
  const i = base.lastIndexOf('__');
  if (i <= 0) return null;
  const id = base.slice(i + 2);
  if (!/^[a-zA-Z0-9_-]{11}$/.test(id)) return null;
  const title = base.slice(0, i);
  return { id, title, baseName: base };
}

function walkTxtFiles(rootDir, bucket, sourceLabel) {
  if (!fs.existsSync(rootDir)) return;
  const st = fs.statSync(rootDir);
  if (!st.isDirectory()) return;
  for (const ent of fs.readdirSync(rootDir, { withFileTypes: true })) {
    const full = path.join(rootDir, ent.name);
    if (ent.isDirectory()) {
      walkTxtFiles(full, bucket, sourceLabel);
    } else if (ent.isFile() && ent.name.toLowerCase().endsWith('.txt')) {
      const stat = fs.statSync(full);
      bucket.push({ full, sourceLabel, size: stat.size });
    }
  }
}

function pickWinner(a, b) {
  if (a.size > b.size) return a;
  if (b.size > a.size) return b;
  if (a.sourceLabel === 'MatthewRyder' && b.sourceLabel !== 'MatthewRyder') return a;
  if (b.sourceLabel === 'MatthewRyder' && a.sourceLabel !== 'MatthewRyder') return b;
  return a;
}

function lineCount(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  if (!raw.length) return 0;
  const n = raw.split(/\r\n|\r|\n/).length;
  return n;
}

function parseArgs(argv) {
  const out = {
    dirA: DEFAULT_DIR_A,
    dirB: DEFAULT_DIR_B,
    merged: DEFAULT_MERGED,
    xlsx: DEFAULT_XLSX,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--matthew' && argv[i + 1]) {
      out.dirA = path.resolve(argv[++i]);
    } else if (a === '--transcripts' && argv[i + 1]) {
      out.dirB = path.resolve(argv[++i]);
    } else if (a === '--merged' && argv[i + 1]) {
      out.merged = path.resolve(argv[++i]);
    } else if (a === '--xlsx' && argv[i + 1]) {
      out.xlsx = path.resolve(argv[++i]);
    } else if (a === '--help' || a === '-h') {
      out.help = true;
    }
  }
  return out;
}

function printHelp() {
  console.log(`merge-transcripts-to-xlsx — dedupe by YouTube ID, copy winners, write catalog XLSX

Defaults (relative to tool package root):
  MatthewRyder → ${DEFAULT_DIR_A}
  transcripts  → ${DEFAULT_DIR_B}
  merged dir   → ${DEFAULT_MERGED}
  XLSX         → ${DEFAULT_XLSX}

Usage:
  node scripts/merge-transcripts-to-xlsx.mjs [options]

Options:
  --matthew DIR     First corpus (default: ./MatthewRyder)
  --transcripts DIR Second corpus (default: ./transcripts)
  --merged DIR      Output folder for deduped .txt copies
  --xlsx PATH       Output .xlsx path

Dedupe rule: larger file wins; on equal size, prefer MatthewRyder.

Each XLSX row includes member_tier = "${MEMBER_TIER_LABEL}".
`);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    printHelp();
    process.exit(0);
  }

  const collected = [];
  walkTxtFiles(opts.dirA, collected, 'MatthewRyder');
  walkTxtFiles(opts.dirB, collected, 'transcripts');

  const byId = new Map();
  for (const item of collected) {
    const base = path.basename(item.full);
    const parsed = parseTranscriptBasename(base);
    if (!parsed) continue;
    const row = { ...item, ...parsed, basename: base };
    const prev = byId.get(parsed.id);
    if (!prev) {
      byId.set(parsed.id, row);
    } else {
      byId.set(parsed.id, pickWinner(row, prev));
    }
  }

  fs.mkdirSync(opts.merged, { recursive: true });

  const rows = [];
  const sorted = [...byId.entries()].sort((x, y) => x[0].localeCompare(y[0]));

  for (const [, winner] of sorted) {
    const dest = path.join(opts.merged, winner.basename);
    fs.copyFileSync(winner.full, dest);
    rows.push({
      video_id: winner.id,
      title: winner.title,
      filename: winner.basename,
      source_prioritized: winner.sourceLabel,
      lines: lineCount(winner.full),
      merged_relative: path.relative(PKG_ROOT, dest),
      member_tier: MEMBER_TIER_LABEL,
    });
  }

  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'catalog');
  XLSX.writeFile(wb, opts.xlsx);

  const dupCount = collected.length - byId.size;
  console.log(
    JSON.stringify(
      {
        scanned_txt: collected.length,
        unique_ids: byId.size,
        duplicates_skipped: dupCount,
        merged_dir: opts.merged,
        xlsx: opts.xlsx,
      },
      null,
      2,
    ),
  );
}

main();
