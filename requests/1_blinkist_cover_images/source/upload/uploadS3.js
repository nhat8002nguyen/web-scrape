const AWS = require('aws-sdk');
const fs = require('fs');
const path = require('path');
const xlsx = require('xlsx');

require('dotenv').config();

const jsonFilePath = './public_urls.json';

const { google } = require('googleapis');
const range = 'Sheet1!A1:A';

async function writeToSheet(values) {
  const auth = new google.auth.GoogleAuth({
    keyFile: './credentials.json',
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
  });

  const sheets = google.sheets({ version: 'v4', auth });
  const spreadsheetId = '1oZHW8sY02JSL3IIZquTGJgrsQ3xn083GcvxQATVQNY8';

  const valueInputOption = 'USER_ENTERED';

  const resource = { values };

  try {
    const res = await sheets.spreadsheets.values.append({
      spreadsheetId,
      range,
      valueInputOption,
      resource
    });
    return res.data;  // Returns the response from the Sheets API.
  } catch (error) {
    console.error('Error writing to Google Sheet:', error);
  }
}

async function writeUrlsToSheet() {
  let jsonData = [];

  try {
    // Read existing data from the JSON file
    const existingData = fs.readFileSync(jsonFilePath, 'utf-8');
    jsonData = JSON.parse(existingData);
  } catch (readError) {
    console.error('Error reading JSON file:', readError);
    return;
  }

  if (jsonData.length === 0) {
    console.log('No URLs to write to Google Sheet.');
    return;
  }

  const urlsToWrite = jsonData.map(entry => [entry['Public URL']]);

  try {
    // Use the writeToSheet function to write the data to the Google Sheet
    await writeToSheet(urlsToWrite);
  } catch (error) {
    console.error('Error writing URLs to Google Sheet:', error);
  }
}

function uploadToS3(filePath) {
  const accessKeyId = 'a4880196fdd299cf0eee6db0f73c11a3';
  const secretAccessKey = '765671efdfb129e44b7f1d089e194d6fa172092929ed23009f1488853f48389c';
  const endpoint = 'https://761e7f63f330750cd2ad0e5d12d59fff.r2.cloudflarestorage.com/';
  const bucketName = 'happylife';
  const keyName = path.basename(filePath);  // Extract the filename from the path
  const publicUrlBase = 'https://delivery.happylife.ai/{keyName}';

  fs.writeFileSync(jsonFilePath, '[]');

  AWS.config.update({
    accessKeyId,
    secretAccessKey,
    endpoint,
    s3ForcePathStyle: true,
    signatureVersion: 'v4'
  });

  const s3 = new AWS.S3();

  const params = {
    Bucket: bucketName,
    Key: keyName,
    Body: fs.createReadStream(filePath),
    ContentType: 'image/jpeg',
    ACL: 'public-read'  // Make the uploaded file publicly readable
  };

  s3.upload(params, async (err, data) => {
    if (err) {
      console.error(`Error uploading file ${filePath}:`, err);
    } else {
      const publicUrl = publicUrlBase.replace('{keyName}', keyName);
      console.log(`File ${filePath} uploaded successfully. Public URL: ${publicUrl}`);

      // Read existing data from the JSON file
      let jsonData = [];
      try {
        const existingData = fs.readFileSync(jsonFilePath, 'utf-8');
        jsonData = JSON.parse(existingData);
      } catch (readError) {
        console.error('Error reading JSON file:', readError);
      }

      // Add the new public URL to the beginning of the existing data
      jsonData.unshift({ "Public URL": publicUrl });

      // Write the updated data back to the JSON file
      fs.writeFileSync(jsonFilePath, JSON.stringify(jsonData, null, 2));

      console.info("Successfully upload images:", data)
      try {
        // Use the writeToSheet function to write the data to the Google Sheet
        await writeToSheet([[publicUrl]]);
      } catch (error) {
        console.error('Error writing to Google Sheet:', error);
      }
    }
  });
}

// Set up your AWS S3 configuration
const s3 = new AWS.S3({
  accessKeyId: 'a4880196fdd299cf0eee6db0f73c11a3',
  secretAccessKey: '765671efdfb129e44b7f1d089e194d6fa172092929ed23009f1488853f48389c',
  endpoint: 'https://761e7f63f330750cd2ad0e5d12d59fff.r2.cloudflarestorage.com/',
  s3ForcePathStyle: true,
  signatureVersion: 'v4'
});

async function uploadToS3AndWriteToExcel(excelFilePath, imageFolderPath) {
  // Open the workbook
  const workbook = xlsx.readFile(excelFilePath);
  // Iterate through all images in the folder
  const imageFiles = fs.readdirSync(imageFolderPath);

  for (let file of imageFiles) {
    const filePath = path.join(imageFolderPath, file);
    const keyName = path.basename(filePath);
    const publicUrlBase = 'https://delivery.happylife.ai/{keyName}';

    // Upload to S3 and get the public URL
    const params = {
      Bucket: 'happylife',
      Key: keyName,
      Body: fs.createReadStream(filePath),
      ContentType: 'image/jpeg',
      ACL: 'public-read'
    };

    try {
      const data = await s3.upload(params).promise();
      const publicUrl = publicUrlBase.replace('{keyName}', keyName);
      console.log(`File uploaded successfully. Public URL: ${publicUrl}`);

      // Extract the index, book name, and author from the file name
      const [index, bookName, authorName] = keyName.split('_');
      // Assuming the sheet name or index is known and valid
      const sheetName = 'Sheet1';
      const sheet = workbook.Sheets[sheetName];

      // Assuming that the index refers to an Excel row number
      const cellAddress = `A${index}`; // Example for column A
      xlsx.utils.sheet_add_aoa(sheet, [[publicUrl]], { origin: cellAddress });

    } catch (error) {
      console.error(`Error uploading file ${filePath}`, error);
    }
  }

  // Finally, write the workbook out to the file
  xlsx.writeFile(workbook, excelFilePath);
}

// Example usage:
uploadToS3AndWriteToExcel(process.env.PROJECT_PATH + '/27-categories-books.xlsx', process.env.PROJECT_PATH + '/cover_images');
