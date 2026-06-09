/************************************************************************
 * COACH ABOOD LLC — CLIENT TEMPLATE GENERATOR  (v8)
 *
 * v8 fixes the Weight tab: the new sheet is created with a day-first (en_GB)
 * locale and the "Week #" / averages formulas no longer use DATEVALUE (which
 * mis-parsed dd/MM/yyyy under a US locale and produced wrong weeks then #VALUE!).
 * Dates render dd/MM/yyyy everywhere (Weight, Nutrition, Week-tab Date columns).
 *
 * v7 adds a WEB APP entry point so the Flask dashboard can generate a client
 * file automatically (fill master tabs -> POST here -> get the new sheet URL
 * back -> auto-register). The menu version (Coach Tools -> Generate Client
 * Template) is unchanged.
 *
 * DEPLOY AS WEB APP:
 *   1. Set WEBAPP_SECRET below to a long random string (keep it private).
 *   2. Deploy -> New deployment -> type "Web app".
 *        Execute as:  Me (the master sheet owner)
 *        Who has access:  Anyone
 *   3. Copy the /exec URL. Put it + the secret in the dashboard's .env:
 *        TEMPLATE_WEBAPP_URL=https://script.google.com/macros/s/XXXX/exec
 *        TEMPLATE_WEBAPP_SECRET=<the same secret>
 *   4. Re-deploy after any code change (Manage deployments -> Edit -> New version).
 *
 * The web app reads the SAME master admin tabs the Flask wizard fills in, so the
 * flow is: Flask writes ⚙ tabs via Sheets API -> Flask POSTs here -> this runs
 * generation as the sheet owner -> returns {ok, url, id, fileName, sharedWith}.
 ************************************************************************/

// CHANGE THIS to a long random string, and set the SAME value as the
// TEMPLATE_WEBAPP_SECRET environment variable on the dashboard host (Render).
const WEBAPP_SECRET = 'CHANGE_ME_to_a_long_random_secret';

// The dashboard's Google service-account email. Every generated client sheet is
// auto-shared with it so the hosted dashboard can read the new sheet. Find it in
// your service-account JSON as "client_email". Leave '' to share manually.
const SERVICE_ACCOUNT_EMAIL = '';

const T_INFO    = '⚙ Client Info';
const T_PROGRAM = '⚙ Program Builder';
const T_WEEKRIR = '⚙ Week & RIR';
const T_TARGETS = '⚙ Targets';

const NAVY       = '#1F3A5F';
const NAVY_LT    = '#2E5077';
const GRAY_HD    = '#D5DBDB';
const ROW_ALT    = '#F4F6F7';
const INPUT      = '#FFFDE7';
const RIRCOL     = '#EAF2F8';
const WHITE      = '#FFFFFF';
const MUTED      = '#566573';
const BORDER_CLR = '#BDC3C7';
const BS         = SpreadsheetApp.BorderStyle.SOLID;

const DAY_COLORS = {
  Push:  '#C0392B',
  Pull:  '#2471A3',
  Legs:  '#1E8449',
  Upper: '#6C3483',
  Lower: '#117A65'
};

// ---- Reps normalizer ----
function normalizeReps(val) {
  return String(val).trim()
    .replace(/\s*\/\s*/g, ', ')
    .replace(/(\d)\s*-\s*(\d)/g, '$1, $2')
    .replace(/\s*,\s*/g, ', ');
}

// ---- Menu ----
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Coach Tools')
    .addItem('Generate Client Template', 'generateClientTemplate')
    .addSeparator()
    .addItem('Run First-Time Setup (check)', 'firstTimeSetup')
    .addToUi();
}

function firstTimeSetup() {
  const ss      = SpreadsheetApp.getActiveSpreadsheet();
  const need    = [T_INFO, T_PROGRAM, T_WEEKRIR, T_TARGETS];
  const missing = need.filter(n => !ss.getSheetByName(n));
  const ui      = SpreadsheetApp.getUi();
  if (missing.length) { ui.alert('Missing admin tabs: ' + missing.join(', ')); return; }
  ui.alert('Setup OK. All admin tabs found. You can now use Generate Client Template.');
}

// ====================================================================
//  WEB APP ENTRY POINTS (called by the Flask dashboard)
// ====================================================================
function doPost(e) { return handleWebRequest_(e); }
function doGet(e)  { return handleWebRequest_(e); }

