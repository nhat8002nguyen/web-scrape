#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import simplepush from "simplepush-notifications";

import {
  acquireActiveWorkPage,
  connectToBrowser,
  defaultChromeExecutable,
  launchBrowser,
} from "./browser.mjs";
import {
  collectCourseLinksFromHub,
  collectLessonUrlsFromCoursePage,
  getCategoryTitle,
  lessonIdFromUrl,
  waitForCoursePageInteractive,
} from "./discover.mjs";
import {
  extractTranscriptFromLessonPage,
  getLessonTitle,
} from "./extractLesson.mjs";
import {
  defaultLessonCachePath,
  loadLessonCache,
  saveLessonCache,
} from "./lessonCache.mjs";
import {
  LEAD_MAGNET_CATEGORY,
  buildLessonOutputFilename,
  categoryOutputDirName,
  contentRollupFilename,
  leadMagnetRollupFilename,
} from "./paths.mjs";

const DEFAULT_START = "https://content.jamessmith.business/mentorship";

/** Notify when this many lessons fail transcript extraction in a row. */
const CONSECUTIVE_FAIL_NOTIFY = 3;

/** @param {string|undefined} raw */
function parsePositiveInt(raw, flagName) {
  if (raw == null || raw === "") return null;
  const v = parseInt(String(raw), 10);
  if (!Number.isFinite(v) || v < 1) {
    console.error(`error: ${flagName} expects a positive integer (got: ${raw})`);
    process.exit(1);
  }
  return v;
}

function parseArgs(argv) {
  /** @type {{
   *   positional: string[],
   *   startUrl: string,
   *   out: string,
   *   userDataDir: string,
   *   profileDirectory: string,
   *   chromePath: string,
   *   forceHeaded: boolean,
   *   delay: number,
   *   limit: number|null,
   *   startAt: number|null,
   *   resume: boolean,
   *   navigationTimeout: number,
   *   stepTimeout: number,
   *   scrapeTimeoutMs: number,
   *   transcriptAfterPlayMs: number,
   *   simplepushKey: string,
   *   verbose: boolean,
   *   connect: boolean,
   *   browserUrl: string,
   *   lessonCache: string,
   *   refreshLessonList: boolean,
   *   help?: boolean,
   * }} */
  const args = {
    positional: [],
    startUrl: DEFAULT_START,
    out: "transcripts",
    userDataDir: "",
    profileDirectory: "",
    chromePath: "",
    forceHeaded: true,
    delay: 2,
    limit: null,
    startAt: null,
    resume: false,
    navigationTimeout: 120_000,
    stepTimeout: 90_000,
    scrapeTimeoutMs: 120_000,
    transcriptAfterPlayMs: 10_000,
    simplepushKey: "",
    verbose: false,
    connect: false,
    browserUrl: "http://127.0.0.1:9222",
    lessonCache: "",
    refreshLessonList: false,
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
      case "--headed":
      case "--no-headless":
        args.forceHeaded = true;
        break;
      case "--headless":
        args.forceHeaded = false;
        break;
      case "--delay":
        args.delay = Number(argv[++i]) || 0;
        break;
      case "-n":
      case "--limit":
      case "--first":
        args.limit = parsePositiveInt(argv[++i], "-n / --limit");
        break;
      case "--start-at":
      case "--from":
        args.startAt = parsePositiveInt(argv[++i], "--start-at");
        break;
      case "--resume":
        args.resume = true;
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
      case "--transcript-after-play-ms":
        args.transcriptAfterPlayMs = Number(argv[++i]) || 10_000;
        break;
      case "--simplepush-key":
        args.simplepushKey = argv[++i] || "";
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
      case "--lesson-cache":
        args.lessonCache = argv[++i] || "";
        break;
      case "--refresh-lesson-list":
        args.refreshLessonList = true;
        break;
      case "-h":
      case "--help":
        args.help = true;
        break;
      default:
        if (a.startsWith("-")) {
          console.error(`Unknown option: ${a}`);
          printHelp();
          process.exit(1);
        }
        break;
    }
  }

  const pos = args.positional.filter((x) => x !== "--");
  if (pos[0] && !pos[0].startsWith("-")) {
    args.startUrl = pos[0];
  }

  return args;
}

