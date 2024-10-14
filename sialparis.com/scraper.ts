import fs from "fs"
import puppeteer from "puppeteer"

// Function to extract email addresses from a string using regex
function extractEmails(text: string): string[] {
  const emailRegex = /([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/gi
  const emails = text.match(emailRegex) || []
  return emails
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

;(async () => {
  const startTime = Date.now()

  // Launch the browser
  const browser = await puppeteer.launch({ headless: true, timeout: 10000 }) // Set to true for headless mode
  const page = await browser.newPage()

  // Navigate to the main exhibitor page
  await page.goto("https://www.sialparis.com/fr-FR/exposants-2024/exhibitors")

  const cookiesbutton = await page.waitForSelector(".banner-actions-container #onetrust-accept-btn-handler")
  await cookiesbutton?.click()

  let exhibitorLinks: string[] = []
  try {
    const data = fs.readFileSync("exhibitor_links.json", "utf8")
    exhibitorLinks = JSON.parse(data)
  } catch (err) {
    console.error("failed to read file: ", err)
  }

  if (exhibitorLinks.length <= 0) {
    // Wait for the initial items to load
    await page.waitForSelector(".ais-InfiniteHits ul li a")

    // Handle pagination to load all exhibitors
    let loadMoreButton = await page.$(".CatalogButton span")
    let pageCount = 1
    while (loadMoreButton) {
      try {
        await loadMoreButton.click()
        pageCount++
        console.log("loaded page ", pageCount)
        await sleep(2000)
        loadMoreButton = await page.waitForSelector(".CatalogButton span")
      } catch (err) {
        console.error("failed to find load more button ", err)
        break
      }
    }

    // Extract exhibitor links
    exhibitorLinks = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll<HTMLAnchorElement>(".ais-InfiniteHits ul li a"))
      return links.map((link) => link.href)
    })

    // Cache exhibitor links to a file (optional)
    fs.writeFileSync("exhibitor_links.json", JSON.stringify(exhibitorLinks))
  }

  // Create a CSV file to store the data
  const csvFile = fs.createWriteStream(`exhibitors-${Date.now()}.csv`)
  csvFile.write("title,website,full_address,country,linkedin,facebook,instagram,twitter,all_categories,email\n")

  // Array to store failed items
  const failedItems: string[] = []

  // Iterate through each exhibitor link
  for (const link of exhibitorLinks) {
    try {
      await page.goto(link)

      // Wait for the exhibitor information to load
      await page.waitForSelector(".CatalogExhibitorStrip-informations h1", { timeout: 10000 })

      const exhibitorData = await page.evaluate(() => {
        const title = document.querySelector(".CatalogExhibitorStrip-informations h1")?.textContent?.trim()
        const addressSpans = Array.from(document.querySelectorAll(".CatalogExhibitorStrip-address span"))
        const fullAddress = addressSpans.map((span) => span.textContent).join(", ")
        const country = addressSpans[addressSpans.length - 1].textContent || ""

        const website = document.querySelector(".CatalogExhibitorStrip-socialitem .cc2-icon-web")
          ? (document.querySelector(".CatalogExhibitorStrip-socialitem .cc2-icon-web") as HTMLAnchorElement).href || ""
          : ""

        // Define getSocialLink within page.evaluate
        function getSocialLink(selector: string): string {
          const element = document.querySelector(selector)
          if (element) {
            const href = (element as HTMLAnchorElement).href
            return href === "javascript:void(0)" ? "" : href
          }
          return ""
        }

        const linkedin = getSocialLink(".CatalogExhibitorStrip-socialitem .cc2-icon-linkedin")
        const facebook = getSocialLink(".CatalogExhibitorStrip-socialitem .cc2-icon-facebook")
        const instagram = getSocialLink(".CatalogExhibitorStrip-socialitem .cc2-icon-instagram")
        const twitter = getSocialLink(".CatalogExhibitorStrip-socialitem .cc2-icon-twitter")

        const categoryLists = Array.from(document.querySelectorAll(".Section-content ul[class=CatalogActivityList]"))
        const allCategories = categoryLists
          .map((list) => {
            const categories = Array.from(list.querySelectorAll("li"))
            return categories.map((category) => category.textContent).join(", ")
          })
          .join("\n")

        return {
          title,
          website,
          fullAddress,
          country,
          linkedin,
          facebook,
          instagram,
          twitter,
          allCategories,
        }
      })

      // Extract email from the website (if available)
      let emails: string[] = []
      if (exhibitorData.website) {
        try {
          await page.goto(exhibitorData.website, { timeout: 20000 })
          let pageContent = await page.content()
          emails.push(...extractEmails(pageContent))

          // Check for a contact page
          let contactLink = await page.$("::-p-xpath(//a[contains(text(), 'contact')])")
          if (!contactLink) {
            contactLink = await page.$("::-p-xpath(//a[contains(@href, 'contact')])")
          }
          if (contactLink) {
            const contactHref = await contactLink.evaluate((el) => (el as HTMLAnchorElement).href)
            await page.goto(contactHref, { timeout: 20000 })
            pageContent = await page.content()
            emails.push(...extractEmails(pageContent))
          }
        } catch (error) {
          console.error(`Error extracting email from ${exhibitorData.website}: ${error}`)
        }
      }
      const uniqueEmails = Array.from(new Set(emails))
      console.log("Data: ", { ...exhibitorData, emails: uniqueEmails.join("; ") })

      // Write the data to the CSV file
      const csvLine = `${exhibitorData.title},${exhibitorData.website},"${exhibitorData.fullAddress}","${
        exhibitorData.country
      }",${exhibitorData.linkedin},${exhibitorData.facebook},${exhibitorData.instagram},${exhibitorData.twitter},"${
        exhibitorData.allCategories
      }",${uniqueEmails.join("; ")}\n`
      csvFile.write(csvLine)
    } catch (error) {
      console.error(`Error processing ${link}: ${error}`)
      failedItems.push(link) // Add failed link to the array
    }
  }

  // Store failed items to a file (if any)
  if (failedItems.length > 0) {
    fs.writeFileSync("failed_items.json", JSON.stringify(failedItems))
    console.log(`${failedItems.length} items failed. See failed_items.json for details.`)
  }

  // Close the CSV file and the browser
  csvFile.end()
  await browser.close()

  // Record the end time and calculate the runtime
  const endTime = Date.now()
  const runtimeInSeconds = (endTime - startTime) / 1000
  console.log(`\nScraper finished in ${runtimeInSeconds} seconds`)
})()
