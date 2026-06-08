/* Client fixtures for the Coach Abood dashboard prototype.
 *
 * These mirror the shapes the Flask app builds in build_card() / build_detail():
 *   card:   {name, plan_usd, weight_unit, status, latest_weight, weight_delta,
 *            spark:[{d,v}], last_logged:{date,days_ago}, payment_display, payment_class}
 *   detail: adds weight30:[{d,v,ma7}], cal30:[{d,v}], week_summary:[{week,logged,total}],
 *            weight_table:[{date,val}], payment_record:{...PAYMENT_COLUMNS}
 *
 * Data is generated deterministically (seeded) so it is stable across reloads.
 */

window.PAYMENT_COLUMNS = [
  'Client Name', 'Monthly Plan ($)', 'Billing Day', 'Last Paid Date',
  'Days Since Last Paid', 'Status', 'Days Overdue', 'Amount Overdue', 'Notes',
];

const TODAY = new Date('2026-06-07T00:00:00');

function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function isoOffset(daysAgo) {
  const d = new Date(TODAY);
  d.setDate(d.getDate() - daysAgo);
  return d;
}
function fmtISO(d) { return d.toISOString().slice(0, 10); }
function fmtDMY(d) {
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}/${mm}/${d.getFullYear()}`;
}

/* Build a daily weight series trending by `slopePerDay`, with noise + gaps. */
function genWeights(seed, days, start, slopePerDay, noise, lastLogGap) {
  const rnd = mulberry32(seed);
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    // Skip the most recent `lastLogGap` days (client stopped logging).
    if (i < lastLogGap) continue;
    // Occasional missed day.
    if (i !== days - 1 && i >= lastLogGap && rnd() < 0.18) continue;
    const day = days - 1 - i;
    const v = start + slopePerDay * day + (rnd() - 0.5) * 2 * noise;
    out.push({ d: fmtISO(isoOffset(i)), v: Math.round(v * 10) / 10 });
  }
  return out;
}

/* 7-day moving average aligned to the series. */
function withMA7(series) {
  return series.map((pt, i) => {
    const slice = series.slice(Math.max(0, i - 6), i + 1);
    const ma = slice.reduce((s, p) => s + p.v, 0) / slice.length;
    return { d: pt.d, v: pt.v, ma7: Math.round(ma * 10) / 10 };
  });
}

function genCalories(seed, days, target, adherence) {
  const rnd = mulberry32(seed + 99);
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    if (rnd() > adherence) continue; // didn't log nutrition that day
    const swing = (rnd() - 0.45) * 2 * (target * 0.14);
    out.push({ d: fmtISO(isoOffset(i)), v: Math.round(target + swing) });
  }
  return out;
}

function genWeekSummary(seed, weeks, sessionsPerWeek, dropOff) {
  const rnd = mulberry32(seed + 7);
  const out = [];
  for (let w = 1; w <= weeks; w++) {
    let logged;
    if (w < weeks) logged = Math.random < 0 ? 0 : Math.min(sessionsPerWeek, Math.round(sessionsPerWeek - (rnd() < dropOff ? 1 : 0)));
    else logged = Math.max(0, Math.round(sessionsPerWeek * rnd())); // current week partial
    out.push({ week: `Week ${w}`, logged, total: sessionsPerWeek });
  }
  return out;
}

function lastLoggedFrom(series) {
  if (!series.length) return null;
  const last = new Date(series[series.length - 1].d + 'T00:00:00');
  const daysAgo = Math.round((TODAY - last) / 86400000);
  return { date: fmtDMY(last), days_ago: daysAgo };
}

function paymentRecord(name, plan, billingDay, lastPaidDaysAgo, status, daysOverdue, notes) {
  const lp = isoOffset(lastPaidDaysAgo);
  return {
    'Client Name': name,
    'Monthly Plan ($)': String(plan),
    'Billing Day': String(billingDay),
    'Last Paid Date': fmtISO(lp),
    'Days Since Last Paid': String(lastPaidDaysAgo),
    'Status': status,
    'Days Overdue': daysOverdue ? String(daysOverdue) : '',
    'Amount Overdue': daysOverdue ? `$${plan}` : '',
    'Notes': notes || '',
  };
}

function payDisplay(record) {
  const status = (record['Status'] || '').toUpperCase().trim();
  if (status.includes('OVERDUE')) {
    const d = record['Days Overdue'];
    return { text: d ? `OVERDUE ${d}d` : 'OVERDUE', cls: 'red', overdue: true };
  }
  if (status === 'DUE SOON') return { text: 'DUE SOON', cls: 'yellow', overdue: false };
  if (status === 'OK' || status === 'PAID') return { text: status, cls: 'green', overdue: false };
  return { text: 'No data', cls: 'gray', overdue: false };
}

function statusDot(weight30, lastLogged, overdue) {
  if (overdue) return 'red';
  const wGap = weight30.length
    ? Math.round((TODAY - new Date(weight30[weight30.length - 1].d + 'T00:00:00')) / 86400000)
    : 99;
  const wo = lastLogged ? lastLogged.days_ago : 99;
  if (wGap >= 5 || wo >= 7) return 'red';
  if (wGap === 4 || wo === 5 || wo === 6) return 'yellow';
  return 'green';
}

/* ── Client definitions ──────────────────────────────────────────────────── */
const DEFS = [
  { name: 'Ceasar Attar', sheetId: '1aBcD3fGhIjKlMnOpQrStUvWxYz0123456789AbCdE',
    plan: 150, unit: 'kg', program: 'PPL UL Program', goal: 'Lean & strong',
    seed: 11, start: 84.5, slope: -0.06, noise: 0.5, lastGap: 1, calTarget: 2350, adh: 0.92,
    weeks: 8, spw: 5, drop: 0.15, billing: 1, paidAgo: 9, status: 'OK', overdue: 0,
    notes: 'Auto-pay on the 1st.' },
  { name: 'Maya Rodriguez', sheetId: '1ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210ZyXwV',
    plan: 120, unit: 'lbs', program: 'Upper Lower Program', goal: 'Recomp',
    seed: 22, start: 158, slope: -0.04, noise: 1.2, lastGap: 5, calTarget: 1950, adh: 0.7,
    weeks: 6, spw: 4, drop: 0.4, billing: 15, paidAgo: 27, status: 'Due Soon', overdue: 0,
    notes: 'Billing day 15.' },
  { name: 'Jordan Lee', sheetId: '1QwErTyUiOpAsDfGhJkLzXcVbNm1234567890QwErT',
    plan: 150, unit: 'kg', program: 'Full Body Program', goal: 'Build muscle',
    seed: 33, start: 72.0, slope: 0.03, noise: 0.6, lastGap: 9, calTarget: 2700, adh: 0.45,
    weeks: 5, spw: 3, drop: 0.6, billing: 5, paidAgo: 41, status: 'Overdue', overdue: 11,
    notes: 'Reminder sent 06/02.' },
  { name: 'Priya Nair', sheetId: '1MnBvCxZaSdFgHjKlPoIuYtReWq0987654321MnBvC',
    plan: 200, unit: 'lbs', program: 'PPL UL Program', goal: 'Lean bulk',
    seed: 44, start: 132, slope: 0.05, noise: 0.9, lastGap: 0, calTarget: 2600, adh: 0.95,
    weeks: 8, spw: 5, drop: 0.1, billing: 20, paidAgo: 4, status: 'OK', overdue: 0,
    notes: '' },
];

const CLIENTS = DEFS.map((c) => {
  const w30full = withMA7(genWeights(c.seed, 60, c.start, c.slope, c.noise, c.lastGap));
  const last = lastLoggedFrom(w30full);
  const cal30 = genCalories(c.seed, 30, c.calTarget, c.adh);
  const week_summary = genWeekSummary(c.seed, c.weeks, c.spw, c.drop);
  const record = paymentRecord(c.name, c.plan, c.billing, c.paidAgo, c.status, c.overdue, c.notes);
  const pay = payDisplay(record);
  const status = statusDot(w30full, last, pay.overdue);

  const sorted = w30full.slice();
  const latest = sorted[sorted.length - 1];
  const prev = sorted[sorted.length - 2];
  const spark = sorted.slice(-7).map(p => ({ d: p.d, v: p.v }));
  const last30 = sorted.filter(p => (TODAY - new Date(p.d + 'T00:00:00')) / 86400000 <= 30);

  return {
    name: c.name,
    sheetId: c.sheetId,
    plan_usd: c.plan,
    weight_unit: c.unit,
    program: c.program,
    goal: c.goal,
    cal_target: c.calTarget,
    status,
    latest_weight: latest ? latest.v : null,
    weight_delta: (latest && prev) ? Math.round((latest.v - prev.v) * 10) / 10 : null,
    spark,
    last_logged: last,
    payment_display: pay.text,
    payment_class: pay.cls,
    payment_record: record,
    weight30: last30,
    cal30,
    week_summary,
    weight_table: sorted.slice(-14).map(p => ({
      date: fmtDMY(new Date(p.d + 'T00:00:00')), val: p.v,
    })),
  };
});

window.CLIENTS = CLIENTS;
window.fmtDMY = fmtDMY;
