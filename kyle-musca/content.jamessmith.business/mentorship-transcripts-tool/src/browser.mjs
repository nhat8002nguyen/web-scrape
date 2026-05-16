import puppeteer from "puppeteer-core";

/**
 * @param {string} browserURL e.g. http://127.0.0.1:9222
 */
export async function connectToBrowser(browserURL) {
  const url = browserURL.trim().replace(/\/$/, "");
  return puppeteer.connect({
    browserURL: url,
    defaultViewport: { width: 1280, height: 720 },
    protocolTimeout: 180_000,
  });
}

/**
 * @param {import("puppeteer").Browser} browser
 */
export async function acquireActiveWorkPage(browser) {
  const page = await browser.newPage();
  await page.bringToFront().catch(() => {});
  return page;
}

export function defaultChromeExecutable() {
  if (process.platform === "darwin") {
    return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  }
  if (process.platform === "win32") {
    return "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  }
  return "google-chrome";
}

/**
 * @param {object} opts
 * @param {string} opts.executablePath
 * @param {string} opts.userDataDir
 * @param {boolean} opts.headless
 * @param {string} [opts.profileDirectory]
 */
export async function launchBrowser({
  executablePath,
  userDataDir,
  headless,
  profileDirectory,
}) {
  const args = ["--no-first-run", "--no-default-browser-check"];
  const pd = (profileDirectory || "").trim();
  if (pd) {
    args.push(`--profile-directory=${pd}`);
  }
  return puppeteer.launch({
    executablePath,
    userDataDir,
    headless: headless ? "new" : false,
    args,
    defaultViewport: { width: 1280, height: 720 },
    protocolTimeout: 180_000,
    timeout: 360_000,
    waitForInitialPage: false,
  });
}
