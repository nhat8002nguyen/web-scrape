'use strict';

// Merges results-retry.xlsx into results-final.xlsx in the original URL order
// defined by all-urls.txt.
//
// Usage:
//   node merge-retry.js
//   node merge-retry.js --final results-final.xlsx --retry results-retry.xlsx --out results-merged.xlsx

const fs   = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');

const args     = process.argv.slice(2);
const flagVal  = (name, def) => { const i = args.indexOf(name); return i !== -1 ? args[i + 1] : def; };

const OUTPUT_DIR  = path.join(__dirname, 'output');
const FINAL_PATH  = path.join(OUTPUT_DIR, flagVal('--final', 'results-final.xlsx'));
const RETRY_PATH  = path.join(OUTPUT_DIR, flagVal('--retry', 'results-retry.xlsx'));
const MERGED_PATH = path.join(OUTPUT_DIR, flagVal('--out',   'results-merged.xlsx'));
const URLS_PATH   = path.join(OUTPUT_DIR, 'all-urls.txt');

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

// Column letters in order (A–K)
const COL_KEYS = ['studyId','studyTitle','studyUrl','blockTitle','rawContactText',
                  'firstName','lastName','email','phone','institutionName','sourceTag'];

async function readXlsx(filePath) {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(filePath);
  const sheet = wb.worksheets[0];
  const rows = [];
  sheet.eachRow((row, rowNumber) => {
    if (rowNumber === 1) return; // skip header
    const obj = {};
    COL_KEYS.forEach((key, i) => {
      const cell = row.getCell(i + 1);
      obj[key] = cell.value == null ? '' : String(cell.value);
    });
    rows.push(obj);
  });
  return rows;
}

async function main() {
  // Build original URL order index
  if (!fs.existsSync(URLS_PATH)) {
    console.error(`all-urls.txt not found at ${URLS_PATH}`);
    process.exit(1);
  }
  const urlOrder = new Map(
    fs.readFileSync(URLS_PATH, 'utf8')
      .split('\n').map(l => l.trim()).filter(Boolean)
      .map((url, idx) => [url, idx])
  );
  console.log(`Loaded ${urlOrder.size} URLs from all-urls.txt`);

  // Read both workbooks
  console.log(`Reading ${FINAL_PATH}…`);
  const finalRows = await readXlsx(FINAL_PATH);
  console.log(`  ${finalRows.length} rows`);

  console.log(`Reading ${RETRY_PATH}…`);
  const retryRows = await readXlsx(RETRY_PATH);
  console.log(`  ${retryRows.length} rows`);

  const retryUrls = new Set(retryRows.map(r => r.studyUrl));
  console.log(`  ${retryUrls.size} unique study URLs in retry file`);

  // Combine: retry rows override (replace) any existing rows for the same URL,
  // then all rows sorted by their URL's original index.
  const finalRowsByUrl = new Map();
  for (const row of finalRows) {
    if (!finalRowsByUrl.has(row.studyUrl)) finalRowsByUrl.set(row.studyUrl, []);
    finalRowsByUrl.get(row.studyUrl).push(row);
  }
  // Override with retry rows
  for (const row of retryRows) {
    if (!finalRowsByUrl.has(row.studyUrl)) finalRowsByUrl.set(row.studyUrl, []);
    else finalRowsByUrl.get(row.studyUrl); // already exists; override below
  }
  // Build merged group map, retry takes priority
  const mergedByUrl = new Map(finalRowsByUrl);
  const retryByUrl = new Map();
  for (const row of retryRows) {
    if (!retryByUrl.has(row.studyUrl)) retryByUrl.set(row.studyUrl, []);
    retryByUrl.get(row.studyUrl).push(row);
  }
  for (const [url, rows] of retryByUrl) {
    mergedByUrl.set(url, rows); // retry overwrites same-URL rows from final
  }

  // Sort groups by original URL order; unknown URLs go to the end
  const sortedUrls = [...mergedByUrl.keys()].sort((a, b) => {
    const ia = urlOrder.has(a) ? urlOrder.get(a) : Infinity;
    const ib = urlOrder.has(b) ? urlOrder.get(b) : Infinity;
    return ia - ib;
  });

  // Write merged workbook using streaming writer
  const wb = new ExcelJS.stream.xlsx.WorkbookWriter({ filename: MERGED_PATH, useStyles: true });
  const sheet = wb.addWorksheet('Contact Data');
  sheet.columns = EXCEL_COLUMNS;
  sheet.getRow(1).font = { bold: true };
  sheet.getRow(1).commit();

  let totalRows = 0;
  for (const url of sortedUrls) {
    for (const row of mergedByUrl.get(url)) {
      const r = sheet.addRow(COL_KEYS.map(k => row[k] || ''));
      r.getCell(5).alignment = { wrapText: true };  // rawContactText
      r.getCell(10).alignment = { wrapText: true }; // institutionName
      r.commit();
      totalRows++;
    }
  }

  await sheet.commit();
  await wb.commit();

  console.log(`\nMerged ${totalRows} rows → ${MERGED_PATH}`);
  console.log(`  From final  : ${finalRows.length - [...retryUrls].reduce((n, u) => n + (finalRowsByUrl.get(u) || []).length, 0)} rows`);
  console.log(`  From retry  : ${retryRows.length} rows`);
}

main().catch(err => { console.error('Fatal:', err.message); process.exit(1); });
