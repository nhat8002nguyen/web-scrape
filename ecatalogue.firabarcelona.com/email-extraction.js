const xlsx = require('xlsx');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');

// Read the Excel file
const workbook = xlsx.readFile('exhibitor_data_all.xlsx');
const sheetName = workbook.SheetNames[0];
const worksheet = workbook.Sheets[sheetName];

// Convert the worksheet to JSON
const data = xlsx.utils.sheet_to_json(worksheet);

// Function to extract email from a website
const extractEmail = async (url) => {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;
    const email = $('body').text().match(emailRegex);
    return email ? email[0] : '';
  } catch (error) {
    console.error(`Error fetching ${url}:`, error.message);
    return '';
  }
};

// Process each row and extract emails
const processRows = async () => {
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    if (row.Website) {
      const email = await extractEmail(row.Website);
      console.log(`Extracted email for ${row.Website}:`, email);
      row.Email = email;
    } else {
      row.Email = '';
    }
  }

  // Write the updated data to a new Excel file
  const newWorksheet = xlsx.utils.json_to_sheet(data);
  const newWorkbook = xlsx.utils.book_new();
  xlsx.utils.book_append_sheet(newWorkbook, newWorksheet, sheetName);
  xlsx.writeFile(newWorkbook, 'exhibitor_data_with_emails.xlsx');
};

processRows();