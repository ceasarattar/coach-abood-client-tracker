/************************************************************************
 * COACH KHADER — CLIENT TEMPLATE GENERATOR  (v9)
 *
 * v9 (dynamic sessions + config-in-POST):
 *   - The Flask wizard now sends ALL client data inline in the POST body
 *     (config-in-POST). The Apps Script no longer needs to read the master
 *     ⚙ admin tabs on the one-click path — it receives a fully-formed config.
 *   - Sessions are dynamic and ordered (no weekday lock). Each session has a
 *     custom label (e.g. "Full Body A") and its own exercises.
 *   - Idempotency via requestId: a repeated POST with the same requestId
 *     returns the cached sheet URL immediately — fixes the orphan-sheet race
 *     when the Flask request timed out and the user retried.
 *   - Trash-on-error: if generation fails mid-way the partial file is moved
 *     to Drive trash so no orphan is left.
 *   - Sheets are shared as "anyone with link can edit" so non-Google clients
 *     (Hotmail, Outlook, …) can open them without a Google account.
 *   - Coach name changed to "Coach Khader" everywhere.
 *   - The menu path (Coach Tools → Generate Client Template) still reads the
 *     master ⚙ admin tabs as before and is unchanged.
 *
 * v8 fixes the Weight tab locale (en_GB, dd/MM/yyyy) and Week # formula.
 * v7 adds the web-app entry point for one-click generation from the dashboard.
 *
 * DEPLOY AS WEB APP (after any Code.gs change):
 *   1. Keep WEBAPP_SECRET below in sync with TEMPLATE_WEBAPP_SECRET on Render.
 *   2. Extensions → Apps Script → Deploy → Manage deployments →
 *      Edit (pencil) → New version → Deploy.
 *   3. If the /exec URL changes, update TEMPLATE_WEBAPP_URL on Render too.
 *   4. Run Coach Tools → Run First-Time Setup once (sets master locale).
 ************************************************************************/

// Match TEMPLATE_WEBAPP_SECRET on Render (keep private).
const WEBAPP_SECRET = '';

// Dashboard's Google service-account email — every generated sheet is auto-
// shared with it so the dashboard can read it. Find it as "client_email" in
// the service-account JSON. Leave '' to share manually.
const SERVICE_ACCOUNT_EMAIL = '';

// Email the client a "your sheet is ready" message when generated.
const NOTIFY_CLIENT = true;
const COACH_NAME = 'Coach Khader';

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
  try { ss.setSpreadsheetLocale('en_GB'); } catch (e) { /* non-fatal */ }
  if (missing.length) { ui.alert('Missing admin tabs: ' + missing.join(', ')); return; }
  ui.alert('Setup OK. Master locale set to dd/MM/yyyy (UK). All admin tabs found — '
           + 'you can now use Generate Client Template.');
}

// ====================================================================
//  WEB APP ENTRY POINTS
// ====================================================================
function doPost(e) { return handleWebRequest_(e); }
function doGet(e)  { return handleWebRequest_(e); }

