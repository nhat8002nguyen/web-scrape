const puppeteer = require("puppeteer");
const simplepush = require("simplepush-notifications");
const { default: axios } = require("axios");
const XLSX = require("xlsx");

const userAgents = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36",
];

const pageStart = 100;
const pageEnd = 147;

async function scrapeData() {
  let browser;
  try {
    const entityIds = new Set();
    let pageCount = pageStart;
    let consecutiveDuplications = 0;

    // Stage 1: Fetch entity IDs from API
    while (consecutiveDuplications < 3 && pageCount < pageEnd) {
      const apiUrl = `https://ecatalogueusearch-api.firabarcelona.com/v1/us/unifiedSearch?page=${pageCount}&size=9&language=en_GB`;

      // Set a random user agent for this request
      const randomUserAgent = userAgents[Math.floor(Math.random() * userAgents.length)];

      const response = await axios.post(
        apiUrl,
        {
          eventName: "",
          sapCode: "J134025",
          eventCode: "",
          searchText: "",
          brand: "",
          selectedHierarchicalProperties: [],
          selectedProperties: [],
          selectedSectors: [],
          selectedHomeOds: [],
          selectedCountries: [],
          filter: "ONLY_EXHIBITORS",
          searchOrder: "BY_RELEVANCE",
          language: "en_GB",
          maxTextLength: 500,
          selectedMultiEvents: [],
          createCache: 0,
        },
        {
          headers: {
            accept: "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,vi;q=0.8",
            "content-type": "application/json",
            origin: "https://ecatalogue.firabarcelona.com",
            priority: "u=1, i",
            referer: "https://ecatalogue.firabarcelona.com/",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": randomUserAgent,
          },
        }
      );

      const newIds = response.data.list.map((item) => item.entityId);
      console.log("Fetched entity IDs:", newIds);

      for (const id of newIds) {
        if (entityIds.has(+id)) {
          consecutiveDuplications++;
        } else {
          consecutiveDuplications = 0;
          entityIds.add(+id);
        }
      }

      pageCount++;
    }

    // Stage 2: Scrape data for each entity ID
    browser = await puppeteer.launch({
      headless: true, // Set to true for headless mode
      defaultViewport: null,
    });
    const page = await browser.newPage();

    const existingIds = new Set();
    try {
      const workbook = XLSX.readFile("exhibitor_data_100-146.xlsx");
      const sheet = workbook.Sheets["Exhibitors"];
      const jsonData = XLSX.utils.sheet_to_json(sheet);
      jsonData.forEach((row) => {
        if (row.EntityId) {
          existingIds.add(row.EntityId);
        }
      });
      console.log("Existing IDs loaded from file:", existingIds);
    } catch (err) {
      console.warn("Error reading existing data file or file does not exist:", err);
    }

    const data = [];
    for (const entityId of entityIds) {
      if (existingIds.has(entityId)) {
        console.log("Skipping entity ID:", entityId);
        continue;
      }

      try {
        const url = `https://ecatalogue.firabarcelona.com/barcelonawineweek2025/exhibitor/${entityId}/detail?lang=en_GB`;

        // Set a random user agent for this request
        const randomUserAgent = userAgents[Math.floor(Math.random() * userAgents.length)];
        await page.setUserAgent(randomUserAgent);

        await page.goto(url);

        // Wait for the title to appear
        try {
          await page.waitForSelector(".detail--exhibitor .detail-content__title", { timeout: 10000 });
        } catch (error) {
          console.warn(`Timeout waiting for selector for entity ID: ${entityId}`);
          continue;
        }

        const companyName = await page
          .$eval(".detail--exhibitor .detail-content__title", (el) => el.textContent.trim())
          .catch(() => "N/A");
        const description = await page
          .$eval(".detail-content__description .description", (el) => el.textContent.trim())
          .catch(() => "N/A");
        const website = await page.$eval(".detail-contact__item a", (el) => el.href).catch(() => "N/A");
        const socialMediaLinks = await page
          .$$eval(".detail-contact__item a", (elements) => elements.slice(1).map((el) => el.href))
          .catch(() => []);

        console.log("Scraped data for entity ID:", entityId);
        console.log("Company:", companyName);
        console.log("Description:", description);
        console.log("Website:", website);
        console.log("Social media:", socialMediaLinks.join(", "));
        console.log("--------------------\n");

        const row = {
          EntityId: +entityId,
          Company: companyName,
          Description: description,
          Website: website,
          SocialMedia: socialMediaLinks.join(";"), // Join links with semicolon
        };

        data.push(row);
      } catch (err) {
        console.error(`Error scraping data for entity ID: ${entityId}`, err);
      }
    }

    // Store data in XLSX file
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Exhibitors");
    XLSX.writeFile(workbook, "exhibitor_data.xlsx");

    console.log("Data scraped successfully!");
    simplepush.send({ key: "nathan123", title: "Scraped done!", message: `scraped ${entityIds.size}`, event: "event" });
  } catch (error) {
    console.error("Error scraping data:", error);
  } finally {
    await browser?.close();
  }
}

scrapeData();
