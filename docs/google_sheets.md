# Google Sheets Integration (Users + Progress + Feedback)

Language Coach can optionally log user snapshots (name/email/progress) and feedback messages to your Google Spreadsheet.

This integration uses a simple **Google Apps Script Web App** webhook, so you don't need extra Python packages or OAuth.

## 1) Create the Apps Script webhook

1. Open your spreadsheet in Google Sheets.
2. Go to **Extensions → Apps Script**.
3. Delete any existing code and paste the script below.
4. Go to **Project Settings → Script properties** and add:
   - Key: `TOKEN`
   - Value: *(any long random string; keep it secret)*
5. Click **Deploy → New deployment → Web app**
   - Execute as: **Me**
   - Who has access: **Anyone** (or “Anyone with the link”)
6. Copy the **Web app URL** (you’ll use it in env vars).

## 2) Apps Script code (paste into Apps Script)

```javascript
const USERS_SHEET = 'LanguageCoach_Users';
const EVENTS_SHEET = 'LanguageCoach_Events';
const FEEDBACK_SHEET = 'LanguageCoach_Feedback';

const USERS_HEADERS = [
  'updated_at','user_id','name','email','last_login',
  'last_event','last_lang','last_lesson_id','last_score',
  'french_completed','french_total','french_percent',
  'spanish_completed','spanish_total','spanish_percent',
  'xp_today','reviews_today','correct_today','wrong_today',
  'page'
];

const EVENTS_HEADERS = [
  'timestamp','event','user_id','name','email',
  'language','lesson_id','score',
  'category','message','page',
  'french_completed','french_total','french_percent',
  'spanish_completed','spanish_total','spanish_percent',
  'xp_today','reviews_today','correct_today','wrong_today'
];

const FEEDBACK_HEADERS = [
  'timestamp','user_id','name','email','category','language','message','page'
];

function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function ensureHeader(sheet, headers) {
  const lastRow = sheet.getLastRow();
  if (lastRow === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    sheet.setFrozenRows(1);
    return;
  }

  const existing = sheet.getRange(1, 1, 1, Math.max(headers.length, sheet.getLastColumn())).getValues()[0];
  const hasAny = existing.some(v => String(v || '').trim());
  if (!hasAny) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
}

function headersForSheet(name) {
  if (name === USERS_SHEET) return USERS_HEADERS;
  if (name === FEEDBACK_SHEET) return FEEDBACK_HEADERS;
  return EVENTS_HEADERS;
}

function appendRow(sheet, headers, rowObj) {
  const values = headers.map(h => (rowObj && rowObj[h] != null) ? rowObj[h] : '');
  sheet.appendRow(values);
}

function upsertUser(sheet, headers, rowObj) {
  const email = String((rowObj && rowObj.email) || '').trim().toLowerCase();
  if (!email) return false;

  const emailCol = headers.indexOf('email') + 1;
  if (emailCol <= 0) return false;

  const lastRow = sheet.getLastRow();
  let targetRow = -1;
  if (lastRow >= 2) {
    const values = sheet.getRange(2, emailCol, lastRow - 1, 1).getValues();
    for (let i = 0; i < values.length; i++) {
      const v = String(values[i][0] || '').trim().toLowerCase();
      if (v === email) { targetRow = i + 2; break; }
    }
  }

  const rowValues = headers.map(h => (rowObj && rowObj[h] != null) ? rowObj[h] : '');
  if (targetRow === -1) sheet.appendRow(rowValues);
  else sheet.getRange(targetRow, 1, 1, headers.length).setValues([rowValues]);
  return true;
}

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const token = PropertiesService.getScriptProperties().getProperty('TOKEN') || '';
    if (token && body.token !== token) return jsonOut({ok:false, error:'unauthorized'});

    const action = String(body.action || 'append_row');
    const sheetName = String(body.sheet || '').trim();
    const row = body.row || {};
    if (!sheetName) return jsonOut({ok:false, error:'missing_sheet'});

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);
    const headers = headersForSheet(sheetName);
    ensureHeader(sheet, headers);

    if (action === 'upsert_user') {
      const ok = upsertUser(sheet, headers, row);
      return jsonOut({ok: ok});
    }

    appendRow(sheet, headers, row);
    return jsonOut({ok:true});
  } catch (err) {
    return jsonOut({ok:false, error:String(err)});
  }
}
```

## 3) Configure Language Coach (env vars)

Set these environment variables where you run the Flask app:

- `SHEETS_WEBHOOK_URL` = *(your Apps Script “Web app URL”)*
- `SHEETS_WEBHOOK_TOKEN` = *(the same TOKEN you set in Apps Script properties)*

Optional (defaults shown):

- `SHEETS_USERS_SHEET=LanguageCoach_Users`
- `SHEETS_EVENTS_SHEET=LanguageCoach_Events`
- `SHEETS_FEEDBACK_SHEET=LanguageCoach_Feedback`
- `SHEETS_WEBHOOK_TIMEOUT=3.0`

Restart the server after setting env vars.

## 4) What gets logged

- **Users sheet**: upsert by email on login + lesson completion (latest snapshot only).
- **Events sheet**: append rows for login, lesson completion, feedback.
- **Feedback sheet**: append rows for feedback messages.

