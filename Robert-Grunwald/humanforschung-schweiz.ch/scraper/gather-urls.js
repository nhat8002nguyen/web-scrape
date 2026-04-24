'use strict';

const puppeteer = require('puppeteer');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { createQueue } = require('./queue');

// ── CLI args ──────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const flagVal = (name, def = null) => {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] ? args[i + 1] : def;
};

const RESUME      = flag('--resume');
const SEED_REDIS  = flag('--seed-redis');
const REDIS_URL   = flagVal('--redis-url', 'redis://127.0.0.1:6379');
const REDIS_KEY   = flagVal('--redis-key', 'humres:urls');

// ── Constants ─────────────────────────────────────────────────────────────────

const BASE_URL    = 'https://www.humanforschung-schweiz.ch';
const SEARCH_URL  = `${BASE_URL}/en/trial-search/`;
const SEARCH_API_URL = `${BASE_URL}/de/`;
const OUTPUT_DIR  = path.join(__dirname, 'output');
const URLS_FILE   = path.join(OUTPUT_DIR, 'all-urls.txt');
const PROGRESS_FILE = path.join(OUTPUT_DIR, 'gather-progress.json');

// Save checkpoint every N pages
const CHECKPOINT_EVERY = 50;
// Delay between page clicks (ms) — be polite to the server
const PAGE_CLICK_DELAY = 1500;
// Batch size when pushing URLs to Redis
const REDIS_BATCH_SIZE = 200;
const API_PAGE_SIZE = 10;

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function loadProgress() {
  try {
    return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));
  } catch {
    return { pageCount: 0, totalCollected: 0 };
  }
}

function saveProgress(pageCount, totalCollected) {
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify({ pageCount, totalCollected }, null, 2));
}

function loadExistingUrls() {
  try {
    return new Set(
      fs.readFileSync(URLS_FILE, 'utf8')
        .split('\n')
        .map(l => l.trim())
        .filter(Boolean)
    );
  } catch {
    return new Set();
  }
}

function appendUrls(urls) {
  if (!urls.length) return;
  fs.appendFileSync(URLS_FILE, urls.join('\n') + '\n', 'utf8');
}

function buildSearchApiUrl(offset) {
  return `${SEARCH_API_URL}?type=1738164853`
    + `&tx_studysearch_studysearchapi[language]=en`
    + `&tx_studysearch_studysearchapi[filter][countries][]=Germany`
    + `&tx_studysearch_studysearchapi[filter][countries][]=Austria`
    + `&tx_studysearch_studysearchapi[sort]=updated_at`
    + `&tx_studysearch_studysearchapi[order]=desc`
    + `&tx_studysearch_studysearchapi[offset]=${offset}`;
}

const FETCH_RETRY_ATTEMPTS = 5;
const FETCH_RETRY_BASE_MS  = 2000;

async function fetchSearchPage(offset) {
  const url = buildSearchApiUrl(offset);
  const requestCfg = {
    timeout: 30000,
    headers: {
      'User-Agent':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
      'Accept': 'application/json,text/plain,*/*',
      'Accept-Language': 'en-US,en;q=0.9',
    },
  };

  let lastErr;
  for (let attempt = 1; attempt <= FETCH_RETRY_ATTEMPTS; attempt++) {
    try {
      const response = await axios.get(url, requestCfg);
      return response.data;
    } catch (err) {
      lastErr = err;
      const waitMs = FETCH_RETRY_BASE_MS * 2 ** (attempt - 1); // 2s, 4s, 8s, 16s, 32s
      console.warn(`  API fetch failed (attempt ${attempt}/${FETCH_RETRY_ATTEMPTS}): ${err.message} — retrying in ${waitMs / 1000}s…`);
      await sleep(waitMs);
    }
  }
  throw lastErr;
}

// ── Puppeteer helpers ─────────────────────────────────────────────────────────

async function applyFilters(page) {
  console.log('Navigating to search page…');
  await page.goto(SEARCH_URL, { waitUntil: 'networkidle2', timeout: 60000 });

  console.log('Opening Further filters…');
  await page.waitForSelector('button', { timeout: 15000 });
  const filterBtn = await page.evaluateHandle(() => {
    return Array.from(document.querySelectorAll('button'))
      .find(b => b.textContent.trim() === 'Further filters') || null;
  });
  if (!filterBtn || (await filterBtn.jsonValue()) === null) {
    throw new Error('Could not find "Further filters" button');
  }
  await filterBtn.click();
  await sleep(1500);

  console.log('Selecting Germany and Austria…');
  await page.evaluate(() => {
    for (const label of document.querySelectorAll('label')) {
      const text = label.textContent.trim();
      if (text === 'Germany' || text === 'Austria') {
        const cb = label.querySelector('input[type="checkbox"]');
        if (cb && !cb.checked) cb.click();
      }
    }
  });
  await sleep(500);

  console.log('Applying filters…');
  await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('div'))
      .find(d => d.textContent.trim() === 'Apply Filters');
    if (btn) btn.click();
  });
  await page.waitForNetworkIdle({ timeout: 15000 }).catch(() => {});
  // Wait until either study detail links are rendered or the page clearly shows no-results state.
  await page.waitForFunction(() => {
    const hasStudyLinks = document.querySelectorAll('a[href*="/study-detail/"]').length > 0;
    const bodyText = (document.body && document.body.innerText ? document.body.innerText : '').toLowerCase();
    const hasNoResultsText =
      bodyText.includes('no results') ||
      bodyText.includes('no studies found') ||
      bodyText.includes('keine resultate') ||
      bodyText.includes('aucun resultat');
    return hasStudyLinks || hasNoResultsText;
  }, { timeout: 45000 }).catch(() => {});
  await sleep(1000);
}