function handleWebRequest_(e) {
  try {
    var params = {};
    if (e && e.postData && e.postData.contents) {
      try { params = JSON.parse(e.postData.contents); } catch (err) { params = {}; }
    }
    // Allow secret via JSON body or query string.
    var secret = params.secret || (e && e.parameter && e.parameter.secret) || '';
    if (secret !== WEBAPP_SECRET) {
      return jsonOut_({ ok: false, error: 'Unauthorized (bad or missing secret).' });
    }

    var cfg = readConfig();              // reads the master ⚙ admin tabs
    var res = generateFromConfig_(cfg);  // builds the new client file (headless)
    return jsonOut_({
      ok: true,
      url: res.dest.getUrl(),
      id: res.dest.getId(),
      fileName: res.fileName,
      sharedWith: res.sharedWith
    });
  } catch (err) {
    return jsonOut_({ ok: false, error: String(err && err.message ? err.message : err) });
  }
}

function jsonOut_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ---- Read all config in one pass (one getValues() per sheet) ----
function readConfig() {
  const ss          = SpreadsheetApp.getActiveSpreadsheet();
  const infoVals    = ss.getSheetByName(T_INFO).getRange('B3:B10').getValues();
  const weekVals    = ss.getSheetByName(T_WEEKRIR).getRange('A4:B100').getValues();
  const pb          = ss.getSheetByName(T_PROGRAM);
  const schedVals   = pb.getRange('B5:C11').getValues();
  const exVals      = pb.getRange('A15:F300').getValues();
  const targetVals  = ss.getSheetByName(T_TARGETS).getRange('B2:B6').getValues();

  const info = infoVals.map(r => r[0]);
  const cfg  = {
    name:    String(info[0] || '').trim(),
    email:   String(info[1] || '').trim(),
    program: String(info[2] || '').trim(),
    goal:    String(info[3] || '').trim(),
    start:   info[4],
    unit:    String(info[5] || 'kg').trim(),
    plan:    info[6],
    billing: info[7]
  };

  if (!cfg.name || cfg.name.toLowerCase().startsWith('enter'))
    throw new Error('Enter a Client Name in the "' + T_INFO + '" tab first.');
  if (!(cfg.start instanceof Date) || isNaN(cfg.start.getTime()))
    throw new Error('Program Start Date must be a valid date — click the cell and use the date picker.');

  cfg.weeks = weekVals
    .filter(r => r[0] !== '' && r[0] !== null && String(r[0]).trim() !== '')
    .map(r => ({ week: Number(r[0]), rir: Number(r[1]) }));
  if (!cfg.weeks.length) throw new Error('No weeks found in "' + T_WEEKRIR + '".');

  cfg.schedule = schedVals
    .map(r => ({ day: String(r[0]).trim(), type: String(r[1]).trim() }))
    .filter(r => r.day !== '');

  const exByType = {};
  exVals
    .filter(r => String(r[0]).trim() !== '' && String(r[1]).trim() !== '')
    .forEach(r => {
      const t = String(r[0]).trim();
      if (!exByType[t]) exByType[t] = [];
      exByType[t].push({
        ex:    String(r[1]).trim(),
        sets:  String(r[2]).trim(),
        reps:  normalizeReps(r[3]),
        notes: String(r[4]).trim(),
        link:  String(r[5]).trim()
      });
    });
  cfg.exByType  = exByType;
  cfg.targets   = targetVals.map(r => r[0]);
  return cfg;
}

// ---- Core generation (headless — no UI). Returns {dest, fileName, sharedWith} ----
function generateFromConfig_(cfg) {
  const fname = cfg.name + ' — Coach Abood LLC';
  const dest  = SpreadsheetApp.create(fname);

  // Day-first locale so dd/MM/yyyy is native everywhere — typed dates, DATEVALUE,
  // and TEXT all read day-first, matching the dashboard's convention. Without
  // this the sheet defaults to US (month-first) and date math goes wrong.
  dest.setSpreadsheetLocale('en_GB');

  buildWeightTab(dest, cfg);
  cfg.weeks.forEach(w => buildWeekTab(dest, cfg, w.week, w.rir));
  buildNutritionTab(dest, cfg);

  const s1 = dest.getSheetByName('Sheet1');
  if (s1) dest.deleteSheet(s1);

  createClientNamedRanges(dest);
  SpreadsheetApp.flush();

  // Share with the dashboard's service account so the hosted app can read it.
  if (SERVICE_ACCOUNT_EMAIL) {
    try { dest.addEditor(SERVICE_ACCOUNT_EMAIL); }
    catch (e) { /* non-fatal: the coach can share manually if this fails */ }
  }

  let sharedWith = '';
  if (cfg.email) {
    try { dest.addEditor(cfg.email); sharedWith = cfg.email; }
    catch (e) { sharedWith = 'ERROR: ' + e.message; }
  }
  return { dest: dest, fileName: fname, sharedWith: sharedWith };
}

