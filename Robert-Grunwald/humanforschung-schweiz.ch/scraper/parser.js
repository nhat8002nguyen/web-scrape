'use strict';

const cheerio = require('cheerio');

// Whole-word institution markers (case-sensitive for abbreviations, case-insensitive via regex flag where needed)
const INSTITUTION_KEYWORDS_EXACT = [
  'AG', 'GmbH', 'Ltd', 'LLC', 'Inc', 'Inc.', 'Corp', 'Corp.',
  'A/S', 'N.V.', 'B.V.', 'S.A.', 'S.p.A.', 'SpA',
];

// Substrings that indicate institutional/org text when found anywhere in the value
const INSTITUTION_SUBSTRINGS = [
  'university', 'universität', 'université', 'università',
  'hospital', 'spital', 'klinik', 'clinic', 'clinique', 'kliniken',
  'department', 'abteilung', 'département',
  'institut', 'institute',
  'centre', 'center', 'zentrum',
  'foundation', 'stiftung',
  'association', 'verein',
  'pharma', 'medical', 'sciences',
  'corporation', 'corp.',
  'trials', 'research', 'laboratory', 'lab',
  'transparency', 'service', 'services',
  'inselspital', 'kantonsspital', 'stadtspital',
  'novartis', 'roche', 'nordisk', 'pfizer', 'bayer',
  'chuv', 'chuvspz',
  'oncology', 'oncologie',
  'therapeutics', 'biosciences', 'biotech', 'biopharmaceutical',
  'norce',
];

const TITLE_PREFIXES = new Set([
  'Dr.', 'Dr', 'Prof.', 'Prof', 'PD', 'MD', 'PhD', 'Ass.',
  'med.', 'rer.', 'nat.', 'phil.', 'habil.', 'dent.', 'sc.',
  'Dipl.', 'Dipl.-Psych.', 'Dipl.-Med.', 'Dipl.-Biol.',
  'MSc', 'BSc', 'MPH',
  // Gendered honorifics (German/French/English)
  'Herr', 'Frau', 'Mr', 'Mr.', 'Mrs', 'Mrs.', 'Ms', 'Ms.',
  // Latin conjunctions used in compound academic titles (e.g. "Dr. med. et phil.")
  'et',
]);

// Case-insensitive prefix check so capitalised or period-less variants like "Med" or "Nat" are stripped.
// Tries: exact, lowercase, lowercase+period (handles "Med" → "med."), uppercase+period.
function isTitlePrefix(word) {
  const lower = word.toLowerCase();
  return TITLE_PREFIXES.has(word) ||
         TITLE_PREFIXES.has(lower) ||
         TITLE_PREFIXES.has(lower + '.') ||
         TITLE_PREFIXES.has(word + '.');
}

// Lowercase-only articles / prepositions that appear in org names (surname particles like "Le", "Von" are capitalised so they pass)
const NON_NAME_WORDS = new Set(['für', 'fuer', 'de', 'la', 'le', 'les', 'van', 'von', 'und', 'and', 'of', 'for', 'di', 'del', 'della', 'des', 'du', 'soins', 'pour']);

function looksLikePersonName(text) {
  const cleaned = text.trim();

  // Explicit non-name phrases
  if (/^not available$/i.test(cleaned)) return false;
  if (/^n\/a$/i.test(cleaned)) return false;

  // Reject if contains digits
  if (/\d/.test(cleaned)) return false;

  // Reject if looks like email or URL
  if (/@|http|www\./.test(cleaned)) return false;

  // Reject if contains commas (address lines, multiple orgs)
  if (/,/.test(cleaned)) return false;

  // Reject if contains a semicolon or slash (multiple entries merged)
  if (/[;/]/.test(cleaned)) return false;

  const lower = cleaned.toLowerCase();

  // Reject if any institution substring appears anywhere (handles compound words like Universitätsklinik)
  for (const sub of INSTITUTION_SUBSTRINGS) {
    if (lower.includes(sub)) return false;
  }

  const words = cleaned.split(/\s+/).filter(Boolean);

  // Reject if any word is an exact institution abbreviation
  for (const kw of INSTITUTION_KEYWORDS_EXACT) {
    if (words.includes(kw)) return false;
  }

  // Strip title prefixes (case-insensitive) to get the actual name words
  const nameWords = words.filter(w => !isTitlePrefix(w));
  if (nameWords.length < 2) return false;

  // Reject if any name word is a lowercase article/preposition (indicates org phrase).
  // Capitalised particles like "Le" or "Von" are valid surname components.
  for (const w of nameWords) {
    if (NON_NAME_WORDS.has(w) && w === w.toLowerCase()) return false;
  }

  // Must have 2–4 name words after stripping titles (allows first + middle initial + last, or hyphenated names)
  if (nameWords.length > 4) return false;

  // Each name word should start with a capital letter (personal names always capitalised)
  const allCapitalised = nameWords.every(w => /^[A-ZÄÖÜÀÂÉÈÊËÎÏÔÙÛÜÆŒ]/.test(w));
  if (!allCapitalised) return false;

  // Any all-uppercase token (2+ letters) is an institution abbreviation, not a name word
  if (nameWords.some(w => /^[A-Z]{2,}$/.test(w))) return false;

  return true;
}