function handleWebRequest_(e) {
  try {
    var params = {};
    if (e && e.postData && e.postData.contents) {
      try { params = JSON.parse(e.postData.contents); } catch (err) { params = {}; }
    }
    var secret = params.secret || (e && e.parameter && e.parameter.secret) || '';
    if (secret !== WEBAPP_SECRET) {
      return jsonOut_({ ok: false, error: 'Unauthorized (bad or missing secret).' });
    }

    // Idempotency: if this requestId was already processed, return the cached result.
    if (params.requestId) {
      var props = PropertiesService.getScriptProperties();
      var cached = props.getProperty('rid:' + params.requestId);
      if (cached) {
        var cd = JSON.parse(cached);
        return jsonOut_({ ok: true, url: cd.url, id: cd.id,
                          fileName: cd.fileName, sharedWith: cd.sharedWith, cached: true });
      }
    }

    // Config-in-POST path (Flask wizard) OR legacy read-from-sheets path (menu fallback).
    var cfg = params.config ? normalizeConfig_(params.config) : readConfig();
    var res = generateFromConfig_(cfg);

    // Cache the result so a retry with the same requestId is instant.
    if (params.requestId) {
      var toCache = { url: res.dest.getUrl(), id: res.dest.getId(),
                      fileName: res.fileName, sharedWith: res.sharedWith };
      PropertiesService.getScriptProperties()
        .setProperty('rid:' + params.requestId, JSON.stringify(toCache));
    }

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

// ====================================================================
//  CONFIG — two sources: inline POST or master ⚙ tabs
// ====================================================================

/**
 * normalizeConfig_: convert the Flask wizard's config-in-POST payload into
 * the internal cfg shape that generateFromConfig_ expects.
 *
 * Input shape (matches _build_config_payload in app.py):
 *   { info: {name,email,program,goal,start,unit,plan,billing},
 *     sessions: [{label, exercises:[{ex,sets,reps,notes,link}]}],
 *     weeks: [{week,rir}],
 *     targets: [cal,protein,carbs,fat,fiber],
 *     sleepTarget: '' }
 */
function normalizeConfig_(rawCfg) {
  var info = rawCfg.info || {};
  var cfg = {
    name:    String(info.name    || '').trim(),
    email:   String(info.email   || '').trim(),
    program: String(info.program || '').trim(),
    goal:    String(info.goal    || '').trim(),
    unit:    String(info.unit    || 'kg').trim(),
    plan:    info.plan,
    billing: info.billing
  };

  if (!cfg.name) throw new Error('Client name is required.');

  // Parse start date — Flask sends dd/mm/yyyy string.
  var s = String(info.start || '').trim();
  var dateObj;
  if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(s)) {
    var parts = s.split('/');
    dateObj = new Date(+parts[2], +parts[1] - 1, +parts[0]);
  } else {
    dateObj = new Date(s); // ISO fallback
  }
  if (isNaN(dateObj.getTime())) {
    throw new Error('Invalid start date: "' + s + '" — expected dd/mm/yyyy.');
  }
  cfg.start = dateObj;

  // Weeks
  cfg.weeks = (rawCfg.weeks || []).filter(function(w) { return w.week; })
    .map(function(w) { return { week: Number(w.week), rir: Number(w.rir) }; });
  if (!cfg.weeks.length) throw new Error('No weeks defined.');

  // Sessions → internal schedule + exByType (same shape buildWeekTab uses).
  var sessions = (rawCfg.sessions || []).filter(function(s) {
    return s.label && s.exercises && s.exercises.length > 0;
  });
  cfg.schedule = sessions.map(function(s) { return { day: s.label, type: s.label }; });
  cfg.exByType = {};
  sessions.forEach(function(s) {
    cfg.exByType[s.label] = (s.exercises || []).map(function(e) {
      return {
        ex:    String(e.ex    || '').trim(),
        sets:  String(e.sets  || '').trim(),
        reps:  normalizeReps(e.reps || ''),
        notes: String(e.notes || '').trim(),
        link:  String(e.link  || '').trim()
      };
    }).filter(function(e) { return e.ex; });
  });

  // Targets: array [cal, protein, carbs, fat, fiber]
  cfg.targets     = rawCfg.targets || ['', '', '', '', ''];
  cfg.sleepTarget = String(rawCfg.sleepTarget || '').trim();

  return cfg;
}

/**
 * readConfig: reads the master ⚙ admin tabs (used by the menu path and as
 * the fallback when no config is supplied in the POST).
 */
function readConfig() {
  const ss          = SpreadsheetApp.getActiveSpreadsheet();
  const infoVals    = ss.getSheetByName(T_INFO).getRange('B3:B10').getValues();
  const weekVals    = ss.getSheetByName(T_WEEKRIR).getRange('A4:B100').getValues();
  const pb          = ss.getSheetByName(T_PROGRAM);
  const schedVals   = pb.getRange('B5:C11').getValues();
  const exVals      = pb.getRange('A15:F300').getValues();
  const targetVals  = ss.getSheetByName(T_TARGETS).getRange('B2:B6').getValues();
  const sleepTargetVal = ss.getSheetByName(T_TARGETS).getRange('B7').getValue();

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
  cfg.exByType    = exByType;
  cfg.targets     = targetVals.map(r => r[0]);
  cfg.sleepTarget = String(sleepTargetVal || '').trim();
  return cfg;
}

// ====================================================================
//  CORE GENERATION — headless, returns {dest, fileName, sharedWith}
// ====================================================================
function generateFromConfig_(cfg) {
  const fname = cfg.name + ' — Coach Khader';
  const dest  = SpreadsheetApp.create(fname);

  try {
    dest.setSpreadsheetLocale('en_GB');

    buildWeightTab(dest, cfg);
    cfg.weeks.forEach(w => buildWeekTab(dest, cfg, w.week, w.rir));
    buildNutritionTab(dest, cfg);

    const s1 = dest.getSheetByName('Sheet1');
    if (s1) dest.deleteSheet(s1);

    createClientNamedRanges(dest);
    SpreadsheetApp.flush();

    // Share with anyone who has the link — works for non-Google clients
    // (Hotmail, Outlook, etc.) without requiring a Google account or PIN.
    try {
      DriveApp.getFileById(dest.getId())
              .setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.EDIT);
    } catch (e) { /* non-fatal */ }

    // Also share with the dashboard's service account (read path).
    if (SERVICE_ACCOUNT_EMAIL) {
      try { dest.addEditor(SERVICE_ACCOUNT_EMAIL); }
      catch (e) { /* non-fatal */ }
    }

    let sharedWith = '';
    if (cfg.email) {
      try {
        dest.addEditor(cfg.email);
        sharedWith = cfg.email;
        if (NOTIFY_CLIENT) notifyClient_(cfg, dest);
      }
      catch (e) { sharedWith = 'ERROR: ' + e.message; }
    }
    return { dest: dest, fileName: fname, sharedWith: sharedWith };

  } catch (err) {
    // Trash the partial file so no orphan is left in Drive.
    try { DriveApp.getFileById(dest.getId()).setTrashed(true); } catch (e2) {}
    throw err;
  }
}

