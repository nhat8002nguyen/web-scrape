import { vttToPlainText } from "./vtt.mjs";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * @param {import("puppeteer").Page} page
 */
export function findVdocipherFrame(page) {
  return page.frames().find((f) => /vdocipher\.com/i.test(f.url())) ?? null;
}

/**
 * @param {import("puppeteer").Frame} frame
 */
export async function startPlaybackInFrame(frame) {
  await frame.evaluate(async () => {
    const v = document.querySelector("video");
    if (v) {
      try {
        await v.play();
      } catch {
        /* user gesture or policy */
      }
    }
  });
}

/**
 * @param {import("puppeteer").Frame} frame
 * @returns {Promise<string[]|null>}
 */
async function readLyricsPrompterLines(frame) {
  return frame.evaluate(() => {
    const ps = [
      ...document.querySelectorAll(".Lyrics-Prompter p[data-cue-id]"),
    ];
    if (ps.length === 0) return null;
    const rows = ps
      .map((p) => ({
        id: Number(p.getAttribute("data-cue-id")),
        text: (p.textContent || "").trim(),
      }))
      .filter((r) => Number.isFinite(r.id))
      .sort((a, b) => a.id - b.id);
    return rows.map((r) => r.text).filter((t) => t.length > 0);
  });
}

/**
 * @param {import("puppeteer").Frame} frame
 * @returns {Promise<string|null>}
 */
async function getVttUrlFromFrame(frame) {
  const raw = await frame.evaluate(() => {
    const track = document.querySelector(
      'video track[kind="captions"], video track',
    );
    const ts = track?.getAttribute("src");
    if (ts) return ts;
    const s = document.querySelector(
      'script[type="application/json"][data-metadata]',
    );
    if (!s?.textContent) return null;
    try {
      const j = JSON.parse(s.textContent);
      const u = j.captions?.[0]?.url;
      return typeof u === "string" ? u : null;
    } catch {
      return null;
    }
  });
  if (!raw) return null;
  try {
    return new URL(raw, frame.url()).href;
  } catch {
    return null;
  }
}

/**
 * Lesson title is the first primary `h3` under main (vide snippet); "Materials" is a later `h3` with similar classes.
 * Waits for SPA hydration before reading.
 * @param {import("puppeteer").Page} page
 * @param {number} [navigationTimeout]
 */
export async function getLessonTitle(page, navigationTimeout = 90_000) {
  const readTitle = () =>
    page.evaluate(() => {
      const main = document.querySelector("main");
      if (!main) return "";
      for (const h of main.querySelectorAll("h3")) {
        const c = String(h.className || "");
        if (!c.includes("text-xl") || !c.includes("font-semibold")) continue;
        const t = (h.textContent || "").trim();
        if (!t || /^materials$/i.test(t)) continue;
        return t;
      }
      return "";
    });

  try {
    await page.waitForFunction(
      () => {
        const main = document.querySelector("main");
        if (!main) return false;
        for (const h of main.querySelectorAll("h3")) {
          const c = String(h.className || "");
          if (!c.includes("text-xl") || !c.includes("font-semibold")) continue;
          const t = (h.textContent || "").trim();
          if (!t || /^materials$/i.test(t)) continue;
          return true;
        }
        return false;
      },
      { timeout: navigationTimeout },
    );
  } catch {
    /* still try readTitle */
  }
  try {
    return await readTitle();
  } catch {
    return "";
  }
}

/**
 * Wait for VdoCipher iframe, start playback, scrape Lyrics-Prompter or fetch VTT within `afterPlayTranscriptMs` of starting playback.
 * @param {object} opts
 * @param {import("puppeteer").Page} opts.page
 * @param {number} [opts.prePlayTimeoutMs] max time to find iframe (default 120000)
 * @param {number} [opts.afterPlayTranscriptMs] wall time after playback starts for lyrics + any remaining for VTT (default 10000)
 * @param {number} [opts.pollMs]
 */
export async function extractTranscriptFromLessonPage({
  page,
  prePlayTimeoutMs = 120_000,
  afterPlayTranscriptMs = 10_000,
  pollMs = 150,
}) {
  await page.waitForSelector("main", { timeout: 60_000 }).catch(() => {});

  await page
    .waitForFunction(
      () =>
        [...document.querySelectorAll("iframe")].some((f) =>
          (f.src || "").toLowerCase().includes("vdocipher"),
        ),
      { timeout: Math.min(60_000, prePlayTimeoutMs) },
    )
    .catch(() => {});

  const iframeDeadline = Date.now() + prePlayTimeoutMs;
  /** @type {import("puppeteer").Frame|null} */
  let frame = null;
  while (Date.now() < iframeDeadline && !frame) {
    frame = findVdocipherFrame(page);
    if (frame) break;
    await sleep(200);
  }

  if (!frame) {
    throw new Error("VdoCipher iframe not found");
  }

  await startPlaybackInFrame(frame);
  const playStartedAt = Date.now();
  await sleep(300);

  while (Date.now() - playStartedAt < afterPlayTranscriptMs) {
    const lines = await readLyricsPrompterLines(frame);
    if (lines && lines.length > 0) {
      return lines.join("\n");
    }
    const remaining = afterPlayTranscriptMs - (Date.now() - playStartedAt);
    if (remaining <= 0) break;
    await sleep(Math.min(pollMs, remaining));
  }

  const msLeft = Math.max(
    0,
    afterPlayTranscriptMs - (Date.now() - playStartedAt),
  );
  if (msLeft < 200) {
    throw new Error(
      `No transcript within ${afterPlayTranscriptMs}ms after playback`,
    );
  }

  const vttUrl = await getVttUrlFromFrame(frame);
  if (!vttUrl) {
    throw new Error(
      `No transcript within ${afterPlayTranscriptMs}ms after playback`,
    );
  }

  let res;
  try {
    res = await fetch(vttUrl, {
      headers: { Accept: "text/vtt, text/plain, */*" },
      signal: AbortSignal.timeout(msLeft),
    });
  } catch {
    throw new Error(
      `No transcript within ${afterPlayTranscriptMs}ms after playback`,
    );
  }
  if (!res.ok) {
    throw new Error(`VTT fetch failed ${res.status}: ${vttUrl}`);
  }
  const raw = await res.text();
  const text = vttToPlainText(raw);
  if (!text) {
    throw new Error("VTT parsed to empty text");
  }
  return text;
}
