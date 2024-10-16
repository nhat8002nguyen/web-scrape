import fs from "fs"
import puppeteer, { Page } from "puppeteer"
import querystring from "querystring"
import request from "request"

// constants for running
const startIndex = 0
const endIndex = 2050

const simplepushUrl = "https://api.simplepush.io/send"

// Function to extract email addresses from a string using regex
function extractEmails(text: string): string[] {
  const emailRegex =
    /([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]*[a-zA-Z]+[a-zA-Z0-9._-]*\.[a-zA-Z0-9_-]*[a-zA-Z]+[a-zA-Z0-9_-]*)/gi
  const emails = text.match(emailRegex) || []
  return emails
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const urls = [
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Autres%20boissons%20alcoolis%C3%A9es",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Boissons%20sans%20alcool",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Epicerie",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Fruits%2C%20l%C3%A9gumes%2C%20l%C3%A9gumineuses%20et%20grains",

  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Fruits%2C%20l%C3%A9gumes%2C%20l%C3%A9gumineuses%20et%20grains",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Produits%20de%20la%20mer",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Produits%20laitiers%2C%20oeufs",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Produits%20laitiers%2C%20oeufs",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Produits%20surgel%C3%A9s",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Produits%20traiteur",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Viandes%20et%20abats",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Vins%20et%20spiritueux",
  "https://www.sialparis.com/fr-FR/exposants-2024/exhibitors?catalog.prod.sial.exhibitors.fr.name-asc%5BhierarchicalMenu%5D%5BbusinessArea.categories.lvl0%5D%5B0%5D=Volailles%20et%20gibiers",
]

;(async () => {
  try {
    const startTime = Date.now()

    // Launch the browser
    const browser = await puppeteer.launch({ headless: true, timeout: 10000, protocolTimeout: 10 * 60 * 1000 }) // Set to true for headless mode
    const page = await browser.newPage()

    for (let i = 0; i < urls.length; i++) {
      // Navigate to the main exhibitor page
      await page.goto(urls[i], { timeout: 2 * 60 * 1000 })

      try {
        const cookiesbutton = await page.waitForSelector(".banner-actions-container #onetrust-accept-btn-handler")
        await cookiesbutton?.click()
      } catch (err) {
        console.error("Failed to wait and click cookies button: ", err)
      }

      let exhibitorLinks: string[] = []
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
      }

      // Create a CSV file to store the data
      const csvFile = fs.createWriteStream(`output/exhibitors-${i}.csv`)
      csvFile.write(
        "title,website,full_address,country,linkedin,facebook,instagram,twitter,all_categories,email,exhibitor_link\n"
      )

      // Array to store failed items
      const failedItems: string[] = []

      // Iterate through each exhibitor link
      for (const link of exhibitorLinks.slice(startIndex || 0, endIndex || exhibitorLinks.length)) {
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
              ? (document.querySelector(".CatalogExhibitorStrip-socialitem .cc2-icon-web") as HTMLAnchorElement).href ||
                ""
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

            const linkedin = getSocialLink(".CatalogExhibitorStrip-socialitem .cc2-icon-linkedin.CatalogRoundedButton")
            const facebook = getSocialLink(".CatalogExhibitorStrip-socialitem .cc2-icon-facebook.CatalogRoundedButton")
            const instagram = getSocialLink(
              ".CatalogExhibitorStrip-socialitem .cc2-icon-instagram.CatalogRoundedButton"
            )
            const twitter = getSocialLink(".CatalogExhibitorStrip-socialitem .cc2-icon-twitter.CatalogRoundedButton")

            const categoryLists = Array.from(
              document.querySelectorAll(".Section-content ul[class=CatalogActivityList]")
            )
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
              await page.goto(exhibitorData.website)
              let pageContent = await page.content()
              emails.push(...extractEmails(pageContent))

              // Check for a contact page
              const contactLink = await findContactAElement(page)

              if (contactLink) {
                await page.goto(contactLink)
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
          }","${uniqueEmails.join("; ")}","${link}"\n`
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

      // sleep for debugging
      // await sleep(5 * 60 * 1000)

      // Close the CSV file and the browser
      csvFile.end()
    }

    await browser.close()

    // Record the end time and calculate the runtime
    const endTime = Date.now()
    const runtimeInSeconds = (endTime - startTime) / 1000
    console.log(`\nScraper finished in ${runtimeInSeconds} seconds`)
  } catch (err: unknown) {
    if (err instanceof Error) {
      console.error("failed to keep scraper running: ", err)
      request.post(
        {
          url: simplepushUrl,
          body: querystring.stringify({
            key: "nathan123",
            title: "Scraper interrupted: " + err.name,
            msg: (err.message as string).slice(0, 200),
            event: "event",
          }),
        },
        function (error: any, response: any, body: any) {
          console.log("Simplepush info: ")
          console.log("error: ", error)
          console.log("response: ", response)
          console.log("body: ", body)
        }
      )
    }
  }
})()

async function findContactAElement(page: Page): Promise<string | undefined> {
  const contactElement = await page.evaluate(() => {
    const translationOfContact = [
      "kontakti",
      "contacte",
      "կապ",
      "kontakt",
      "əlaqə",
      "кантакт",
      "contact",
      "kontakt",
      "контакти",
      "kontakt",
      "επικοινωνία",
      "kontakt",
      "kontakt",
      "kontakt",
      "yhteystiedot",
      "contact",
      "კონტაქტი",
      "kontakt",
      "επικοινωνία",
      "kapcsolat",
      "hafa samband",
      "teagmháil",
      "contatti",
      "kontakt",
      "kontakti",
      "kontakt",
      "kontaktai",
      "contact",
      "kuntatt",
      "contacte",
      "contact",
      "kontakt",
      "contact",
      "контакт",
      "kontakt",
      "kontakt",
      "contactos",
      "contact",
      "контакты",
      "contatti",
      "контакт",
      "kontakt",
      "kontakt",
      "contacto",
      "kontakt",
      "kontakt",
      "iletişim",
      "контакти",
      "contact",
      "تماس",
      "اتصال",
      "contacto",
      "contacto",
      "contact",
      "যোগাযোগ",
      "contact",
      "contact",
      "contact",
      "འབྲེལ་བ་",
      "contacto",
      "contact",
      "contato",
      "hubungi",
      "contact",
      "contact",
      "ទំនាក់ទំនង",
      "contact",
      "contact",
      "contacto",
      "contact",
      "contact",
      "contacto",
      "联系",
      "contacto",
      "contact",
      "contact",
      "contact",
      "contacto",
      "contact",
      "contacto",
      "contact",
      "contact",
      "contacto",
      "kontaktu",
      "contacto",
      "اتصال",
      "contacto",
      "contacto",
      "ርክብ",
      "contact",
      "ግንኙነት",
      "contact",
      "contact",
      "contact",
      "contact",
      "contact",
      "contacto",
      "contact",
      "contacto",
      "contact",
      "kontak",
      "contacto",
      "संपर्क",
      "kontak",
      "تماس",
      "اتصال",
      "קשר",
      "contact",
      "連絡",
      "اتصال",
      "байланыс",
      "contact",
      "contact",
      "اتصال",
      "байланыш",
      "ຕິດຕໍ່",
      "اتصال",
      "contact",
      "contact",
      "اتصال",
      "fifandraisana",
      "contact",
      "hubungi",
      "ގުޅުން",
      "contact",
      "contact",
      "اتصال",
      "contact",
      "contacto",
      "contact",
      "اتصال",
      "contacto",
      "ဆက်သွယ်ရန်",
      "contact",
      "contact",
      "सम्पर्क",
      "contact",
      "contacto",
      "contact",
      "contact",
      "련락",
      "اتصال",
      "رابطہ",
      "contact",
      "contacto",
      "contact",
      "contacto",
      "contacto",
      "makipag-ugnayan",
      "اتصال",
      "contact",
      "contact",
      "contact",
      "fesoʻotaʻi",
      "contacto",
      "اتصال",
      "contact",
      "contact",
      "contact",
      "contact",
      "contact",
      "xiriir",
      "contact",
      "연락",
      "contact",
      "සම්බන්ධ වන්න",
      "اتصال",
      "contact",
      "اتصال",
      "聯絡",
      "тамос",
      "mawasiliano",
      "ติดต่อ",
      "contact",
      "fetu'utaki",
      "contact",
      "اتصال",
      "habarlaşmak",
      "contact",
      "contact",
      "اتصال",
      "contact",
      "contacto",
      "aloqa",
      "contact",
      "contacto",
      "liên hệ",
      "اتصال",
      "contact",
      "contact",
    ]

    const pageLinks = document.querySelectorAll("li a")
    const el = Array.from(pageLinks.values())
      .slice(0, 50)
      .find((el) => {
        const anchor = el as HTMLAnchorElement
        for (const contactWord of translationOfContact) {
          if (anchor.href.includes(contactWord)) {
            return anchor
          }
        }
      })
    return el ? (el as HTMLAnchorElement).href : el
  })
  return contactElement
}