// Capitalised surname particles that start a compound last name (e.g. "Le Rhun", "Van Berg", "De Winter")
const SURNAME_PARTICLES = new Set([
  'Le', 'La', 'Les', 'Du', 'Des',        // French
  'De', 'Den', 'Der', 'Van', 'Vom',       // Dutch / Flemish / German
  'Von', 'Zu', 'Zur', 'Zum',             // German
  'Di', 'Del', 'Della', 'Degli', 'Dei', 'Da', // Italian
  'Al', 'El',                             // Arabic / Spanish
]);

function splitName(text) {
  const words = text.trim().split(/\s+/).filter(Boolean);
  // Remove title prefixes (case-insensitive) — only the given/family names remain
  const nameWords = words.filter(w => !isTitlePrefix(w));
  if (nameWords.length < 2) return { firstName: '', lastName: '' };

  // Detect a surname particle between the first given-name word and the last word.
  // The surname starts at the first particle found (e.g. "Emilie Le Rhun" → last = "Le Rhun").
  let surnameStart = nameWords.length - 1; // default: last word only
  for (let i = 1; i < nameWords.length - 1; i++) {
    if (SURNAME_PARTICLES.has(nameWords[i])) {
      surnameStart = i;
      break;
    }
  }

  const lastName = nameWords.slice(surnameStart).join(' ');
  const firstName = nameWords.slice(0, surnameStart).join(' ');
  return { firstName, lastName };
}

// Tries progressively relaxed variants of a text part to find a person name inside it.
// Only used for 'Contact Person Switzerland' blocks, so conservative fallbacks are safe.
function extractNameFromPart(text) {
  if (looksLikePersonName(text)) return text;

  // "Franzisca Rusca (AbbVie Medical Information)" → try before first parenthesis
  const beforeParen = text.split('(')[0].trim();
  if (beforeParen && beforeParen !== text && looksLikePersonName(beforeParen)) return beforeParen;

  // "Simon Häfliger – Inselspital Bern" → try before em-dash / en-dash
  const beforeDash = text.split(/\s*[–—]\s*/)[0].trim();
  if (beforeDash && beforeDash !== text && looksLikePersonName(beforeDash)) return beforeDash;

  // "Prof. Dr. med. Markus Denzinger, MHBA" → try before first comma
  const beforeComma = text.split(',')[0].trim();
  if (beforeComma && beforeComma !== text && looksLikePersonName(beforeComma)) return beforeComma;

  // "SAKK, Céline Rüegsegger" or "SAKK, Dr. Jana Musilova" → try segment after first comma
  const commaIdx = text.indexOf(',');
  if (commaIdx >= 0) {
    const afterFirstComma = text.slice(commaIdx + 1).split(',')[0].trim();
    if (afterFirstComma && looksLikePersonName(afterFirstComma)) return afterFirstComma;
  }

  return '';
}

function decodeEmail($, anchorEl) {
  // Clone span inside anchor, remove hidden <i> elements, then read text
  const span = $(anchorEl).find('span').first();
  if (!span.length) return '';
  const cloned = span.clone();
  cloned.find('i.hidden').remove();
  return cloned.text().trim();
}

