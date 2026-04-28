'use strict';

const axios = require('axios');
const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');
const simplepush = require('simplepush-notifications');
const { parseDetailPage } = require('./parser');
const { createQueue } = require('./queue');

const SIMPLEPUSH_KEY = '56F6LP';

// ── CLI args ──────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const flagVal = (name, def) => {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] !== undefined ? args[i + 1] : def;
};

const QUEUE_TYPE  = flagVal('--queue', 'memory');
const REDIS_URL   = flagVal('--redis-url', 'redis://127.0.0.1:6379');
const REDIS_KEY   = flagVal('--redis-key', 'humres:urls');
const INPUT_FILE  = flagVal('--input', 'all-urls.txt');
const OUTPUT_FILE = flagVal('--output', 'results.xlsx');
const PROXY_URL   = flagVal('--proxy-url', '');
const PROXY_FILE  = flagVal('--proxy-file', '');
const NUM_WORKERS = Math.max(1, parseInt(flagVal('--workers', '3'), 10));
const DELAY_MS    = Math.max(0, parseInt(flagVal('--delay', '500'), 10));
const RESUME      = flag('--resume');

// ── Constants ─────────────────────────────────────────────────────────────────

const OUTPUT_DIR      = path.join(__dirname, 'output');
const EXCEL_PATH      = path.join(OUTPUT_DIR, OUTPUT_FILE);
const FAILED_PATH     = path.join(OUTPUT_DIR, 'failed-urls.txt');
const SKIPPED_PATH    = path.join(OUTPUT_DIR, 'skipped-urls.txt');
const PROGRESS_PATH   = path.join(OUTPUT_DIR, 'scrape-progress.json');
const DEFAULT_PROXY_FILE = path.join(__dirname, 'free_proxies.txt');

const RETRY_ATTEMPTS  = 3;
const RETRY_BASE_MS   = 1000;
const FLUSH_EVERY     = 500;   // flush Excel stream every N completed URLs
const PROGRESS_EVERY  = 100;   // print progress line every N completed URLs

const EXCEL_COLUMNS = [
  { header: 'Study ID',              key: 'studyId',        width: 45 },
  { header: 'Study Title',           key: 'studyTitle',     width: 55 },
  { header: 'Study URL',             key: 'studyUrl',       width: 80 },
  { header: 'Contact Block Title',   key: 'blockTitle',     width: 30 },
  { header: 'Raw Contact Text',      key: 'rawContactText', width: 55 },
  { header: 'Contact First Name',    key: 'firstName',      width: 22 },
  { header: 'Contact Last Name',     key: 'lastName',       width: 22 },
  { header: 'Contact Email Address', key: 'email',          width: 38 },
  { header: 'Contact Phone Number',  key: 'phone',          width: 22 },
  { header: 'Institution Name',      key: 'institutionName',width: 50 },
  { header: 'Displayed Source Tag',  key: 'sourceTag',      width: 20 },
];

const httpClient = axios.create({
  timeout: 30000,
  headers: {
    'User-Agent':
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
  },
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function withRetry(fn, maxAttempts = RETRY_ATTEMPTS, baseMs = RETRY_BASE_MS) {
  let lastErr;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (attempt < maxAttempts) {
        await sleep(baseMs * 2 ** (attempt - 1)); // 1s, 2s, 4s
      }
    }
  }
  throw lastErr;
}

function parseProxyLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) return null;

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    let parsed;
    try {
      parsed = new URL(trimmed);
    } catch {
      return null;
    }
    if (!parsed.hostname || !parsed.port) return null;
    return {
      host: parsed.hostname,
      port: Number(parsed.port),
      username: decodeURIComponent(parsed.username || ''),
      password: decodeURIComponent(parsed.password || ''),
    };
  }

  const parts = trimmed.split(':');
  if (parts.length < 2) return null;
  const [host, portRaw, username = '', password = ''] = parts;
  const port = Number(portRaw);
  if (!host || Number.isNaN(port)) return null;
  return { host, port, username, password };
}