function printHelp() {
  console.log(`Usage: node src/cli.mjs [start-url] [options]

Start URL defaults to ${DEFAULT_START}

Options:
  -o, --out DIR           Output directory (default: transcripts)
  --user-data-dir DIR     Chrome user data root (required unless --connect)
  --profile-directory, --profile NAME   e.g. Default or Profile 1
  --chrome-path PATH      Chrome binary (default: OS default)
  --headed, --no-headless   Visible window when launching Chrome (default)
  --headless              Headless when launching Chrome
  --delay SECONDS         Pause after each successful lesson (default: 2)
  -n, --limit, --first N  Process at most N lessons total (after --start-at)
  --start-at, --from N    Start at Nth lesson in discovered list (1-based)
  --resume                Skip if OUT_DIR or OUT_DIR/*/*__[lessonId].txt exists
  --navigation-timeout MS (default: 120000)
  --step-timeout MS       Reserved for future step granularity (default: 90000)
  --scrape-timeout MS     Max time to find VdoCipher iframe before play (default: 120000)
  --transcript-after-play-ms MS  Max time after playback for lyrics/VTT (default: 10000)
  --simplepush-key KEY    Notify via Simplepush after ${CONSECUTIVE_FAIL_NOTIFY} scrape failures in a row
  --verbose, -V
  --connect               Attach to Chrome with --remote-debugging-port
  --browser-url URL       DevTools URL (default: http://127.0.0.1:9222); implies --connect
  --lesson-cache FILE     Lesson list JSON (default: OUT_DIR/lesson-queue.json)
  --refresh-lesson-list   Ignore cache; re-scan hub and courses, then rewrite lesson cache

Attach mode (--connect) does not quit your browser when the script exits.

Outputs:
  - One .txt per lesson: OUT_DIR/{category}/{sanitized title}__{lessonId}.txt (category = hub course name)
  - ${leadMagnetRollupFilename()}  at OUT_DIR root (category "${LEAD_MAGNET_CATEGORY}" only)
  - ${contentRollupFilename()}     at OUT_DIR root (all categories; includes Lead Magnet sections)
  - skipped.jsonl on failures
  - lesson-queue.json in OUT_DIR (cached { categoryName, url }[]; skip hub crawl when reused)
`);
}

