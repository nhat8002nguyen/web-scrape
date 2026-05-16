const COURSE_PATH_RE = /^\/content\/[^/]+$/;

/**
 * Absolute course URLs from mentorship hub (grid of category cards).
 * @param {import("puppeteer").Page} page
 * @param {string} hubUrl
 * @param {string} origin e.g. `https://content.jamessmith.business`
 */
export async function collectCourseLinksFromHub(page, hubUrl, origin) {
  await page.goto(hubUrl, { waitUntil: "domcontentloaded", timeout: 120_000 });
  await page.waitForSelector("main", { timeout: 60_000 });
  // SPA: course grid mounts after first paint.
  await page.waitForSelector('main a[href*="/content/"]', { timeout: 90_000 });

  const hrefs = await page.$$eval("main a[href]", (anchors) =>
    anchors.map((a) => a.getAttribute("href")).filter(Boolean),
  );

  /** @type {Set<string>} */
  const out = new Set();
  for (const h of hrefs) {
    try {
      const u = new URL(h, origin);
      const p = u.pathname.replace(/\/$/, "");
      if (COURSE_PATH_RE.test(p)) {
        out.add(`${origin}${p}`);
      }
    } catch {
      /* skip invalid */
    }
  }
  return [...out].sort();
}

/**
 * Course and section pages hydrate after `domcontentloaded`; section/lesson routes always
 * expose anchors whose href contains `/sections/`.
 * @param {import("puppeteer").Page} page
 * @param {number} navigationTimeout
 */
export async function waitForCoursePageInteractive(page, navigationTimeout) {
  await page.waitForSelector("main", { timeout: 60_000 }).catch(() => {});
  await page.waitForSelector('main a[href*="/sections/"]', {
    timeout: navigationTimeout,
  });
}

/**
 * Course hero title: SPA may hydrate after `domcontentloaded`; class order can differ from `h3.text-2xl.font-semibold`.
 * @param {import("puppeteer").Page} page
 * @param {number} [navigationTimeout]
 */
export async function getCategoryTitle(page, navigationTimeout = 90_000) {
  const readTitle = () =>
    page.evaluate(() => {
      const main = document.querySelector("main");
      if (!main) return "";
      for (const h of main.querySelectorAll("h3")) {
        const c = String(h.className || "");
        if (c.includes("text-2xl") && c.includes("font-semibold")) {
          const t = (h.textContent || "").trim();
          if (t) return t;
        }
      }
      for (const h of main.querySelectorAll("h3")) {
        const c = String(h.className || "");
        if (!c.includes("font-semibold")) continue;
        const t = (h.textContent || "").trim();
        if (t) return t;
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
          if (!c.includes("text-2xl") || !c.includes("font-semibold")) continue;
          if ((h.textContent || "").trim().length > 0) return true;
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

const LESSON_IN_SECTION_RE = /^\/content\/[^/]+\/sections\/[^/]+\/content\/[^/]+$/;
const SECTION_LANDING_RE = /^\/content\/[^/]+\/sections\/[^/]+$/;

/**
 * From current course page, list absolute lesson URLs. Handles:
 * - Flat list (`/sections/root/content/…`)
 * - Pure section-index courses
 * - Mixed pages: direct videos + section cards on the same page (e.g. bonus sections)
 * - Nested sections via a queue (subsections link to more `/content/…/sections/…` landings)
 *
 * @param {import("puppeteer").Page} page
 * @param {string} origin
 * @param {number} navigationTimeout
 */
export async function collectLessonUrlsFromCoursePage(
  page,
  origin,
  navigationTimeout,
) {
  await waitForCoursePageInteractive(page, navigationTimeout);

  const hrefs = await page.$$eval("main a[href]", (as) =>
    as.map((a) => a.getAttribute("href")).filter(Boolean),
  );

  /** @type {Set<string>} */
  const lessonUrls = new Set();
  /** @type {Set<string>} */
  const enqueuedOrVisitedSectionPaths = new Set();
  /** @type {string[]} */
  const sectionQueue = [];

  /**
   * @param {string} h raw href
   */
  const triageHref = (h) => {
    let u;
    try {
      u = new URL(h, origin);
    } catch {
      return;
    }
    const path = u.pathname.replace(/\/$/, "") || "/";

    if (LESSON_IN_SECTION_RE.test(path)) {
      lessonUrls.add(`${u.origin}${path}`);
      return;
    }

    if (SECTION_LANDING_RE.test(path)) {
      if (!enqueuedOrVisitedSectionPaths.has(path)) {
        enqueuedOrVisitedSectionPaths.add(path);
        sectionQueue.push(u.href);
      }
    }
  };

  for (const h of hrefs) {
    triageHref(h);
  }

  sectionQueue.sort((a, b) =>
    new URL(a).pathname.localeCompare(new URL(b).pathname),
  );

  while (sectionQueue.length > 0) {
    const sectionUrl = sectionQueue.shift();
    if (!sectionUrl) continue;

    let pathKey;
    try {
      pathKey = new URL(sectionUrl).pathname.replace(/\/$/, "") || "/";
    } catch {
      continue;
    }
    if (!SECTION_LANDING_RE.test(pathKey)) continue;

    await page.goto(sectionUrl, {
      waitUntil: "domcontentloaded",
      timeout: navigationTimeout,
    });
    await waitForCoursePageInteractive(page, navigationTimeout);

    const sub = await page.$$eval("main a[href]", (as) =>
      as.map((a) => a.getAttribute("href")).filter(Boolean),
    );
    for (const h of sub) {
      triageHref(h);
    }

    sectionQueue.sort((a, b) =>
      new URL(a).pathname.localeCompare(new URL(b).pathname),
    );
  }

  return [...lessonUrls].sort();
}

/**
 * Last path segment (lesson id).
 * @param {string} lessonUrl
 */
export function lessonIdFromUrl(lessonUrl) {
  try {
    const p = new URL(lessonUrl).pathname.replace(/\/$/, "");
    const parts = p.split("/");
    return parts[parts.length - 1] || "unknown";
  } catch {
    return "unknown";
  }
}