// ---- Main (menu-driven, with UI alerts) ----
function generateClientTemplate() {
  const ui = SpreadsheetApp.getUi();
  let cfg;
  try { cfg = readConfig(); }
  catch (e) { ui.alert('Error: ' + e.message); return; }

  const res = generateFromConfig_(cfg);
  const shareMsg = res.sharedWith
    ? (res.sharedWith.indexOf('ERROR') === 0
        ? '⚠️ Could not auto-share. Share manually with ' + cfg.email + '.\n' + res.sharedWith
        : '✅ Shared with ' + res.sharedWith + ' as Editor.')
    : '⚠️ No client email entered — share the file manually from Google Drive.';

  ui.alert('Done!\n\n' + res.fileName + '\n\n' + shareMsg + '\n\n' + res.dest.getUrl());
}

// ---- Weight tab ----
function buildWeightTab(dest, cfg) {
  const sh      = dest.insertSheet('Weight');
  const n       = 140;
  const lastRow = n + 1;
  const lastCol = 11;

  sh.setHiddenGridlines(true);

  sh.getRange(1, 1, 1, lastCol)
    .setValues([[
      'Date', 'Weight (' + cfg.unit + ')', 'Day Δ', '7-Day Avg', 'Weekly Avg',
      'Week #', 'Notes', 'Steps', 'Total Steps', 'Calories', 'Total Calories'
    ]])
    .setFontWeight('bold').setFontColor(WHITE)
    .setBackground(NAVY).setHorizontalAlignment('center');

  const last = n + 1;  // last data row (rows 2..141 for n=140)

  // Day Δ — today minus yesterday; blank on the first row or any gap.
  sh.getRange('C1').setFormula(
    '={"Day Δ"; ""; ARRAYFORMULA(IF((B3:B' + last + '="")+(B2:B' + (last-1) + '=""),"",B3:B' + last + '-B2:B' + (last-1) + '))}'
  );
  // 7-Day Avg — trailing 7-day average of logged weights (named range WeightMA7).
  // BYROW + AVERAGEIFS over the date window; robust and ignores blank days.
  sh.getRange('D1').setFormula(
    '={"7-Day Avg"; BYROW(SEQUENCE(' + n + ',1,2),LAMBDA(r,IF(INDEX(B:B,r)="","",IFERROR(AVERAGEIFS(B$2:B$' + last + ',A$2:A$' + last + ',">="&INDEX(A:A,r)-6,A$2:A$' + last + ',"<="&INDEX(A:A,r)),""))))}'
  );
  sh.getRange('E1').setFormula(
    '={"Weekly Avg"; BYROW(F2:F' + last + ',LAMBDA(f,IF(f="","",IFERROR(AVERAGEIF(F$2:F$' + last + ',f,B$2:B$' + last + '),""))))}'
  );
  // Week # — column A holds real dates, so subtract directly. (DATEVALUE was the
  // old bug: it re-parsed the dd/MM/yyyy text under a US locale -> wrong weeks.)
  sh.getRange('F1').setFormula(
    '={"Week #"; ARRAYFORMULA(IF(A2:A' + last + '="","",INT((A2:A' + last + '-A$2)/7)+1))}'
  );

  const start    = cfg.start;
  const dateVals = [];
  for (let i = 0; i < n; i++)
    dateVals.push([new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)]);
  sh.getRange(2, 1, n, 1)
    .setValues(dateVals)
    .setNumberFormat('dd/MM/yyyy')
    .setHorizontalAlignment('center');

  sh.getRange(2, 2, n, 1).setBackground(INPUT);
  sh.getRange(2, 7, n, 1).setBackground(INPUT);
  sh.getRange(2, 8, n, 1).setBackground(INPUT);
  sh.getRange(2, 10, n, 1).setBackground(INPUT);

  [110, 100, 80, 110, 110, 80, 200, 90, 110, 90, 120]
    .forEach((w, i) => sh.setColumnWidth(i + 1, w));

  sh.setFrozenRows(1);

  sh.getRange(1, 1, lastRow, lastCol)
    .setBorder(true, true, true, true, true, true, BORDER_CLR, BS);

  sh.getRange(2, 2, n, 1).setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireNumberBetween(20, 300).setAllowInvalid(false)
      .setHelpText('Enter weight in ' + cfg.unit + ' (20–300).').build()
  );
}