function logVerbose(verbose, msg) {
  if (verbose) {
    console.error(`[mentorship-transcripts] ${msg}`);
  }
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

function sleepMs(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * @param {string} body
 */
function formatTranscriptFileBody(body) {
  const b = body.trim();
  if (!b) return "\n";
  return b.endsWith("\n") ? b : `${b}\n`;
}

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

/**
 * @param {string} outDir
 * @param {string} categoryName
 */
function lessonCategoryDir(outDir, categoryName) {
  return path.join(outDir, categoryOutputDirName(categoryName));
}

/**
 * @param {string} skipPath
 * @param {Record<string, unknown>} obj
 */
function appendSkipLog(skipPath, obj) {
  fs.appendFileSync(skipPath, `${JSON.stringify(obj)}\n`, "utf-8");
}

/**
 * @param {string} outDir
 * @param {string} categoryName
 * @param {string} videoTitle
 * @param {string} body
 */
function appendRollup(outDir, categoryName, videoTitle, body) {
  const block = `\n\n=== ${categoryName} / ${videoTitle} ===\n\n${body.trim()}\n`;
  const contentRollupPath = path.join(outDir, contentRollupFilename());
  if (categoryName.trim() === LEAD_MAGNET_CATEGORY) {
    fs.appendFileSync(path.join(outDir, leadMagnetRollupFilename()), block, "utf-8");
  }
  fs.appendFileSync(contentRollupPath, block, "utf-8");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    process.exit(0);
  }

  if (!args.connect && !(args.userDataDir || "").trim()) {
    console.error("error: use --connect or provide --user-data-dir");
    process.exit(1);
  }

  const outDir = path.resolve(process.cwd(), args.out);
  fs.mkdirSync(outDir, { recursive: true });
  const skipPath = path.join(outDir, "skipped.jsonl");

  const origin = new URL(args.startUrl).origin;

  const lessonCacheAbs = (args.lessonCache || "").trim()
    ? path.resolve(process.cwd(), args.lessonCache)
    : defaultLessonCachePath(outDir);

  logVerbose(args.verbose, `outDir=${outDir}`);
  logVerbose(args.verbose, `startUrl=${args.startUrl}`);
  logVerbose(args.verbose, `lessonCache=${lessonCacheAbs}`);

  const browser = args.connect
    ? await connectToBrowser(args.browserUrl)
    : await launchBrowser({
        executablePath: args.chromePath || defaultChromeExecutable(),
        userDataDir: args.userDataDir,
        headless: !args.forceHeaded,
        profileDirectory: args.profileDirectory,
      });

  const page = await acquireActiveWorkPage(browser);
  page.setDefaultNavigationTimeout(args.navigationTimeout);
  page.setDefaultTimeout(args.stepTimeout);

  try {
    /** @type {Array<{ categoryName: string; url: string }>} */
    let lessons;

    if (!args.refreshLessonList) {
      const cached = loadLessonCache(lessonCacheAbs, args.startUrl);
      if (cached) {
        lessons = cached;
        logVerbose(
          args.verbose,
          `using lesson cache (${lessons.length} lesson(s), no hub/course crawl)`,
        );
      }
    } else {
      logVerbose(args.verbose, "refresh-lesson-list: will re-scan and rewrite cache");
    }

    if (!lessons) {
      const courses = await collectCourseLinksFromHub(
        page,
        args.startUrl,
        origin,
      );
      logVerbose(args.verbose, `courses=${courses.length}`);

      lessons = [];
      for (const courseUrl of courses) {
        await page.goto(courseUrl, {
          waitUntil: "domcontentloaded",
          timeout: args.navigationTimeout,
        });
        await waitForCoursePageInteractive(page, args.navigationTimeout);
        const categoryName =
          (await getCategoryTitle(page, args.navigationTimeout)) || "untitled";
        const urls = await collectLessonUrlsFromCoursePage(
          page,
          origin,
          args.navigationTimeout,
        );
        logVerbose(
          args.verbose,
          `course "${categoryName}": ${urls.length} lessons`,
        );
        for (const url of urls) {
          lessons.push({ categoryName, url });
        }
      }
      saveLessonCache(lessonCacheAbs, args.startUrl, lessons);
      logVerbose(
        args.verbose,
        `wrote lesson cache (${lessons.length} lesson(s)) -> ${lessonCacheAbs}`,
      );
    }

    let slice = lessons;
    if (args.startAt != null) {
      slice = slice.slice(args.startAt - 1);
    }
    if (args.limit != null) {
      slice = slice.slice(0, args.limit);
    }

    logVerbose(args.verbose, `processing ${slice.length} lesson(s)`);

    let consecutiveScrapeFailures = 0;

    for (const { categoryName, url } of slice) {
      const lessonId = lessonIdFromUrl(url);
      if (args.resume && transcriptExistsForLesson(outDir, lessonId)) {
        logVerbose(args.verbose, `resume skip: ${lessonId}`);
        continue;
      }

      logVerbose(args.verbose, `goto ${url}`);
      try {
        await page.goto(url, {
          waitUntil: "domcontentloaded",
          timeout: args.navigationTimeout,
        });
        const title =
          (await getLessonTitle(page, args.navigationTimeout)) || "untitled";
        const fname = buildLessonOutputFilename(title, lessonId);
        const categoryDir = lessonCategoryDir(outDir, categoryName);
        fs.mkdirSync(categoryDir, { recursive: true });
        const outPath = path.join(categoryDir, fname);

        if (args.resume && fs.existsSync(outPath)) {
          logVerbose(args.verbose, `resume skip file: ${fname}`);
          continue;
        }

        const text = await extractTranscriptFromLessonPage({
          page,
          prePlayTimeoutMs: args.scrapeTimeoutMs,
          afterPlayTranscriptMs: args.transcriptAfterPlayMs,
        });

        fs.writeFileSync(
          outPath,
          formatTranscriptFileBody(text),
          "utf-8",
        );
        appendRollup(outDir, categoryName, title, text);
        logVerbose(
          args.verbose,
          `wrote ${path.relative(outDir, outPath)}`,
        );
        consecutiveScrapeFailures = 0;

        if (args.delay > 0) {
          await sleepMs(args.delay * 1000);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        console.error(`skip ${lessonId}: ${message}`);
        appendSkipLog(skipPath, {
          at: new Date().toISOString(),
          url,
          lessonId,
          categoryName,
          error: message,
        });
        consecutiveScrapeFailures += 1;
        if (
          consecutiveScrapeFailures >= CONSECUTIVE_FAIL_NOTIFY &&
          args.simplepushKey
        ) {
          try {
            await notifySimplepush(
              args.simplepushKey,
              "Mentorship transcripts: scrape failures",
              `${CONSECUTIVE_FAIL_NOTIFY} lessons in a row failed (last: ${lessonId}). Check skipped.jsonl`,
            );
            logVerbose(
              args.verbose,
              `simplepush: notified after ${CONSECUTIVE_FAIL_NOTIFY} consecutive failures`,
            );
          } catch (spErr) {
            console.error(
              `simplepush error: ${spErr instanceof Error ? spErr.message : spErr}`,
            );
          }
          consecutiveScrapeFailures = 0;
        }
      }
    }
  } finally {
    if (args.connect) {
      await browser.disconnect();
    } else {
      await browser.close();
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