function loadProxies() {
  const proxies = [];

  if (PROXY_URL) {
    const parsed = parseProxyLine(PROXY_URL);
    if (!parsed) {
      console.warn(`Invalid --proxy-url format: ${PROXY_URL}`);
    } else {
      proxies.push(parsed);
    }
  }

  const proxyFilePath = PROXY_FILE
    ? (path.isAbsolute(PROXY_FILE) ? PROXY_FILE : path.join(__dirname, PROXY_FILE))
    : DEFAULT_PROXY_FILE;

  if (fs.existsSync(proxyFilePath)) {
    const fileProxies = fs.readFileSync(proxyFilePath, 'utf8')
      .split('\n')
      .map(parseProxyLine)
      .filter(Boolean);
    proxies.push(...fileProxies);
  }

  const dedup = new Map();
  for (const p of proxies) {
    const key = `${p.host}:${p.port}:${p.username}:${p.password}`;
    if (!dedup.has(key)) dedup.set(key, p);
  }

  return Array.from(dedup.values());
}

function getProxyForIndex(index, proxies) {
  if (!proxies.length) return null;
  return proxies[index % proxies.length];
}

async function fetchHtml(url, requestIndex, proxies) {
  const proxy = getProxyForIndex(requestIndex, proxies);
  const proxyCfg = proxy
    ? {
        host: proxy.host,
        port: proxy.port,
        auth: proxy.username ? { username: proxy.username, password: proxy.password } : undefined,
      }
    : undefined;

  let res;
  try {
    res = await httpClient.get(url, proxyCfg ? { proxy: proxyCfg } : undefined);
  } catch (proxyErr) {
    // If proxy fails, fallback to direct request so long runs keep going.
    if (!proxyCfg) throw proxyErr;
    res = await httpClient.get(url, { proxy: false });
  }

  if (!res.data.includes('contact-box')) {
    throw new Error('contact-box not found in response — page may not be server-rendered');
  }
  return res.data;
}

function appendFailedUrl(url, reason) {
  fs.appendFileSync(FAILED_PATH, `${url}\t${reason}\n`, 'utf8');
}

function loadProgress() {
  try {
    return JSON.parse(fs.readFileSync(PROGRESS_PATH, 'utf8'));
  } catch {
    return { lastFlushedIndex: -1, completedCount: 0, failedCount: 0 };
  }
}

function saveProgress(state) {
  fs.writeFileSync(PROGRESS_PATH, JSON.stringify(state, null, 2));
}

function formatEta(completedCount, totalCount, startTime) {
  if (completedCount === 0) return '?';
  const elapsed = (Date.now() - startTime) / 1000;
  const rate = completedCount / elapsed;
  const remaining = (totalCount - completedCount) / rate;
  const h = Math.floor(remaining / 3600);
  const m = Math.floor((remaining % 3600) / 60);
  return `~${h}h${m}m`;
}

// ── Excel streaming writer ────────────────────────────────────────────────────

function createExcelWriter() {
  const workbook = new ExcelJS.stream.xlsx.WorkbookWriter({
    filename: EXCEL_PATH,
    useStyles: true,
  });
  const sheet = workbook.addWorksheet('Contact Data');
  sheet.columns = EXCEL_COLUMNS;
  sheet.getRow(1).font = { bold: true };
  sheet.getRow(1).commit();

  return {
    addRow(row) {
      const r = sheet.addRow({
        studyId:         row.studyId,
        studyTitle:      row.studyTitle,
        studyUrl:        row.studyUrl,
        blockTitle:      row.blockTitle,
        rawContactText:  row.rawContactText,
        firstName:       row.firstName,
        lastName:        row.lastName,
        email:           row.email,
        phone:           row.phone,
        institutionName: row.institutionName,
        sourceTag:       row.sourceTag,
      });
      r.getCell('rawContactText').alignment = { wrapText: true };
      r.getCell('institutionName').alignment = { wrapText: true };
      r.commit();
    },
    async commit() {
      await sheet.commit();
      await workbook.commit();
    },
  };
}

