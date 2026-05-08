#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import simplepush from "simplepush-notifications";

import {
  createBrowserSession,
  defaultChromeExecutable,
} from "./extractTranscript.mjs";
import { listChannelVideos } from "./listChannelVideos.mjs";
import {
  buildOutputFilename,
  formatTranscriptBody,
  youtubeWatchUrl,
} from "./output.mjs";

const CONSECUTIVE_FAIL_STOP = 5;

/** @param {string|undefined} raw */
function parseLimitArg(raw) {
  if (raw == null || raw === "") return null;
  const v = parseInt(String(raw), 10);
  if (!Number.isFinite(v) || v < 1) {
    console.error(`error: -n / --limit / --first expects a positive integer (got: ${raw})`);
    process.exit(1);
  }
  return v;
}

/** @param {string|undefined} raw */
function parseStartAtArg(raw) {
  if (raw == null || raw === "") return null;
  const v = parseInt(String(raw), 10);
  if (!Number.isFinite(v) || v < 1) {
    console.error(`error: --start-at / --from expects a positive integer (got: ${raw})`);
    process.exit(1);
  }
  return v;
}

function parseArgs(argv) {
  const args = {
    positional: [],
    out: "transcripts",
    userDataDir: "",
    chromePath: "",
    simplepushKey: "",
    forceHeaded: false,
    headedFallback: true,
    delay: 5,
    limit: null,
    resume: false,
    profileDirectory: "",
    navigationTimeout: 120_000,
    stepTimeout: 90_000,
    scrapeTimeoutMs: 120_000,
    verbose: false,
    connect: false,
    browserUrl: "http://127.0.0.1:9222",
    resumeDirs: [],
    startAt: null,
    retrySkippedPath: "",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--" || !a.startsWith("-")) {
      args.positional.push(a);
      continue;
    }
    switch (a) {
      case "-o":
      case "--out":
        args.out = argv[++i] || "";
        break;
      case "--user-data-dir":
        args.userDataDir = argv[++i] || "";
        break;
      case "--profile-directory":
      case "--profile":
        args.profileDirectory = argv[++i] || "";
        break;
      case "--chrome-path":
        args.chromePath = argv[++i] || "";
        break;
      case "--simplepush-key":
        args.simplepushKey = argv[++i] || "";
        break;
      case "--headed":
      case "--no-headless":
        args.forceHeaded = true;
        args.headedFallback = true;
        break;
      case "--headless":
        args.forceHeaded = false;
        args.headedFallback = true;
        break;
      case "--headless-only":
        args.forceHeaded = false;
        args.headedFallback = false;
        break;
      case "--delay":
        args.delay = Number(argv[++i]) || 0;
        break;
      case "-n":
      case "--limit":
      case "--first":
        args.limit = parseLimitArg(argv[++i]);
        break;
      case "--start-at":
      case "--from":
        args.startAt = parseStartAtArg(argv[++i]);
        break;
      case "--resume":
        args.resume = true;
        break;
      case "--resume-dir":
        args.resumeDirs.push(argv[++i] || "");
        break;
      case "--navigation-timeout":
        args.navigationTimeout = Number(argv[++i]) || 120_000;
        break;
      case "--step-timeout":
        args.stepTimeout = Number(argv[++i]) || 90_000;
        break;
      case "--scrape-timeout":
        args.scrapeTimeoutMs = Number(argv[++i]) || 120_000;
        break;
      case "--verbose":
      case "-V":
        args.verbose = true;
        break;
      case "--connect":
        args.connect = true;
        break;
      case "--browser-url":
        args.browserUrl = argv[++i] || "";
        args.connect = true;
        break;
      case "--retry-skipped":
        args.retrySkippedPath = argv[++i] || "";
        break;
      case "-h":
      case "--help":
        args.help = true;
        break;
      default:
        if (a.startsWith("-")) {
          console.error(`Unknown option: ${a}`);
          args.help = true;
        }
        break;
    }
  }

  return args;
}

