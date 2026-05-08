const axios = require('axios');
const cheerio = require('cheerio'); // For HTML parsing
const he = require('he'); // For HTML entity decoding
const xlsx = require('xlsx');

async function getExhibitorList(start = 0, rows = 30) {
  try {
    const response = await axios.get('https://www.prowein.com/vis-api/vis/v3/en/search', {
      params: {
        _start: start,
        _rows: rows,
        f_type: 'profile'
      },
      headers: {
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Connection': 'keep-alive',
        'Referer': `https://www.prowein.com/vis/v1/en/search?_query=&_start=${start - 1}&f_type=profile`, // Dynamic referer
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Mobile Safari/537.36',
        'X-Vis-Domain': 'www.prowein.com',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"'
      }
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching exhibitor list:", error);
    return null;
  }
}


async function getExhibitorDetails(id) {
  try {
    const response = await axios.get(`https://www.prowein.com/vis-api/vis/v1/en/exhibitors/${id}/slices/profile`, {
      headers: {
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://www.prowein.com/vis/v1/en/search?_query=&_start=3960&f_type=profile', // You might want to make this dynamic as well
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Mobile Safari/537.36',
        'X-Vis-Domain': 'www.prowein.com',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"'
      }
    });
    return response.data;
  } catch (error) {
    console.error(`Error fetching exhibitor details for ${id}:`, error);
    return null;
  }
}

function extractData(details) {
    if (!details) return null;

    const $ = cheerio.load(details.text || ''); // Load the HTML content

    const name = details.name;

    const description = he.decode($.text()).trim() || '';

    const email = details.email;
    const phone = details.phone?.phone; // Optional chaining for phone number
    const websiteLink = details.links?.find(link => link.type === 'link')?.link; // Find the website link

    const address = details.profileAddress?.address.join(', '); // Join address array
    const city = details.profileAddress?.city;
    const zip = details.profileAddress?.zip;
    const country = details.profileAddress?.country;

    const fullAddress = `${address}, ${city} ${zip}, ${country}`.replace(/,\s+/g, ', '); // Combine and clean up address parts

    return {
        name,
        description,
        email,
        phone,
        websiteLink,
        address,
        city,
        zip,
        country,
        fullAddress
    };
}


async function scrapeData(startPage = 0, numPages = 1) {
    const allExhibitorsData = [];

    for (let page = startPage; page < startPage + numPages; page++) {
        const exhibitorList = await getExhibitorList(page * 30); // 30 items per page
        if (!exhibitorList || !exhibitorList.docs) {
            console.error("Failed to fetch exhibitor list or empty result.");
            break; // Exit loop if there's an issue
        }

        for (const exhibitor of exhibitorList.docs) {
            const exhibitorId = exhibitor.id.split('=')[1]; // Extract ID
            const details = await getExhibitorDetails(exhibitorId);
            const extractedData = extractData(details);
            if(extractedData){
                allExhibitorsData.push(extractedData);
            }

            await new Promise(resolve => setTimeout(resolve, 500)); // Add a delay between requests
        }
    }
    return allExhibitorsData;
}


// Example usage:
async function main() {
    let scrapedData = [];
    const numPages = 133; // Number of pages to scrape
    for (let i = 0; i < numPages; i++) {
      console.log(`Scraped page ${i}...`);
      scrapedData.push(...(await scrapeData(i, 1))); 
      console.log(JSON.stringify(scrapedData, null, 2)); // Print the results
      console.log('Ammount of data: ', scrapedData.length);

      if (i === numPages - 1) break; 
      await new Promise(resolve => setTimeout(resolve, 30000)); 
    }

    // Create a new workbook and worksheet
    const workbook = xlsx.utils.book_new();
    const worksheet = xlsx.utils.json_to_sheet(scrapedData);

    // Add the worksheet to the workbook
    xlsx.utils.book_append_sheet(workbook, worksheet, 'Exhibitors');

    // Write the workbook to an XLSX file
    xlsx.writeFile(workbook, 'exhibitors_data.xlsx');
}

main();