// ── Ordered flush buffer ──────────────────────────────────────────────────────
// Workers complete out of order; we buffer results and flush them in URL-index
// order so the Excel output follows the original URL list sequence.

function createFlushBuffer(excelWriter, initialLastFlushed = -1) {
  const buffer = new Map(); // index → rows[]
  let lastFlushedIndex = initialLastFlushed;

  function store(index, rows) {
    buffer.set(index, rows);
  }

  function flush() {
    while (buffer.has(lastFlushedIndex + 1)) {
      const rows = buffer.get(lastFlushedIndex + 1);
      buffer.delete(lastFlushedIndex + 1);
      lastFlushedIndex++;
      for (const row of rows) excelWriter.addRow(row);
    }
    return lastFlushedIndex;
  }

  return { store, flush, getLastFlushed: () => lastFlushedIndex };
}

// ── Worker pool ───────────────────────────────────────────────────────────────

async function runWorkerPool(queue, totalCount, processUrl, numWorkers) {
  let globalIndex = 0; // monotonically increasing index for ordered output

  const worker = async (workerId) => {
    while (true) {
      const url = await queue.pop();
      if (url === null) break;

      const index = globalIndex++;
      await processUrl(url, index, workerId);

      if (DELAY_MS > 0) await sleep(DELAY_MS);
    }
  };

  await Promise.all(
    Array.from({ length: numWorkers }, (_, id) => worker(id))
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const proxies = loadProxies();

  // ── Load URLs and set up queue ──

  let urls = [];
  let queue;

  if (QUEUE_TYPE === 'redis') {
    queue = await createQueue('redis', { redisUrl: REDIS_URL, key: REDIS_KEY });
    const size = await queue.size();
    console.log(`Queue type: Redis  |  ${REDIS_URL}  |  key: ${REDIS_KEY}`);
    console.log(`Items in queue: ${size}`);
    // In Redis mode we don't know total up front if multiple workers share the queue
    // Use queue size at startup as approximate total
    urls = { length: size }; // duck-type for progress display
  } else {
    const resolved = path.isAbsolute(INPUT_FILE)
      ? INPUT_FILE
      : path.join(OUTPUT_DIR, INPUT_FILE);
    if (!fs.existsSync(resolved)) {
      console.error(`Input file not found: ${resolved}`);
      console.error('Run gather-urls.js first, or specify --input <file>');
      process.exit(1);
    }
    urls = fs.readFileSync(resolved, 'utf8')
      .split('\n').map(l => l.trim()).filter(Boolean);
    console.log(`Queue type: memory  |  ${urls.length} URLs loaded from ${resolved}`);
    queue = await createQueue('memory', { items: urls });
  }

  const totalCount = urls.length;

  // ── Resume: skip already-flushed indices ──
  let progress = RESUME ? loadProgress() : { lastFlushedIndex: -1, completedCount: 0, failedCount: 0 };

  if (RESUME && progress.lastFlushedIndex >= 0) {
    console.log(`Resuming from index ${progress.lastFlushedIndex + 1} (${progress.completedCount} done, ${progress.failedCount} failed)`);
    // Drain already-completed URLs from in-memory queue
    if (QUEUE_TYPE === 'memory') {
      for (let i = 0; i <= progress.lastFlushedIndex; i++) {
        await queue.pop(); // discard
      }
    }
  }

  console.log(`Workers: ${NUM_WORKERS}  |  Delay: ${DELAY_MS}ms/worker  |  Output: ${EXCEL_PATH}`);
  if (proxies.length > 0) {
    console.log(`Proxy mode: enabled (${proxies.length} proxies, auto-fallback to direct IP)`);
  } else {
    console.log('Proxy mode: disabled (direct/public IP only)');
  }
  console.log(`Retry: ${RETRY_ATTEMPTS} attempts with exponential backoff\n`);

  // ── Set up Excel writer ──
  const excelWriter = createExcelWriter();
  const flushBuffer = createFlushBuffer(excelWriter, progress.lastFlushedIndex);

  // ── Shared counters (safe for single-threaded async) ──
  let completedCount = progress.completedCount;
  let failedCount    = progress.failedCount;
  let skippedCount   = 0;
  let pendingFlush   = 0; // URLs completed since last Excel flush
  const startTime    = Date.now();

  // ── Per-URL processor ──
  const processUrl = async (url, index, workerId) => {
    let rows = [];
    let fetchFailed = false;
    try {
      const html = await withRetry(() => fetchHtml(url, index, proxies));
      rows = parseDetailPage(html, url);
    } catch (err) {
      fetchFailed = true;
      failedCount++;
      appendFailedUrl(url, err.message.replace(/\t|\n/g, ' '));
      console.error(`  [W${workerId}] FAIL ${url}  — ${err.message.slice(0, 80)}`);
    }

    if (!fetchFailed && rows.length === 0) {
      skippedCount++;
      fs.appendFileSync(SKIPPED_PATH, `${url}\n`, 'utf8');
    }

    flushBuffer.store(index, rows);
    completedCount++;
    pendingFlush++;

    // Flush to Excel and save checkpoint every FLUSH_EVERY URLs
    if (pendingFlush >= FLUSH_EVERY) {
      flushBuffer.flush();
      saveProgress({ lastFlushedIndex: flushBuffer.getLastFlushed(), completedCount, failedCount });
      pendingFlush = 0;
    }

    // Progress line
    if (completedCount % PROGRESS_EVERY === 0) {
      const eta = formatEta(completedCount, totalCount, startTime);
      const pct = totalCount > 0 ? ((completedCount / totalCount) * 100).toFixed(1) : '?';
      console.log(
        `[${completedCount}/${totalCount}] ${pct}%  ✓ ${completedCount - failedCount} done  ✗ ${failedCount} failed  ETA ${eta}`
      );
    }
  };

  // ── Run workers ──
  await runWorkerPool(queue, totalCount, processUrl, NUM_WORKERS);

  // Final flush of any remaining buffered rows
  flushBuffer.flush();

  // Commit the Excel file to disk
  console.log('\nFinalising Excel file…');
  await excelWriter.commit();

  // Save final progress
  saveProgress({ lastFlushedIndex: flushBuffer.getLastFlushed(), completedCount, failedCount });

  await queue.close();

  const elapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
  console.log(`\n${'─'.repeat(60)}`);
  console.log(`Done in ${elapsed} min`);
  console.log(`  URLs processed : ${completedCount}`);
  console.log(`  With rows      : ${completedCount - failedCount - skippedCount}`);
  console.log(`  Skipped (no data): ${skippedCount}  → ${SKIPPED_PATH}`);
  console.log(`  Failed         : ${failedCount}`);
  console.log(`  Excel output   : ${EXCEL_PATH}`);
  if (failedCount > 0) {
    console.log(`  Failed URLs    : ${FAILED_PATH}`);
    console.log(`  Re-run with   : node scrape.js --input output/failed-urls.txt --output output/results-retry.xlsx`);
  }

  const notifMessage =
    `Done in ${elapsed} min | ` +
    `${completedCount - failedCount - skippedCount} rows | ` +
    `${skippedCount} skipped | ` +
    `${failedCount} failed`;
  simplepush.send(
    { key: SIMPLEPUSH_KEY, title: 'Scrape finished ✓', message: notifMessage },
    (err) => { if (err) console.warn('Simplepush error:', err); },
  );
}

main().catch(err => {
  console.error('Fatal:', err.message);
  simplepush.send(
    { key: SIMPLEPUSH_KEY, title: 'Scrape FAILED ✗', message: err.message.slice(0, 200) },
    () => process.exit(1),
  );
});