function printHelp() {
  console.log(`Usage: member-only-yt-transcripts <channel-url> [options]
       member-only-yt-transcripts --retry-skipped PATH [options]

Options:
  --retry-skipped PATH    Process video_id entries from skipped.jsonl (no yt-dlp; deduped order)
  -o, --out DIR              Output directory (default: transcripts)
  --user-data-dir DIR        Chrome user data dir (required unless --connect)
  --profile-directory NAME   Profile folder name, e.g. Default or Profile 1
  --profile NAME             Same as --profile-directory
  --chrome-path PATH         Chrome binary (default: OS default)
  --simplepush-key KEY       Notify on ${CONSECUTIVE_FAIL_STOP} consecutive failures
  --headed, --no-headless    Always use a visible Chrome window (no headless)
  --headless                 Headless first, then headed if that fails (default)
  --headless-only            Headless only (no headed fallback; may fail with extensions)
  --delay SECONDS            Pause after each success (default: 5)
  -n, --limit N, --first N   Only the first N videos (e.g. test: -n 3)
  --start-at N, --from N     Begin at the Nth video in the list (1-based; after --limit)
  --resume                   Skip if *__.txt under -o, --resume-dir(s), or ./MatthewRyder has this id
  --resume-dir DIR          With --resume, also index existing .txt under DIR (repeatable)
  --navigation-timeout MS
  --step-timeout MS
  --scrape-timeout MS        Max wall time per video for one scrape attempt (default: 120000). Must cover nav + extension; increase if you see timeout before soft-skip.
  --verbose, -V             Log navigation URLs and Chrome load steps (stderr)
  --connect                 Attach to Chrome with --remote-debugging-port (see README)
  --browser-url URL         DevTools URL (default: http://127.0.0.1:9222); implies --connect

Attach mode (--connect) does not start Chrome and only disconnects CDP at exit — your browser keeps running.
`);
}

