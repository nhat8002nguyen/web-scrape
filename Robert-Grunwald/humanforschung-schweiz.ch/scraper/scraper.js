'use strict';

const puppeteer = require('puppeteer');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');
const { parseDetailPage } = require('./parser');

const BASE_URL = 'https://www.humanforschung-schweiz.ch';
const SEARCH_URL = `${BASE_URL}/en/trial-search/`;
const OUTPUT_DIR = path.join(__dirname, 'output');

// CLI flags: --urls <file>  --output <file>
const args = process.argv.slice(2);
const urlsFlagIdx = args.indexOf('--urls');
const outputFlagIdx = args.indexOf('--output');
const URLS_INPUT_FILE  = urlsFlagIdx  !== -1 ? args[urlsFlagIdx  + 1] : null;
const OUTPUT_FILENAME  = outputFlagIdx !== -1 ? args[outputFlagIdx + 1] : 'sample.xlsx';

const URLS_FILE  = path.join(OUTPUT_DIR, 'urls.txt');
const EXCEL_FILE = path.join(OUTPUT_DIR, OUTPUT_FILENAME);

// Phase 1: collect at least this many study URLs (ignored when --urls is supplied)
const TARGET_URLS = 20;

// Polite delay between axios requests (ms)
const REQUEST_DELAY_MS = 800;

const EXCEL_COLUMNS = [
  { header: 'Study ID',              key: 'studyId' },
  { header: 'Study Title',           key: 'studyTitle' },
  { header: 'Study URL',             key: 'studyUrl' },
  { header: 'Contact Block Title',   key: 'blockTitle' },
  { header: 'Raw Contact Text',      key: 'rawContactText' },
  { header: 'Contact First Name',    key: 'firstName' },
  { header: 'Contact Last Name',     key: 'lastName' },
  { header: 'Contact Email Address', key: 'email' },
  { header: 'Contact Phone Number',  key: 'phone' },
  { header: 'Institution Name',      key: 'institutionName' },
  { header: 'Displayed Source Tag',  key: 'sourceTag' },
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

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Puppeteer: collect study URLs ────────────────────────────────────────────

async function collectStudyUrls(page) {
  console.log('Navigating to search page…');
  await page.goto(SEARCH_URL, { waitUntil: 'networkidle2', timeout: 60000 });

  // Click "Further filters" button
  console.log('Opening Further filters…');
  await page.waitForSelector('button', { timeout: 15000 });
  const filterBtn = await page.evaluateHandle(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    return buttons.find(b => b.textContent.trim() === 'Further filters') || null;
  });
  if (!filterBtn || (await filterBtn.jsonValue()) === null) {
    throw new Error('Could not find "Further filters" button');
  }
  await filterBtn.click();
  await sleep(1500);

  // Check Germany and Austria checkboxes
  console.log('Selecting Germany and Austria…');
  await page.evaluate(() => {
    const labels = Array.from(document.querySelectorAll('label'));
    for (const label of labels) {
      const text = label.textContent.trim();
      if (text === 'Germany' || text === 'Austria') {
        const checkbox = label.querySelector('input[type="checkbox"]');
        if (checkbox && !checkbox.checked) checkbox.click();
      }
    }
  });
  await sleep(500);

  // Click Apply Filters
  console.log('Applying filters…');
  await page.evaluate(() => {
    const divs = Array.from(document.querySelectorAll('div'));
    const btn = divs.find(d => d.textContent.trim() === 'Apply Filters');
    if (btn) btn.click();
  });
  await page.waitForNetworkIdle({ timeout: 15000 }).catch(() => {});
  await sleep(2000);

  const urls = new Set();

  // Collect URLs across pages until we have enough
  while (urls.size < TARGET_URLS) {
    const pageUrls = await page.evaluate((base) => {
      const links = Array.from(document.querySelectorAll('a[href*="/study-detail/"]'));
      return links.map(a => {
        // Use the clean URL without the hash fragment
        const href = a.getAttribute('href').split('#')[0];
        return href.startsWith('http') ? href : base + href;
      });
    }, BASE_URL);

    for (const u of pageUrls) urls.add(u);
    console.log(`  Collected ${urls.size} URLs so far…`);

    if (urls.size >= TARGET_URLS) break;

    // Try to click the next-page button
    const nextBtn = await page.$('.fTjoUN0DQMY0bqIV');
    if (!nextBtn) break;

    const isDisabled = await page.evaluate(el => el.disabled || el.classList.contains('disabled'), nextBtn);
    if (isDisabled) break;

    await nextBtn.click();
    await page.waitForNetworkIdle({ timeout: 10000 }).catch(() => {});
    await sleep(1500);
  }

  return Array.from(urls).slice(0, TARGET_URLS);
}