// ---- Week tab ----
function buildWeekTab(dest, cfg, week, rir) {
  const sh        = dest.insertSheet('Week ' + week);
  const totalCols = 11;
  let r           = 1;

  sh.setHiddenGridlines(true);

  sh.getRange(r, 1, 1, totalCols).merge()
    .setValue('WEEK ' + week)
    .setFontWeight('bold').setFontSize(20)
    .setFontColor(WHITE).setBackground(NAVY).setHorizontalAlignment('center');
  r++;

  sh.getRange(r, 1, 1, totalCols).merge()
    .setValue("This week's target: RIR " + rir +
              "  —  stop each set when you could still do about " + rir + " more rep(s).")
    .setFontColor(WHITE).setBackground(NAVY_LT)
    .setHorizontalAlignment('center').setFontStyle('italic');
  r += 2;

  const heads = [
    'Exercise', 'Target Sets', 'Target Reps', 'Target RIR',
    'Coach Notes', 'Tutorial', 'Date', 'Weight Used', 'Sets Done', 'Reps Done', 'Client Notes'
  ];

  cfg.schedule.forEach(s => {
    const type = s.type;
    if (!type) return;
    const exs = cfg.exByType[type] || [];
    if (!exs.length) return;

    const color      = DAY_COLORS[type] || NAVY;
    const blockStart = r;

    sh.getRange(r, 1, 1, totalCols).merge()
      .setValue(type.toUpperCase() + '  —  ' + s.day)
      .setFontWeight('bold').setFontSize(13)
      .setFontColor(WHITE).setBackground(color);
    r++;

    sh.getRange(r, 1, 1, totalCols)
      .setValues([heads])
      .setFontWeight('bold').setBackground(GRAY_HD).setWrap(true);
    r++;

    const dataStart = r;
    const numEx     = exs.length;

    const colsAE = exs.map(e => [e.ex, e.sets, e.reps, rir, e.notes]);
    sh.getRange(dataStart, 1, numEx, 5).setValues(colsAE);

    const colsGK = exs.map(() => ['', '', '', '', '']);
    sh.getRange(dataStart, 7, numEx, 5).setValues(colsGK);

    const evenRowNums = exs.map((_, i) => dataStart + i).filter((_, i) => i % 2 === 0);
    const oddRowNums  = exs.map((_, i) => dataStart + i).filter((_, i) => i % 2 !== 0);

    evenRowNums.forEach(row => {
      sh.getRange(row, 1, 1, 6).setBackground(WHITE);
      sh.getRange(row, 11, 1, 1).setBackground(WHITE);
    });
    oddRowNums.forEach(row => {
      sh.getRange(row, 1, 1, 6).setBackground(ROW_ALT);
      sh.getRange(row, 11, 1, 1).setBackground(ROW_ALT);
    });

    sh.getRange(dataStart, 2, numEx, 1).setHorizontalAlignment('center');
    sh.getRange(dataStart, 3, numEx, 1).setNumberFormat('@').setHorizontalAlignment('center');
    sh.getRange(dataStart, 4, numEx, 1).setBackground(RIRCOL).setFontWeight('bold').setHorizontalAlignment('center');
    sh.getRange(dataStart, 5, numEx, 1).setFontColor(MUTED).setWrap(true);
    sh.getRange(dataStart, 6, numEx, 1).setHorizontalAlignment('center');
    sh.getRange(dataStart, 7, numEx, 4).setBackground(INPUT).setHorizontalAlignment('center');
    sh.getRange(dataStart, 7, numEx, 1).setNumberFormat('dd/MM/yyyy');  // Date col
    sh.getRange(dataStart, 11, numEx, 1).setWrap(true);

    exs.forEach((e, i) => {
      const cell = sh.getRange(dataStart + i, 6);
      if (e.link && (e.link.startsWith('http://') || e.link.startsWith('https://'))) {
        cell.setFormula('=HYPERLINK("' + e.link + '","▶ Watch")').setFontColor('#2471A3');
      } else if (e.link) {
        cell.setValue(e.link);
      }
    });

    sh.getRange(blockStart, 1, r - blockStart + numEx, totalCols)
      .setBorder(true, true, true, true, true, true, BORDER_CLR, BS);

    r += numEx + 1;
  });

  [210, 95, 105, 100, 260, 120, 105, 110, 100, 100, 200]
    .forEach((w, i) => sh.setColumnWidth(i + 1, w));

  sh.setFrozenRows(2);
}