function notifySimplepush(key, title, message) {
  if (!key) return Promise.resolve();
  return new Promise((resolve, reject) => {
    simplepush.send({ key, title, message }, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

function appendSkipLog(skipPath, obj) {
  fs.appendFileSync(
    skipPath,
    `${JSON.stringify(obj)}\n`,
    { encoding: "utf-8" },
  );
}

function sleepMs(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function withTimeout(promise, ms, errMessage) {
  if (ms == null || !Number.isFinite(ms) || ms <= 0) {
    return promise;
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(errMessage));
    }, ms);
    promise.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}

/**
 * Index *__.txt under one directory tree by YouTube video id (after last __).
 * Values are paths relative to cwd when possible, else absolute.
 * @param {string} scanRoot
 * @returns {Map<string, string>}
 */
function buildTranscriptIndexByVideoId(scanRoot) {
  /** @type {Map<string, string>} */
  const map = new Map();
  const rootAbs = path.resolve(scanRoot);
  const cwdAbs = process.cwd();

  /** @param {string} dirAbs */
  function scan(dirAbs) {
    let entries;
    try {
      entries = fs.readdirSync(dirAbs, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const full = path.join(dirAbs, e.name);
      if (e.isDirectory()) {
        scan(full);
      } else if (e.isFile() && e.name.endsWith(".txt")) {
        const base = e.name.slice(0, -".txt".length);
        const sep = base.lastIndexOf("__");
        if (sep === -1) continue;
        const videoId = base.slice(sep + 2);
        if (videoId && !map.has(videoId)) {
          const relCwd = path.relative(cwdAbs, full);
          map.set(
            videoId,
            relCwd && !relCwd.startsWith("..") ? relCwd : full,
          );
        }
      }
    }
  }
  scan(rootAbs);
  return map;
}

/**
 * Merge indexes in order: first directory wins per video id (see collectResumeScanRoots order).
 * @param {string[]} scanRoots absolute dirs
 */
function buildMergedResumeIndex(scanRoots) {
  const merged = new Map();
  for (const root of scanRoots) {
    const partial = buildTranscriptIndexByVideoId(root);
    for (const [id, p] of partial) {
      if (!merged.has(id)) merged.set(id, p);
    }
  }
  return merged;
}

/**
 * Dirs to scan for --resume. Order: ./MatthewRyder (if present), --resume-dir(s), then -o
 * so ids found in MatthewRyder beat duplicates under transcripts/.
 * @param {string} outDirAbs
 * @param {{ resumeDirs: string[] }} args
 */
function collectResumeScanRoots(outDirAbs, args) {
  const seen = new Set();
  const ordered = [];

  function tryAdd(abs) {
    const r = path.resolve(abs);
    if (seen.has(r)) return;
    try {
      if (!fs.statSync(r).isDirectory()) return;
    } catch {
      return;
    }
    seen.add(r);
    ordered.push(r);
  }

  const autoMatthew = path.resolve(process.cwd(), "MatthewRyder");
  if (path.resolve(autoMatthew) !== path.resolve(outDirAbs)) {
    tryAdd(autoMatthew);
  }

  for (const raw of args.resumeDirs) {
    const t = (raw || "").trim();
    if (t) tryAdd(path.resolve(process.cwd(), t));
  }

  tryAdd(outDirAbs);

  return ordered;
}

const SKIPPED_VIDEO_ID_RE = /^[\w-]{11}$/;

/**
 * @param {string} relativeOrAbsolute
 * @returns {Array<[string, string]>} [videoId, title]
 */
function loadVideosFromSkippedJsonl(relativeOrAbsolute) {
  const abs = path.isAbsolute(relativeOrAbsolute)
    ? relativeOrAbsolute
    : path.resolve(process.cwd(), relativeOrAbsolute);
  if (!fs.existsSync(abs)) {
    throw new Error(`file not found: ${abs}`);
  }
  const raw = fs.readFileSync(abs, { encoding: "utf-8" });
  const lines = raw.split("\n");
  const seen = new Set();
  /** @type {Array<[string, string]>} */
  const out = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) continue;
    let o;
    try {
      o = JSON.parse(line);
    } catch {
      continue;
    }
    const id = o.video_id;
    if (typeof id !== "string" || !SKIPPED_VIDEO_ID_RE.test(id)) continue;
    if (seen.has(id)) continue;
    seen.add(id);
    const title = typeof o.title === "string" ? o.title : "";
    out.push([id, title]);
  }
  return out;
}

async function main() {
  const raw = process.argv.slice(2).filter((a) => a !== "--");
  const args = parseArgs(raw);

  const retrySkippedPath = (args.retrySkippedPath || "").trim();

  if (args.help) {
    printHelp();
    process.exit(0);
  }

  if (!retrySkippedPath && !args.positional[0]) {
    printHelp();
    process.exit(1);
  }

  if (args.resumeDirs.some((d) => (d || "").trim()) && !args.resume) {
    console.error("warning: --resume-dir has no effect without --resume.");
  }

  if (!args.connect && !args.userDataDir.trim()) {
    console.error("error: --user-data-dir is required unless you use --connect.");
    process.exit(1);
  }

  const outDir = path.resolve(process.cwd(), args.out);
  fs.mkdirSync(outDir, { recursive: true });
  const skipPath = path.join(outDir, "skipped.jsonl");

  const chromeExecutable =
    args.chromePath.trim() || defaultChromeExecutable();

  let videos;
  if (retrySkippedPath) {
    try {
      videos = loadVideosFromSkippedJsonl(retrySkippedPath);
    } catch (e) {
      console.error(`error: --retry-skipped: ${e.message}`);
      process.exit(1);
    }
    console.error(
      `Retry from skipped log: ${videos.length} unique id(s) from ` +
        `${path.isAbsolute(retrySkippedPath) ? retrySkippedPath : path.resolve(process.cwd(), retrySkippedPath)} → output ${outDir}`,
    );
  } else {
    const channelUrl = args.positional[0];
    try {
      videos = listChannelVideos(channelUrl);
    } catch (e) {
      console.error(`error listing channel: ${e.message}`);
      process.exit(1);
    }
  }

  const totalListed = videos.length;
  if (args.limit != null) {
    videos = videos.slice(0, args.limit);
    console.error(
      (retrySkippedPath ? "Skipped retry" : "Channel listed") +
        ` ${totalListed} video(s); processing first ${videos.length} only (` +
        `-n / --limit / --first). Output: ${outDir}`,
    );
  } else {
    console.error(`Processing ${videos.length} video(s). Output: ${outDir}`);
  }

  if (!videos.length) {
    console.error(
      retrySkippedPath
        ? "No valid video_id lines found in --retry-skipped file."
        : "No videos found for this channel URL (yt-dlp returned an empty list).",
    );
    process.exit(1);
  }

  const batchTotal = videos.length;
  let indexBase = 0;
  if (args.startAt != null) {
    if (args.startAt > batchTotal) {
      console.error(
        `error: --start-at ${args.startAt} is past end of list (${batchTotal} video(s) in this run).`,
      );
      process.exit(1);
    }
    indexBase = args.startAt - 1;
    videos = videos.slice(indexBase);
    console.error(
      `Starting at ${args.startAt}/${batchTotal} (` +
        `${videos.length} video(s) left in this run; progress shows [index/${batchTotal}]).`,
    );
  }

  if (!videos.length) {
    console.error("No videos left to process after --start-at.");
    process.exit(1);
  }

  console.error(
    retrySkippedPath
      ? "Note: Retry mode uses skipped.jsonl only (no yt-dlp). Chrome opens each https://www.youtube.com/watch?v=…"
      : "Note: The channel URL is only used to list video IDs (yt-dlp). Chrome opens each watch page: https://www.youtube.com/watch?v=…",
  );

  const browserUrl = (args.browserUrl || "").trim() || "http://127.0.0.1:9222";

  if (args.connect) {
    console.error(`Browser: attach to existing Chrome at ${browserUrl} (script does not start or quit Chrome).`);
    console.error(
      "Start Chrome with a remote debugging port and your usual profile — see README “Attach to your own Chrome”.",
    );
  } else {
    console.error(
      `Browser: ${args.forceHeaded ? "headed" : "headless"}${args.forceHeaded ? "" : args.headedFallback ? " (with headed fallback)" : " (no fallback)"}.`,
    );
    console.error(
      "Quit Google Chrome fully (Cmd+Q) before running; this tool starts its own Chrome using your profile. A stray Chrome causes \"already running\" / lock errors.",
    );
  }
  const pd = args.profileDirectory.trim();
  if (pd && !args.connect) {
    console.error(`Chrome profile-directory: ${pd}`);
  }

  const session = createBrowserSession({
    executablePath: chromeExecutable,
    userDataDir: args.connect ? "" : path.resolve(args.userDataDir),
    forceHeaded: args.forceHeaded,
    headedFallback: args.headedFallback,
    profileDirectory: pd,
    connectBrowserUrl: args.connect ? browserUrl : null,
  });

  const scrapeMs = Math.max(1_000, args.scrapeTimeoutMs);
  const timeouts = {
    navigationTimeout: Math.min(args.navigationTimeout, scrapeMs),
    stepTimeout: Math.min(args.stepTimeout, scrapeMs),
    verbose: args.verbose,
  };

  console.error(
    `Per-video scrape timeout: ${scrapeMs}ms (fail + skip if exceeded; --scrape-timeout).`,
  );

  const resumeScanRoots = args.resume
    ? collectResumeScanRoots(outDir, args)
    : [];
  if (args.resume && resumeScanRoots.length > 0) {
    console.error(
      `Resume: skip if video id already in any of ${resumeScanRoots.length} folder(s):`,
    );
    for (const r of resumeScanRoots) {
      console.error(`  ${r}`);
    }
  }

  let consecutiveSkips = 0;
  let downloaded = 0;
  let skipped = 0;

  const resumeByVideoId = args.resume
    ? buildMergedResumeIndex(resumeScanRoots)
    : null;

  try {
    for (let i = 0; i < videos.length; i += 1) {
      const [videoId, title] = videos[i];
      const index = indexBase + i + 1;
      const filename = buildOutputFilename(title, videoId);
      const dest = path.join(outDir, filename);
      const watchUrl = youtubeWatchUrl(videoId);

      if (resumeByVideoId?.has(videoId)) {
        const existingRel = resumeByVideoId.get(videoId);
        console.error(
          `[${index}/${batchTotal}] SKIP (resume) ${videoId} -> ${existingRel}`,
        );
        consecutiveSkips = 0;
        continue;
      }

      const display =
        title.length <= 120 ? title : `${title.slice(0, 117)}...`;
      console.error(`[${index}/${batchTotal}] ${videoId}: ${display}`);

      try {
        const lines = await withTimeout(
          session.extractTranscriptForWatchUrl(watchUrl, timeouts),
          scrapeMs,
          `Transcript scrape timed out after ${scrapeMs}ms (--scrape-timeout)`,
        );
        const body = formatTranscriptBody(lines);
        fs.writeFileSync(dest, body, "utf-8");
        downloaded += 1;
        consecutiveSkips = 0;
        if (args.delay > 0 && i < videos.length - 1) {
          await sleepMs(args.delay * 1000);
        }
      } catch (err) {
        skipped += 1;
        const soft =
          err != null &&
          typeof err === "object" &&
          /** @type {{ watchMetadataOk?: boolean }} */ (err).watchMetadataOk ===
            true;
        const reason = err instanceof Error ? err.message : String(err);
        if (soft) {
          consecutiveSkips = 0;
          console.error(`  skip (watch title ok, not a consecutive fail): ${reason}`);
        } else {
          consecutiveSkips += 1;
          console.error(`  skip: ${reason}`);
        }
        if (/already running for/i.test(reason)) {
          console.error(
            "  hint: Another Chrome is using this user data dir. Quit all Chrome windows (Cmd+Q) and any stuck process from a failed run, then retry.",
          );
        }
        if (/WS endpoint URL/i.test(reason)) {
          console.error(
            "  hint: Chrome was slow to start or another Chrome had the profile locked; launch timeout is 6 minutes.",
          );
        }
        if (/Transcript scrape timed out/i.test(reason)) {
          console.error(
            "  hint: Increase --scrape-timeout (ms); watch-title paths can need >60s (nav + several 10s extension steps).",
          );
        }
        appendSkipLog(skipPath, {
          video_id: videoId,
          title,
          reason: `member_extension: ${reason}`,
        });

        if (consecutiveSkips >= CONSECUTIVE_FAIL_STOP) {
          const msg = `Stopped after ${consecutiveSkips} consecutive failures (last: ${videoId}).`;
          console.error(msg);
          try {
            await notifySimplepush(
              args.simplepushKey,
              "YouTube member transcripts",
              msg,
            );
          } catch (notifyErr) {
            console.error(
              `warning: Simplepush failed: ${notifyErr.message || notifyErr}`,
            );
          }
          process.exit(1);
        }
      }
    }
  } finally {
    await session.closeBrowser();
  }

  console.error(
    `Done. Downloaded: ${downloaded}, skipped: ${skipped}, log: ${skipPath}`,
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