async function extractPageUrls(page) {
  return page.evaluate((base) => {
    return Array.from(document.querySelectorAll('a[href*="/study-detail/"]'))
      .map(a => {
        const href = a.getAttribute('href').split('#')[0];
        return href.startsWith('http') ? href : base + href;
      });
  }, BASE_URL);
}

async function clickNextPage(page) {
  const beforeFirstUrl = await page.evaluate(() => {
    const link = document.querySelector('a[href*="/study-detail/"]');
    if (!link) return '';
    const href = link.getAttribute('href') || '';
    return href.split('#')[0];
  });

  const moved = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button.sfp-pagination-button'));
    if (!buttons.length) return false;

    // The site currently uses class "prev" for going forward to the next page.
    // Fall back to aria-label matching in case markup changes again.
    const candidate = buttons.find(btn =>
      !btn.disabled &&
      !btn.classList.contains('disabled') &&
      (
        btn.classList.contains('prev') ||
        /next page/i.test(btn.getAttribute('aria-label') || '')
      )
    );
    if (!candidate) return false;
    candidate.click();
    return true;
  });

  if (!moved) return false;

  await page.waitForNetworkIdle({ timeout: 10000 }).catch(() => {});
  await page.waitForFunction(
    (previous) => {
      const link = document.querySelector('a[href*="/study-detail/"]');
      if (!link) return false;
      const href = (link.getAttribute('href') || '').split('#')[0];
      return href && href !== previous;
    },
    { timeout: 15000 },
    beforeFirstUrl
  ).catch(() => {});
  await sleep(PAGE_CLICK_DELAY);
  return true;
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  // Setup Redis queue if seeding
  let redisQueue = null;
  if (SEED_REDIS) {
    console.log(`Connecting to Redis at ${REDIS_URL}…`);
    redisQueue = await createQueue('redis', { redisUrl: REDIS_URL, key: REDIS_KEY });
    console.log('Redis connected.');
  }

  // Load resume state
  let { totalCollected } = RESUME ? loadProgress() : { totalCollected: 0 };
  const seenUrls = RESUME ? loadExistingUrls() : new Set();

  // Derive the true next page from the actual number of URLs on disk, not the
  // checkpoint page counter — they can differ when the process crashes between
  // checkpoints, which would otherwise cause 3 consecutive "no new URLs" and
  // a premature stop.
  let pageCount = RESUME ? Math.ceil(seenUrls.size / API_PAGE_SIZE) : 0;

  if (RESUME) {
    console.log(`Resuming from page ${pageCount} (offset ${pageCount * API_PAGE_SIZE}), ${seenUrls.size} URLs already collected.`);
  }

  try {
    let total = null;
    let pagesWithNoNew = 0;

    while (true) {
      const offset = pageCount * API_PAGE_SIZE;
      const payload = await fetchSearchPage(offset);
      const hits = Array.isArray(payload && payload.hits) ? payload.hits : [];
      if (typeof payload.total === 'number') total = payload.total;

      const rawUrls = hits
        .map(hit => hit && hit._source && hit._source.id)
        .filter(id => Number.isInteger(id))
        .map(id => `${BASE_URL}/en/trial-search/study-detail/${id}`);

      const newUrls = rawUrls.filter(u => !seenUrls.has(u));

      for (const u of newUrls) seenUrls.add(u);
      totalCollected += newUrls.length;

      // Persist to file
      appendUrls(newUrls);

      // Push to Redis if seeding
      if (redisQueue && newUrls.length) {
        for (let i = 0; i < newUrls.length; i += REDIS_BATCH_SIZE) {
          await redisQueue.pushMany(newUrls.slice(i, i + REDIS_BATCH_SIZE));
        }
      }

      if (newUrls.length === 0) {
        pagesWithNoNew++;
        if (pagesWithNoNew >= 3) {
          console.log('No new URLs found on 3 consecutive pages — assuming end of results.');
          break;
        }
      } else {
        pagesWithNoNew = 0;
      }

      pageCount++;

      // Checkpoint
      if (pageCount % CHECKPOINT_EVERY === 0) {
        saveProgress(pageCount, totalCollected);
        if (total !== null) {
          console.log(`[Page ${pageCount}] ${totalCollected}/${total} URLs collected so far…`);
        } else {
          console.log(`[Page ${pageCount}] ${totalCollected} URLs collected so far…`);
        }
      }
      if (hits.length < API_PAGE_SIZE) {
        console.log('Last API page reached.');
        break;
      }
      if (total !== null && totalCollected >= total) {
        console.log('Collected all URLs reported by API.');
        break;
      }
      await sleep(150);
    }

    saveProgress(pageCount, totalCollected);
    console.log(`\nDone. Total URLs collected: ${totalCollected}`);
    console.log(`Saved to: ${URLS_FILE}`);
    if (redisQueue) {
      const remaining = await redisQueue.size();
      console.log(`Redis queue size: ${remaining}`);
    }

  } finally {
    if (redisQueue) await redisQueue.close();
  }
}

main().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