// ---- Nutrition tab ----
function buildNutritionTab(dest, cfg) {
  const sh = dest.insertSheet('Nutrition');
  sh.setHiddenGridlines(true);

  sh.getRange('A1:G1').merge()
    .setValue('DAILY NUTRITION')
    .setFontWeight('bold').setFontSize(18)
    .setFontColor(WHITE).setBackground(NAVY).setHorizontalAlignment('center');

  sh.getRange('A2').setValue('Date:').setFontWeight('bold').setHorizontalAlignment('right');
  sh.getRange('B2').setBackground(INPUT).setNumberFormat('dd/MM/yyyy');

  sh.getRange(3, 1, 1, 7)
    .setValues([['Food', 'Calories', 'Protein (g)', 'Carbs (g)', 'Fat (g)', 'Fiber (g)', 'Amount']])
    .setFontWeight('bold').setBackground(GRAY_HD);

  [
    ['BREAKFAST', '#E8F5E9', '#1B5E20', 4, 7],
    ['LUNCH',     '#E3F2FD', '#0D47A1', 12, 7],
    ['DINNER',    '#FFF3E0', '#E65100', 20, 7],
    ['SNACKS',    '#F3E5F5', '#4A148C', 28, 5]
  ].forEach(([name, bg, fg, start, nrows]) => {
    sh.getRange(start - 1, 1, 1, 7).merge()
      .setValue('▶ ' + name).setFontWeight('bold').setBackground(bg).setFontColor(fg);
    sh.getRange(start, 1, nrows, 6).setBackground(INPUT);
  });

  sh.getRange('A34').setValue('DAILY TOTAL').setFontWeight('bold').setFontColor(WHITE).setBackground(NAVY);
  ['B','C','D','E','F'].forEach(c => {
    sh.getRange(c + '34')
      .setFormula('=SUM(' + c + '4:' + c + '10,' + c + '12:' + c + '18,' + c + '20:' + c + '26,' + c + '28:' + c + '32)')
      .setFontWeight('bold').setFontColor(WHITE).setBackground(NAVY);
  });
  sh.getRange('G34').setBackground(NAVY);

  sh.getRange('A35').setValue('TARGET').setFontWeight('bold').setBackground(ROW_ALT);
  sh.getRange(35, 2, 1, 5).setValues([cfg.targets]).setBackground(ROW_ALT);
  sh.getRange('G35').setBackground(ROW_ALT);

  sh.getRange('A36').setValue('REMAINING').setFontWeight('bold').setBackground(ROW_ALT);
  ['B','C','D','E','F'].forEach(c => sh.getRange(c + '36').setFormula('=' + c + '35-' + c + '34').setBackground(ROW_ALT));
  sh.getRange('G36').setBackground(ROW_ALT);

  sh.getRange(1, 1, 36, 7)
    .setBorder(true, true, true, true, true, true, BORDER_CLR, BS);

  sh.setColumnWidth(1, 200);
  for (let c = 2; c <= 7; c++) sh.setColumnWidth(c, 110);
  sh.setFrozenRows(3);
}

// ---- Named ranges (locked spec — do not rename) ----
function createClientNamedRanges(dest) {
  const w = dest.getSheetByName('Weight');
  dest.setNamedRange('WeightDates',  w.getRange('A2:A'));
  dest.setNamedRange('WeightValues', w.getRange('B2:B'));
  dest.setNamedRange('WeightMA7',    w.getRange('D2:D'));
  dest.setNamedRange('WeeklyAvg',    w.getRange('E2:E'));
  dest.setNamedRange('DailyTotal_Calories', dest.getSheetByName('Nutrition').getRange('B34'));
}
