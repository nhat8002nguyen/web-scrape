import puppeteer from "puppeteer-core";

const EXTENSION_ROOT_SEL = '[id="-extension-root"]';

/** Extension step budget when `ytd-watch-metadata` title is visible (soft-skip on failure in CLI). */
const WATCH_META_SHORT_STEP_MS = 10_000;

/** Max time to wait for the member extension's "Get Subtitles" control after the Subtitles tab. */
const GET_SUBTITLES_WAIT_MS = 10_000;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Attach to a Chrome you started with --remote-debugging-port (see README).
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
 * Open a dedicated tab for automation. Do not call browser.pages() before newPage()
 * on some CDP sessions — can race Target discovery.
 * @param {import('puppeteer').Browser} browser
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
 * @param {boolean} opts.headless - true => Chrome new headless
 * @param {string} [opts.profileDirectory] - Chrome profile dir name (e.g. Default, Profile 1)
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
    enableExtensions: true,
  });
}

/**
 * @param {import('puppeteer').Page} page
 * @param {string} watchUrl
 * @param {number} navigationTimeout
 * @param {boolean} [verbose]
 */
function youtubeVideoIdFromUrl(u) {
  try {
    const h = new URL(u).hostname.replace(/^www\./, "");
    if (!/youtube\.com$/i.test(h) && !/youtu\.be$/i.test(h)) return null;
    if (/youtu\.be$/i.test(h)) {
      const id = new URL(u).pathname.replace(/^\//, "").split("/")[0];
      return id && /^[\w-]{11}$/.test(id) ? id : null;
    }
    const v = new URL(u).searchParams.get("v");
    return v && /^[\w-]{11}$/.test(v) ? v : null;
  } catch {
    return null;
  }
}

/**
 * YouTube member / paid level gate shown instead of player — skip extension waits.
 * @returns {string} trimmed message if gate present, else ""
 */
async function getMemberOnlyYpcGateSnippet(page) {
  return page.evaluate(() => {
    const el = document.querySelector("div.html5-ypc-description");
    if (!el) return "";
    const t = (el.textContent || "").replace(/\s+/g, " ").trim();
    if (!t) return "";
    if (
      /available to this channel'?s members/i.test(t) ||
      /members-only content/i.test(t)
    ) {
      return t.length > 180 ? `${t.slice(0, 177)}…` : t;
    }
    return "";
  });
}

function throwMemberOnlySoftSkip(snippet) {
  const soft = new Error(
    `Member-only / level paywall (html5-ypc-description): ${snippet}`,
  );
  Object.assign(soft, { watchMetadataOk: true, memberOnlyYpc: true });
  throw soft;
}

async function getWatchMetadataH1Text(page) {
  return page.evaluate(() => {
    function readFromH1(h) {
      if (!h) return "";
      const fs = h.querySelector("yt-formatted-string");
      if (fs) {
        const fromTitle = (fs.getAttribute("title") || "")
          .replace(/\u200b/g, "")
          .trim();
        const fromText = (fs.textContent || "").replace(/\u200b/g, "").trim();
        if (fromTitle) return fromTitle;
        if (fromText) return fromText;
      }
      return (h.textContent || "").replace(/\u200b/g, "").trim();
    }

    const selectors = [
      "ytd-watch-metadata #title h1",
      "ytd-watch-metadata h1",
      "h1.style-scope.ytd-watch-metadata",
    ];
    for (const sel of selectors) {
      const h = document.querySelector(sel);
      const t = readFromH1(h);
      if (t) return t;
    }
    return "";
  });
}

async function gotoWatchUrl(page, watchUrl, navigationTimeout, verbose) {
  await page.setViewport({ width: 1280, height: 720 }).catch(() => {});
  page.setDefaultNavigationTimeout(navigationTimeout);
  await page.bringToFront().catch(() => {});
  if (verbose) {
    console.error(`[member-only-yt] Navigating to: ${watchUrl}`);
  } else {
    console.error(`Loading watch page: ${watchUrl}`);
  }

  const targetId = youtubeVideoIdFromUrl(watchUrl);
  const currentId = youtubeVideoIdFromUrl(page.url());
  if (
    targetId &&
    currentId === targetId &&
    /youtube\.com\/watch/i.test(page.url())
  ) {
    if (verbose) {
      console.error(
        `[member-only-yt] Already on watch?v=${targetId}; skipping navigation`,
      );
    }
    return;
  }

  /** YouTube often never reaches "full" load — prefer domcontentloaded first */
  const attempts = [
    ["domcontentloaded", navigationTimeout],
    ["commit", Math.min(60_000, navigationTimeout)],
    ["load", Math.min(45_000, navigationTimeout)],
  ];

  let lastErr;
  for (const [waitUntil, timeout] of attempts) {
    try {
      await page.goto(watchUrl, { waitUntil, timeout });
      const u = page.url();
      if (verbose) {
        console.error(`[member-only-yt] Loaded (${waitUntil}): ${u}`);
      }
      if (u.startsWith("chrome-error://")) {
        throw new Error(`Chrome error page: ${u}`);
      }
      if (!/youtube\.com|youtu\.be/i.test(u)) {
        throw new Error(`Unexpected URL after navigation: ${u}`);
      }
      return;
    } catch (e) {
      lastErr = e;
      if (verbose) {
        const msg = e instanceof Error ? e.message : String(e);
        console.error(`[member-only-yt] Navigation retry: ${waitUntil} failed — ${msg}`);
      }
    }
  }

  if (verbose) {
    console.error("[member-only-yt] Retrying navigation via window.location.assign …");
  }
  try {
    const assignTimeout = Math.min(navigationTimeout, 120_000);
    await Promise.all([
      page.waitForNavigation({
        waitUntil: "domcontentloaded",
        timeout: assignTimeout,
      }),
      page.evaluate((u) => {
        window.location.assign(u);
      }, watchUrl),
    ]);
    const u = page.url();
    if (verbose) {
      console.error(`[member-only-yt] Loaded (assign): ${u}`);
    }
    if (u.startsWith("chrome-error://")) {
      throw new Error(`Chrome error page: ${u}`);
    }
    if (!/youtube\.com|youtu\.be/i.test(u)) {
      throw new Error(`Unexpected URL after assign: ${u}`);
    }
  } catch (e) {
    const assignErr = e instanceof Error ? e : new Error(String(e));
    throw lastErr instanceof Error
      ? new Error(`${lastErr.message} | assign fallback: ${assignErr.message}`)
      : assignErr;
  }
}

/**
 * @param {"exact" | "includes"} match
 */
async function clickInExtensionByLabel(
  page,
  rootSelector,
  label,
  timeoutMs,
  match = "exact",
) {
  const deadline = Date.now() + timeoutMs;
  const wantNorm = label.replace(/\s+/g, " ").trim().toLowerCase();
  while (Date.now() < deadline) {
    const clicked = await page.evaluate(
      (sel, wantedNorm, matchMode) => {
        function innerRoot() {
          const host = document.querySelector(sel);
          return host ? host.shadowRoot || host : null;
        }
        function collectActionables(inner) {
          const acc = [];
          function walk(node) {
            if (!node) return;
            node
              .querySelectorAll(
                'button, [role="button"], [role="tab"], input[type="button"], input[type="submit"]',
              )
              .forEach((el) => {
                acc.push(el);
              });
            node.querySelectorAll("*").forEach((el) => {
              if (el.shadowRoot) walk(el.shadowRoot);
            });
          }
          walk(inner);
          return acc;
        }
        const inner = innerRoot();
        if (!inner) return false;
        for (const el of collectActionables(inner)) {
          const t = (el.textContent || el.value || "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
          const ok =
            t === wantedNorm ||
            (matchMode === "includes" && t.includes(wantedNorm));
          if (ok) {
            el.click();
            return true;
          }
        }
        return false;
      },
      rootSelector,
      wantNorm,
      match,
    );
    if (clicked) return;
    await sleep(300);
  }
  throw new Error(`Timeout: could not find or click "${label}"`);
}

function throwNoGetSubtitlesSoftSkip() {
  const soft = new Error(
    `Get Subtitles did not appear within ${GET_SUBTITLES_WAIT_MS}ms (not counted as failure).`,
  );
  Object.assign(soft, { watchMetadataOk: true, noGetSubtitlesButton: true });
  throw soft;
}

/**
 * Poll up to {@link GET_SUBTITLES_WAIT_MS} for a matching control, then click. Soft-skip if missing.
 */
async function waitForGetSubtitlesButtonAndClick(page, rootSelector) {
  const deadline = Date.now() + GET_SUBTITLES_WAIT_MS;
  const wantNorm = "get subtitles";
  while (Date.now() < deadline) {
    const clicked = await page.evaluate(
      (sel, wantedNorm) => {
        function innerRoot() {
          const host = document.querySelector(sel);
          return host ? host.shadowRoot || host : null;
        }
        function collectActionables(inner) {
          const acc = [];
          function walk(node) {
            if (!node) return;
            node
              .querySelectorAll(
                'button, [role="button"], [role="tab"], input[type="button"], input[type="submit"]',
              )
              .forEach((el) => {
                acc.push(el);
              });
            node.querySelectorAll("*").forEach((el) => {
              if (el.shadowRoot) walk(el.shadowRoot);
            });
          }
          walk(inner);
          return acc;
        }
        const inner = innerRoot();
        if (!inner) return false;
        for (const el of collectActionables(inner)) {
          const t = (el.textContent || el.value || "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
          if (t === wantedNorm || t.includes(wantedNorm)) {
            el.click();
            return true;
          }
        }
        return false;
      },
      rootSelector,
      wantNorm,
    );
    if (clicked) return;
    await sleep(300);
  }
  throwNoGetSubtitlesSoftSkip();
}

/**
 * @param {import('puppeteer').Page} page
 * @param {string} watchUrl
 * @param {{ navigationTimeout?: number, stepTimeout?: number, verbose?: boolean }} [options]
 * @returns {Promise<string[]>}
 */
export async function extractTranscriptLines(page, watchUrl, options = {}) {
  const navigationTimeout = options.navigationTimeout ?? 120_000;
  const stepTimeout = options.stepTimeout ?? 90_000;
  const { verbose = false } = options;

  await gotoWatchUrl(page, watchUrl, navigationTimeout, verbose);

  await page.bringToFront().catch(() => {});

  const ypcSnippet = await getMemberOnlyYpcGateSnippet(page);
  if (ypcSnippet) {
    throwMemberOnlySoftSkip(ypcSnippet);
  }

  const metaTitleText = await getWatchMetadataH1Text(page);
  const hasWatchMetaTitle = metaTitleText.length > 0;
  const stepEff = hasWatchMetaTitle ? WATCH_META_SHORT_STEP_MS : stepTimeout;

  try {
    await page.waitForSelector(EXTENSION_ROOT_SEL, { timeout: stepEff });
    await page.waitForFunction(
      (sel) => {
        const host = document.querySelector(sel);
        if (!host) return false;
        const inner = host.shadowRoot || host;
        function hasControl(r) {
          if (!r) return false;
          if (r.querySelector('button, [role="button"], [role="tab"]'))
            return true;
          for (const el of r.querySelectorAll("*")) {
            if (el.shadowRoot && hasControl(el.shadowRoot)) return true;
          }
          return false;
        }
        return hasControl(inner);
      },
      { timeout: stepEff },
      EXTENSION_ROOT_SEL,
    );
    await sleep(400);
    await clickInExtensionByLabel(
      page,
      EXTENSION_ROOT_SEL,
      "subtitles",
      stepEff,
      "exact",
    );
    await sleep(500);
    await waitForGetSubtitlesButtonAndClick(page, EXTENSION_ROOT_SEL);

    await page.waitForFunction(
      (sel) => {
        function innerRoot() {
          const host = document.querySelector(sel);
          return host ? host.shadowRoot || host : null;
        }
        function shadowQueryAll(root, css) {
          const out = [];
          function walk(r) {
            if (!r) return;
            r.querySelectorAll(css).forEach((e) => {
              out.push(e);
            });
            r.querySelectorAll("*").forEach((el) => {
              if (el.shadowRoot) walk(el.shadowRoot);
            });
          }
          walk(root);
          return out;
        }
        const inner = innerRoot();
        if (!inner) return false;
        if (shadowQueryAll(inner, ".xiiOB8Kg").length > 0) return true;
        for (const d of shadowQueryAll(inner, "div")) {
          const spans = d.querySelectorAll(":scope > span");
          if (spans.length >= 2) return true;
        }
        return false;
      },
      { timeout: stepEff },
      EXTENSION_ROOT_SEL,
    );

    await sleep(400);

    const lines = await page.evaluate((sel) => {
      function innerRoot() {
        const host = document.querySelector(sel);
        return host ? host.shadowRoot || host : null;
      }
      function shadowQueryAll(root, css) {
        const out = [];
        function walk(r) {
          if (!r) return;
          r.querySelectorAll(css).forEach((e) => {
            out.push(e);
          });
          r.querySelectorAll("*").forEach((el) => {
            if (el.shadowRoot) walk(el.shadowRoot);
          });
        }
        walk(root);
        return out;
      }
      const inner = innerRoot();
      if (!inner) return [];
      let rows = shadowQueryAll(inner, ".xiiOB8Kg");
      if (!rows.length) {
        rows = shadowQueryAll(inner, "div").filter((d) => {
          const spans = d.querySelectorAll(":scope > span");
          return spans.length >= 2;
        });
      }
      const out = [];
      for (const r of rows) {
        const spans = r.querySelectorAll("span");
        let text = "";
        if (spans.length >= 2) text = spans[1].textContent || "";
        else if (spans.length === 1) text = spans[0].textContent || "";
        text = text.replace(/\u200b/g, "").trim();
        if (text) out.push(text);
      }
      return out;
    }, EXTENSION_ROOT_SEL);

    if (!lines.length) {
      throw new Error("Transcript container found but no lines extracted");
    }
    return lines;
  } catch (err) {
    if (
      err != null &&
      typeof err === "object" &&
      /** @type {{ watchMetadataOk?: boolean }} */ (err).watchMetadataOk === true
    ) {
      throw err;
    }
    if (hasWatchMetaTitle) {
      const msg = err instanceof Error ? err.message : String(err);
      const soft = new Error(
        `${msg} (watch metadata h1 has title; ${WATCH_META_SHORT_STEP_MS}ms extension budget — not counted toward stop threshold)`,
      );
      Object.assign(soft, { watchMetadataOk: true });
      throw soft;
    }
    throw err;
  }
}

/**
 * Creates a session: either launch Chrome (--user-data-dir) or attach (--connect).
 * @param {object} opts
 * @param {string} opts.executablePath
 * @param {string} opts.userDataDir
 * @param {boolean} opts.forceHeaded
 * @param {boolean} opts.headedFallback
 * @param {string} [opts.profileDirectory]
 * @param {string|null} [opts.connectBrowserUrl] - e.g. http://127.0.0.1:9222
 */
export function createBrowserSession(opts) {
  const {
    executablePath,
    userDataDir,
    forceHeaded,
    headedFallback,
    profileDirectory = "",
    connectBrowserUrl = null,
  } = opts;

  const rawConnect = (connectBrowserUrl || "").trim();
  const isConnect = Boolean(rawConnect);

  /** @type {import('puppeteer').Browser | null} */
  let browser = null;
  let useHeadless = isConnect ? false : !forceHeaded;
  let headedFallbackLeft =
    !isConnect && headedFallback && !forceHeaded;

  async function ensureBrowser() {
    if (browser) return browser;
    if (isConnect) {
      browser = await connectToBrowser(rawConnect);
    } else {
      browser = await launchBrowser({
        executablePath,
        userDataDir,
        headless: useHeadless,
        profileDirectory,
      });
    }
    return browser;
  }

  async function switchToHeaded() {
    if (isConnect) {
      throw new Error(
        "Headed fallback is unavailable in --connect mode; use a normal Chrome window.",
      );
    }
    if (browser) {
      await browser.close().catch(() => {});
      browser = null;
    }
    useHeadless = false;
    browser = await launchBrowser({
      executablePath,
      userDataDir,
      headless: false,
      profileDirectory,
    });
  }

  /** @type {import('puppeteer').Page | null} */
  let workPage = null;

  async function getWorkPage() {
    const b = await ensureBrowser();
    if (!workPage || workPage.isClosed()) {
      workPage = await acquireActiveWorkPage(b);
    }
    return workPage;
  }

  return {
    /**
     * @param {string} watchUrl
     * @param {{ navigationTimeout?: number, stepTimeout?: number, verbose?: boolean }} [options]
     */
    async extractTranscriptForWatchUrl(watchUrl, options) {
      try {
        const page = await getWorkPage();
        return await extractTranscriptLines(page, watchUrl, options);
      } catch (err) {
        if (headedFallbackLeft && useHeadless) {
          headedFallbackLeft = false;
          workPage = null;
          await switchToHeaded();
          const page = await getWorkPage();
          return extractTranscriptLines(page, watchUrl, options);
        }
        throw err;
      }
    },

    async closeBrowser() {
      if (browser) {
        if (isConnect) {
          await browser.disconnect();
        } else {
          await browser.close().catch(() => {});
        }
        browser = null;
      }
      workPage = null;
    },
  };
}