// ── Axios + cheerio: fetch and parse a detail page ───────────────────────────

async function fetchDetailPage(url, puppeteerPage) {
  let html;
  try {
    const response = await httpClient.get(url);
    html = response.data;
  } catch (err) {
    console.warn(`  axios failed for ${url}: ${err.message} — falling back to Puppeteer`);
    html = null;
  }

  // Fallback: load via Puppeteer if axios failed or contact-box not found
  if (!html || !html.includes('contact-box')) {
    console.log(`  Using Puppeteer fallback for ${url}`);
    await puppeteerPage.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
    html = await puppeteerPage.content();
  }

  return parseDetailPage(html, url);
}

// ── Excel export ─────────────────────────────────────────────────────────────

async function writeExcel(rows) {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet('Contact Data');

  sheet.columns = EXCEL_COLUMNS.map(col => ({
    header: col.header,
    key: col.key,
    width: col.key === 'rawContactText' || col.key === 'studyTitle' ? 50 : 30,
  }));

  // Bold header row
  sheet.getRow(1).font = { bold: true };

  for (const row of rows) {
    sheet.addRow({
      studyId:        row.studyId,
      studyTitle:     row.studyTitle,
      studyUrl:       row.studyUrl,
      blockTitle:     row.blockTitle,
      rawContactText: row.rawContactText,
      firstName:      row.firstName,
      lastName:       row.lastName,
      email:          row.email,
      phone:          row.phone,
      institutionName: row.institutionName,
      sourceTag:      row.sourceTag,
    });
  }

  // Wrap text in rawContactText and institutionName columns
  sheet.getColumn('rawContactText').alignment = { wrapText: true };
  sheet.getColumn('institutionName').alignment = { wrapText: true };

  await workbook.xlsx.writeFile(EXCEL_FILE);
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  let studyUrls;
  let browser = null;
  let detailFallbackPage = null;

  if (URLS_INPUT_FILE) {
    // Fast path: read URLs from file, no Puppeteer needed for the search step
    const resolved = path.isAbsolute(URLS_INPUT_FILE)
      ? URLS_INPUT_FILE
      : path.join(OUTPUT_DIR, URLS_INPUT_FILE);
    studyUrls = fs.readFileSync(resolved, 'utf8')
      .split('\n')
      .map(l => l.trim())
      .filter(Boolean);
    console.log(`Loaded ${studyUrls.length} URLs from ${resolved}`);
    console.log(`Output file: ${EXCEL_FILE}\n`);
  } else {
    // Full path: use Puppeteer to apply filters and collect URLs
    browser = await puppeteer.launch({ headless: true });
    const searchPage = await browser.newPage();
    await searchPage.setRequestInterception(true);
    searchPage.on('request', req => {
      if (['image', 'font', 'media'].includes(req.resourceType())) {
        req.abort();
      } else {
        req.continue();
      }
    });

    try {
      studyUrls = await collectStudyUrls(searchPage);
    } catch (err) {
      console.error('Failed to collect URLs:', err.message);
      await browser.close();
      process.exit(1);
    }

    console.log(`\nCollected ${studyUrls.length} study URLs`);
    fs.writeFileSync(URLS_FILE, studyUrls.join('\n') + '\n', 'utf8');
    console.log(`URLs saved to ${URLS_FILE}`);

    detailFallbackPage = await browser.newPage();
  }

  // Open a Puppeteer fallback page only if we have a browser running
  if (browser && !detailFallbackPage) {
    detailFallbackPage = await browser.newPage();
  }

  const allRows = [];
  for (let i = 0; i < studyUrls.length; i++) {
    const url = studyUrls[i];
    console.log(`\n[${i + 1}/${studyUrls.length}] Fetching: ${url}`);
    try {
      const rows = await fetchDetailPage(url, detailFallbackPage);
      console.log(`  → ${rows.length} contact block(s)`);
      allRows.push(...rows);
    } catch (err) {
      console.error(`  Error on ${url}: ${err.message}`);
    }
    if (i < studyUrls.length - 1) await sleep(REQUEST_DELAY_MS);
  }

  if (browser) await browser.close();

  console.log(`\nTotal rows: ${allRows.length}`);
  await writeExcel(allRows);
  console.log(`Excel saved to ${EXCEL_FILE}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
