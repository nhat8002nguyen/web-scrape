'use strict';

const puppeteer = require('puppeteer');
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
const OUTPUT_DIR  = path.join(__dirname, 'output');
const URLS_FILE   = path.join(OUTPUT_DIR, 'all-urls.txt');
const PROGRESS_FILE = path.join(OUTPUT_DIR, 'gather-progress.json');

// Save checkpoint every N pages
const CHECKPOINT_EVERY = 50;
// Delay between page clicks (ms) — be polite to the server
const PAGE_CLICK_DELAY = 1500;
// Batch size when pushing URLs to Redis
const REDIS_BATCH_SIZE = 200;

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
  const nextBtn = await page.$('.fTjoUN0DQMY0bqIV');
  if (!nextBtn) return false;
  const isDisabled = await page.evaluate(
    el => el.disabled || el.classList.contains('disabled'), nextBtn
  );
  if (isDisabled) return false;
  await nextBtn.click();
  await page.waitForNetworkIdle({ timeout: 10000 }).catch(() => {});
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
  let { pageCount, totalCollected } = RESUME ? loadProgress() : { pageCount: 0, totalCollected: 0 };
  const seenUrls = RESUME ? loadExistingUrls() : new Set();

  if (RESUME) {
    console.log(`Resuming from page ${pageCount}, ${seenUrls.size} URLs already collected.`);
  }

  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  // Block heavy resources
  await page.setRequestInterception(true);
  page.on('request', req => {
    if (['image', 'font', 'media'].includes(req.resourceType())) req.abort();
    else req.continue();
  });

  try {
    // Always apply filters fresh (filters are session state, not persisted across restarts)
    await applyFilters(page);

    // If resuming, skip to the correct page by clicking through
    if (RESUME && pageCount > 0) {
      console.log(`Fast-forwarding to page ${pageCount}…`);
      for (let i = 0; i < pageCount; i++) {
        const moved = await clickNextPage(page);
        if (!moved) {
          console.log('Reached last page during fast-forward — already complete.');
          await browser.close();
          if (redisQueue) await redisQueue.close();
          return;
        }
        if ((i + 1) % 100 === 0) console.log(`  Fast-forwarded ${i + 1} pages…`);
      }
    }

    let pagesWithNoNew = 0;

    while (true) {
      const rawUrls = await extractPageUrls(page);
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
        console.log(`[Page ${pageCount}] ${totalCollected} URLs collected so far…`);
      }

      const hasMore = await clickNextPage(page);
      if (!hasMore) {
        console.log('No more pages.');
        break;
      }
    }

    saveProgress(pageCount, totalCollected);
    console.log(`\nDone. Total URLs collected: ${totalCollected}`);
    console.log(`Saved to: ${URLS_FILE}`);
    if (redisQueue) {
      const remaining = await redisQueue.size();
      console.log(`Redis queue size: ${remaining}`);
    }

  } finally {
    await browser.close();
    if (redisQueue) await redisQueue.close();
  }
}

main().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