function findContactBoxes($) {
  let contactContainer = null;

  $('h2').each((_, el) => {
    if ($(el).text().trim() !== 'Contact') return;

    // The contact boxes are siblings or descendants of the parent row.
    contactContainer = $(el).closest('div.row, section, div').filter((_, p) =>
      $(p).find('.contact-box').length > 0
    ).first();

    if (!contactContainer.length) {
      contactContainer = $(el).parent();
    }
  });

  if (contactContainer && contactContainer.length) {
    const sectionBoxes = contactContainer.find('.contact-box');
    if (sectionBoxes.length) return sectionBoxes;
  }

  // Some study pages expose contact boxes without a "Contact" heading.
  return $('.contact-box');
}

function extractContactBlocks($, studyUrl) {
  const rows = [];

  // Study metadata
  const studyIdParts = [];
  $('.study-ids span').each((_, el) => {
    const txt = $(el).text().trim();
    if (txt && txt !== '|') studyIdParts.push(txt);
  });
  const studyId = studyIdParts.join(' | ');
  const studyTitle = $('h1.study-detail-title').text().trim();

  const contactBoxes = findContactBoxes($);
  if (!contactBoxes.length) return rows;

  contactBoxes.each((_, box) => {
    const $box = $(box);

    const blockTitle = $box.find('h3').first().text().trim();

    // Email from obfuscated anchor
    const emailAnchor = $box.find('a[data-mailto-token]').first();
    const email = emailAnchor.length ? decodeEmail($, emailAnchor) : '';

    // Source tag — pick first non-empty p.data-source (malformed HTML can produce empty leading sibling)
    let sourceTag = '';
    $box.find('p.data-source').each((_, p) => {
      const txt = $(p).text().trim();
      if (txt && !sourceTag) sourceTag = txt;
    });

    // Collect remaining <p> texts (not source tag, not empty, not "not available")
    const textParts = [];
    $box.find('p').each((_, p) => {
      if ($(p).hasClass('data-source')) return;
      const txt = $(p).text().trim();
      if (txt && !/^not available$/i.test(txt)) textParts.push(txt);
    });

    // Raw contact text: capture all visible parts BEFORE any extraction removes the phone
    const rawContactText = textParts.join('\n');

    // Phone: first text part matching a phone pattern
    let phone = '';
    const phoneIndex = textParts.findIndex(t => /[+\d][\d\s\-().]{5,}/.test(t));
    if (phoneIndex !== -1) {
      phone = textParts[phoneIndex];
      textParts.splice(phoneIndex, 1);
    }

    // Name / institution split depends on block title.
    // Only "Contact Person Switzerland" blocks are expected to contain a real person name.
    // All other block types (General Information, Scientific Information, …) leave name
    // fields blank and route everything into institutionName.
    let firstName = '';
    let lastName = '';
    let institutionName = '';

    if (blockTitle === 'Contact Person Switzerland') {
      let nameCandidate = '';
      let nameSourcePart = '';
      for (const t of textParts) {
        const candidate = extractNameFromPart(t);
        if (candidate) { nameCandidate = candidate; nameSourcePart = t; break; }
      }
      if (nameCandidate) {
        const split = splitName(nameCandidate);
        firstName = split.firstName;
        lastName  = split.lastName;
      }
      // Institution: all parts that are not the identified person name part
      institutionName = textParts
        .filter(t => t !== nameSourcePart && !looksLikePersonName(t))
        .map(t => t.split('\n\n')[0].trim())
        .filter(Boolean)
        .join('\n');
    } else {
      institutionName = textParts
        .map(t => t.split('\n\n')[0].trim())
        .filter(Boolean)
        .join('\n');
    }

    // Only include this block if there is at least one useful field
    const hasUsefulData = rawContactText || email || phone || institutionName || sourceTag;
    if (!hasUsefulData) return;

    rows.push({
      studyId,
      studyTitle,
      studyUrl,
      blockTitle,
      rawContactText,
      firstName,
      lastName,
      email,
      phone,
      institutionName,
      sourceTag,
    });
  });

  return rows;
}

function parseDetailPage(html, studyUrl) {
  const $ = cheerio.load(html);
  return extractContactBlocks($, studyUrl);
}

module.exports = { parseDetailPage };
