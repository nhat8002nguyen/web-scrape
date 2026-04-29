# Windows Setup Guide

This guide explains how to run the Human Research Switzerland scraper on a
Windows PC without Redis.

## 1. Install Node.js and npm

1. Open <https://nodejs.org/>
2. Download the **LTS** version of Node.js.
3. Run the installer and keep the default options enabled.
4. After installation, open **PowerShell** and check:

```powershell
node --version
npm --version
```

You should see Node.js `v20.x.x` or higher and npm `10.x.x` or higher.

## 2. Open the Project Folder

Open **PowerShell** in the `scraper` folder.

For example, if the project was extracted to `Downloads`, the folder should look
similar to:

```powershell
cd Downloads\humanforschung-schweiz.ch\scraper
```

## 3. Install Dependencies

From the `scraper` folder, run:

```powershell
npm install
```

This installs all required packages. It may take a few minutes.

## 4. Run a Small Test First

Use this to confirm everything works before running the full scrape.

```powershell
node gather-urls.js --pages 5 --output sample-urls.txt
node scrape.js --input sample-urls.txt --output sample-results.xlsx
```

Expected output files:

- `output\sample-urls.txt`
- `output\sample-results.xlsx`

## 5. Run the Full Scrape

```powershell
node gather-urls.js
node scrape.js --input all-urls.txt --output results-final.xlsx
```

Expected output files:

- `output\all-urls.txt`
- `output\results-final.xlsx`

## 6. Resume an Interrupted Run

If PowerShell closes or the computer restarts, resume with:

```powershell
node gather-urls.js --resume
node scrape.js --input all-urls.txt --output results-final.xlsx --resume
```

## 7. Optional: Run Faster

The default scraper uses 3 workers. If the website responds well, you can use
more workers:

```powershell
node scrape.js --input all-urls.txt --output results-final.xlsx --workers 5 --delay 1000
```

If you see many failed URLs, reduce workers or increase delay:

```powershell
node scrape.js --input all-urls.txt --output results-final.xlsx --workers 2 --delay 2000
```

## 8. Troubleshooting

### `node` is not recognized

Close PowerShell, open it again, and retry:

```powershell
node --version
```

If it still fails, reinstall Node.js and make sure the installer adds Node.js
to PATH.

### `npm install` fails

Try deleting `node_modules` and installing again:

```powershell
Remove-Item -Recurse -Force node_modules
npm install
```

### The Excel file is too large

The full run can create a large Excel file. Open it with Excel filters enabled,
or import it into Google Sheets if Excel is slow.