// ---- Notify the client their sheet is ready ----
function notifyClient_(cfg, dest) {
  try {
    MailApp.sendEmail({
      to: cfg.email,
      subject: 'Your ' + COACH_NAME + ' training sheet is ready',
      htmlBody:
        '<p>Hi ' + (cfg.name || 'there') + ',</p>' +
        '<p>Your personal training &amp; nutrition tracker is ready. Open it here:</p>' +
        '<p><a href="' + dest.getUrl() + '">' + dest.getName() + '</a></p>' +
        '<p>Use it to log your weight, sleep, workouts and daily nutrition. ' +
        'Message me anytime with questions.</p>' +
        '<p>— ' + COACH_NAME + '</p>'
    });
  } catch (e) {
    // Non-fatal: client has access even if the email quota is hit.
  }
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

// ====================================================================
//  SHEET BUILDERS
// ====================================================================

// ---- Weight tab ----
function buildWeightTab(dest, cfg) {
  const sh      = dest.insertSheet('Weight');
  const n       = 140;
  const lastRow = n + 1;
  const lastCol = 12;

  sh.setHiddenGridlines(true);

  const sleepHead = cfg.sleepTarget ? 'Sleep (hrs) · goal ' + cfg.sleepTarget : 'Sleep (hrs)';
  sh.getRange(1, 1, 1, lastCol)
    .setValues([[
      'Date', 'Weight (' + cfg.unit + ')', 'Day Δ', '7-Day Avg', 'Weekly Avg',
      'Week #', 'Notes', 'Steps', 'Total Steps', 'Calories', 'Total Calories', sleepHead
    ]])
    .setFontWeight('bold').setFontColor(WHITE)
    .setBackground(NAVY).setHorizontalAlignment('center');

  const last = n + 1;

  sh.getRange('C1').setFormula(
    '={"Day Δ"; ""; ARRAYFORMULA(IF((B3:B' + last + '="")+(B2:B' + (last-1) + '=""),"",B3:B' + last + '-B2:B' + (last-1) + '))}'
  );
  sh.getRange('D1').setFormula(
    '={"7-Day Avg"; BYROW(SEQUENCE(' + n + ',1,2),LAMBDA(r,IF(INDEX(B:B,r)="","",IFERROR(AVERAGEIFS(B$2:B$' + last + ',A$2:A$' + last + ',">="&INDEX(A:A,r)-6,A$2:A$' + last + ',"<="&INDEX(A:A,r)),""))))}'
  );
  sh.getRange('E1').setFormula(
    '={"Weekly Avg"; BYROW(F2:F' + last + ',LAMBDA(f,IF(f="","",IFERROR(AVERAGEIF(F$2:F$' + last + ',f,B$2:B$' + last + '),""))))}'
  );
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
  sh.getRange(2, 12, n, 1).setBackground(INPUT);

  [110, 100, 80, 110, 110, 80, 200, 90, 110, 90, 120, 100]
    .forEach((w, i) => sh.setColumnWidth(i + 1, w));

  sh.setFrozenRows(1);
  sh.getRange(1, 1, lastRow, lastCol)
    .setBorder(true, true, true, true, true, true, BORDER_CLR, BS);

  sh.getRange(2, 2, n, 1).setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireNumberBetween(20, 300).setAllowInvalid(false)
      .setHelpText('Enter weight in ' + cfg.unit + ' (20–300).').build()
  );
  sh.getRange(2, 12, n, 1).setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireNumberBetween(0, 24).setAllowInvalid(false)
      .setHelpText('Hours of sleep (0–24).').build()
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

    // For dynamic sessions (day === type), show just the label; for weekday-
    // based programs from the menu path, show "TYPE — Day" as before.
    const headerText = (s.day && s.day !== s.type)
      ? (s.type.toUpperCase() + '  —  ' + s.day)
      : s.type.toUpperCase();

    sh.getRange(r, 1, 1, totalCols).merge()
      .setValue(headerText)
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
    sh.getRange(dataStart, 7, numEx, 1).setNumberFormat('dd/MM/yyyy');
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
