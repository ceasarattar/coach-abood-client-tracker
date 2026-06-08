/* Pages: Clients grid, Client detail, Add client, Log modal.
   Uses window.CLIENTS, window.navigate, useToast(). */

const { useState: useStateC, useMemo: useMemoC } = React;

function clientBy(name) { return window.CLIENTS.find(c => c.name === name); }

function deltaEl(delta, unit) {
  if (delta == null) return <span className="delta flat">—</span>;
  if (delta < 0) return <span className="delta down"><Icon name="arrowright" size={12} style={{ transform: 'rotate(45deg)' }} />{Math.abs(delta).toFixed(1)} {unit}</span>;
  if (delta > 0) return <span className="delta up"><Icon name="arrowright" size={12} style={{ transform: 'rotate(-45deg)' }} />{delta.toFixed(1)} {unit}</span>;
  return <span className="delta flat">±0.0</span>;
}

function lastLoggedLabel(ll) {
  if (!ll) return { txt: 'Never logged', tone: 'faint' };
  if (ll.days_ago === 0) return { txt: 'Logged today', tone: 'green' };
  if (ll.days_ago === 1) return { txt: 'Yesterday', tone: 'green' };
  if (ll.days_ago >= 7) return { txt: `${ll.days_ago} days ago`, tone: 'red' };
  if (ll.days_ago >= 5) return { txt: `${ll.days_ago} days ago`, tone: 'amber' };
  return { txt: `${ll.days_ago} days ago`, tone: 'muted' };
}

/* ── Client card ───────────────────────────────────────────────────────── */
function ClientCard({ c }) {
  const ll = lastLoggedLabel(c.last_logged);
  return (
    <div className="panel client-card" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.95rem' }}
      onClick={() => window.navigate(`#/client/${encodeURIComponent(c.name)}`)}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <StatusDot status={c.status} />
        <span style={{ fontWeight: 680, fontSize: '1rem', flex: 1, letterSpacing: '-0.02em' }}>{c.name}</span>
        <span className="pill mono">${c.plan_usd}/mo</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div>
          <div style={{ fontSize: '0.68rem', color: 'var(--faint)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>Latest weight</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 720, letterSpacing: '-0.03em', marginTop: '0.15rem' }} className="tnum">
            {c.latest_weight != null ? `${c.latest_weight.toFixed(1)}` : '—'}
            <span style={{ fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600 }}> {c.weight_unit}</span>
          </div>
        </div>
        <div style={{ textAlign: 'right', paddingBottom: '0.2rem' }}>{deltaEl(c.weight_delta, c.weight_unit)}<div style={{ fontSize: '0.66rem', color: 'var(--faint)', marginTop: '0.1rem' }}>vs last entry</div></div>
      </div>

      <Sparkline points={c.spark} color={c.weight_delta <= 0 ? 'var(--green)' : 'var(--amber)'} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: `var(--${ll.tone === 'muted' ? 'muted' : ll.tone === 'faint' ? 'faint' : ll.tone})`, fontWeight: 600 }}>
          <Icon name="dumbbell" size={14} /> {ll.txt}
        </div>
        <span style={{ fontSize: '0.7rem', color: 'var(--faint)' }} className="mono">{c.program.replace(' Program', '')}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-soft)', paddingTop: '0.8rem', marginTop: 'auto' }}>
        <Badge tone={c.payment_class}>{c.payment_display}</Badge>
        <span style={{ fontSize: '0.78rem', color: 'var(--accent-bright)', fontWeight: 650, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
          Open <Icon name="chevright" size={14} />
        </span>
      </div>
    </div>
  );
}

/* ── Clients grid page ─────────────────────────────────────────────────── */
function ClientsPage() {
  const [filter, setFilter] = useStateC('all');
  const clients = window.CLIENTS;
  const counts = useMemoC(() => ({
    all: clients.length,
    attention: clients.filter(c => c.status !== 'green').length,
    overdue: clients.filter(c => c.payment_class === 'red').length,
  }), [clients]);
  const shown = filter === 'attention' ? clients.filter(c => c.status !== 'green') : clients;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Clients</h1>
          <p className="page-sub">{counts.all} active · <span style={{ color: counts.attention ? 'var(--amber)' : 'var(--muted)' }}>{counts.attention} need attention</span></p>
        </div>
        <button className="btn btn-primary" onClick={() => window.navigate('#/clients/add')}>
          <Icon name="userplus" size={16} /> Add client
        </button>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.3rem' }}>
        <button className={`btn btn-sm ${filter === 'all' ? '' : 'btn-ghost'}`} onClick={() => setFilter('all')}>All clients</button>
        <button className={`btn btn-sm ${filter === 'attention' ? '' : 'btn-ghost'}`} onClick={() => setFilter('attention')}>
          Needs attention {counts.attention > 0 && <span style={{ marginLeft: 4, color: 'var(--amber)' }}>{counts.attention}</span>}
        </button>
      </div>

      <div className="card-grid">
        {shown.map(c => <ClientCard key={c.name} c={c} />)}
      </div>
    </div>
  );
}

/* ── Stat tile ─────────────────────────────────────────────────────────── */
function Stat({ label, value, sub, icon, tone }) {
  return (
    <div className="panel" style={{ padding: '1rem 1.1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--faint)', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
        {icon && <Icon name={icon} size={14} />} {label}
      </div>
      <div className="tnum" style={{ fontSize: '1.5rem', fontWeight: 720, letterSpacing: '-0.03em', marginTop: '0.4rem', color: tone || 'var(--text)' }}>{value}</div>
      {sub && <div style={{ fontSize: '0.74rem', color: 'var(--muted)', marginTop: '0.1rem' }}>{sub}</div>}
    </div>
  );
}

/* ── Client detail page ────────────────────────────────────────────────── */
function ClientDetailPage({ params }) {
  const c = clientBy(decodeURIComponent(params.name || ''));
  const [logKind, setLogKind] = useStateC(null); // 'weight' | 'payment' | null
  if (!c) return <div className="empty">Client not found.</div>;

  const w = c.weight30;
  const change30 = w.length >= 2 ? Math.round((w[w.length - 1].v - w[0].v) * 10) / 10 : null;
  const avgCal = c.cal30.length ? Math.round(c.cal30.reduce((s, p) => s + p.v, 0) / c.cal30.length) : null;
  const ll = lastLoggedLabel(c.last_logged);
  const rec = c.payment_record;

  return (
    <div>
      <span className="back-link" onClick={() => window.navigate('#/')}><Icon name="arrowleft" size={14} /> All clients</span>

      <div className="page-head">
        <div>
          <h1 className="page-title"><StatusDot status={c.status} /> {c.name}</h1>
          <p className="page-sub">
            {c.goal} · <span className="mono">{c.program}</span> · ${c.plan_usd}/mo
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn" onClick={() => setLogKind('weight')}><Icon name="scale" size={16} /> Log weight</button>
          <button className="btn btn-primary" onClick={() => setLogKind('payment')}><Icon name="dollar" size={16} /> Mark paid</button>
        </div>
      </div>

      {/* Stat strip */}
      <div className="stat-strip" style={{ marginBottom: 'var(--gap)' }}>
        <Stat label="Latest weight" icon="scale" value={c.latest_weight != null ? `${c.latest_weight.toFixed(1)} ${c.weight_unit}` : '—'} sub={c.last_logged ? `as of ${c.weight_table[c.weight_table.length - 1].date}` : 'no entries'} />
        <Stat label="30-day change" icon="trend" tone={change30 < 0 ? 'var(--green)' : change30 > 0 ? 'var(--amber)' : null}
          value={change30 != null ? `${change30 > 0 ? '+' : ''}${change30.toFixed(1)} ${c.weight_unit}` : '—'} sub="vs 30 days ago" />
        <Stat label="Last workout" icon="dumbbell" tone={`var(--${ll.tone === 'muted' || ll.tone === 'faint' ? 'text' : ll.tone})`}
          value={ll.txt} sub={c.last_logged ? c.last_logged.date : '—'} />
        <Stat label="Avg calories" icon="flame" value={avgCal != null ? avgCal.toLocaleString() : '—'} sub={`target ${c.cal_target.toLocaleString()} kcal`} />
      </div>

      <div className="detail-grid">
        {/* Left column — charts */}
        <div className="stack">
          <div className="panel">
            <div className="panel-title">Body weight · last 30 days</div>
            <WeightChart series={w} unit={c.weight_unit} />
          </div>
          <div className="panel">
            <div className="panel-title">Daily calories · last 30 days</div>
            <CalorieChart series={c.cal30} target={c.cal_target} />
          </div>
        </div>

        {/* Right column — payment + program */}
        <div className="stack">
          <div className="panel">
            <div className="panel-title">Payment <Badge tone={c.payment_class}>{c.payment_display}</Badge></div>
            <table className="table">
              <tbody>
                {['Monthly Plan ($)', 'Billing Day', 'Last Paid Date', 'Days Since Last Paid', 'Amount Overdue', 'Notes'].map(k => {
                  const v = rec[k];
                  if (!v) return null;
                  return <tr key={k}><th style={{ color: 'var(--muted)', textTransform: 'none', letterSpacing: 0, fontSize: '0.78rem', fontWeight: 550 }}>{k.replace(' ($)', '')}</th>
                    <td className={k.includes('Date') || k.includes('Day') || k.includes('Plan') || k.includes('Overdue') ? 'num' : ''} style={{ textAlign: 'right' }}>{k === 'Monthly Plan ($)' ? `$${v}` : v}</td></tr>;
                })}
              </tbody>
            </table>
            <button className="btn btn-sm" style={{ marginTop: '0.8rem', width: '100%' }} onClick={() => setLogKind('payment')}><Icon name="check" size={14} /> Mark payment received</button>
          </div>

          <div className="panel">
            <div className="panel-title">Program</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.7rem' }}>
              <div style={{ width: 38, height: 38, borderRadius: 10, background: 'var(--surface-2)', display: 'grid', placeItems: 'center', color: 'var(--accent-bright)' }}><Icon name="dumbbell" size={18} /></div>
              <div><div style={{ fontWeight: 650 }}>{c.program}</div><div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>{c.goal}</div></div>
            </div>
            <button className="btn btn-sm btn-ghost" style={{ width: '100%' }} onClick={() => {
              const p = window.PROGRAMS.find(p => p.name === c.program);
              if (p) window.navigate(`#/library/${p.id}/edit`);
            }}><Icon name="edit" size={14} /> View program in library</button>
          </div>
        </div>
      </div>

      {/* Tables row */}
      <div className="two-col" style={{ marginTop: 'var(--gap)' }}>
        <div className="panel">
          <div className="panel-title">Workout log · sessions completed by week</div>
          {c.week_summary.length ? (
            <table className="table">
              <thead><tr><th>Week</th><th>Sessions</th><th style={{ width: '45%' }}>Progress</th></tr></thead>
              <tbody>
                {c.week_summary.map(wk => {
                  const pct = wk.total ? Math.round(100 * wk.logged / wk.total) : 0;
                  return (
                    <tr key={wk.week}>
                      <td style={{ fontWeight: 600, color: 'var(--text)' }}>{wk.week}</td>
                      <td className="num">{wk.logged} / {wk.total}</td>
                      <td>
                        <div style={{ height: 7, background: 'var(--surface-2)', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--amber)' : 'var(--red)', transition: 'width 0.4s' }}></div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : <p className="no-data">No week tabs found for this client.</p>}
        </div>

        <div className="panel">
          <div className="panel-title">Last 14 weight entries</div>
          <div style={{ maxHeight: 320, overflowY: 'auto' }}>
            <table className="table hover">
              <thead><tr><th>Date</th><th style={{ textAlign: 'right' }}>Weight ({c.weight_unit})</th></tr></thead>
              <tbody>
                {[...c.weight_table].reverse().map((r, i) => (
                  <tr key={i}><td className="num">{r.date}</td><td className="num" style={{ textAlign: 'right', color: 'var(--text)' }}>{r.val.toFixed(1)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {logKind && <LogModal client={c} kind={logKind} onClose={() => setLogKind(null)} onSwitch={setLogKind} />}
    </div>
  );
}

/* ── Log modal (weight / payment) — maps to /client/<name>/log ─────────── */
function LogModal({ client, kind, onClose, onSwitch }) {
  const toast = useToast();
  const today = window.fmtDMY(new Date('2026-06-07T00:00:00'));
  const [date, setDate] = useStateC(today);
  const [weight, setWeight] = useStateC('');

  const submit = (e) => {
    e.preventDefault();
    if (kind === 'weight') {
      if (!weight) { toast('Enter a weight value.', 'err'); return; }
      toast(`Logged ${weight} ${client.weight_unit} for ${date}.`, 'ok');
    } else {
      toast(`Marked payment received on ${date}.`, 'ok');
    }
    onClose();
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'oklch(0 0 0 / 0.55)', display: 'grid', placeItems: 'center', zIndex: 150, padding: '1rem', backdropFilter: 'blur(2px)' }} onClick={onClose}>
      <div className="panel" style={{ width: 'min(440px, 100%)', boxShadow: 'var(--shadow)' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.2rem' }}>
          <button className={`btn btn-sm ${kind === 'weight' ? '' : 'btn-ghost'}`} onClick={() => onSwitch('weight')}><Icon name="scale" size={14} /> Log weight</button>
          <button className={`btn btn-sm ${kind === 'payment' ? '' : 'btn-ghost'}`} onClick={() => onSwitch('payment')}><Icon name="dollar" size={14} /> Mark paid</button>
        </div>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '0.3rem' }}>
          {kind === 'weight' ? `Log weight — ${client.name}` : `Mark payment — ${client.name}`}
        </h2>
        <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '1.2rem' }}>
          {kind === 'weight' ? 'Writes to the matching date row in the client\u2019s Weight tab.' : 'Updates Last Paid Date in the master Payments tab.'}
        </p>
        <form onSubmit={submit}>
          <label className="field">
            <span className="field-label"><Icon name="calendar" size={14} /> {kind === 'weight' ? 'Date' : 'Paid date'}</span>
            <input className="input mono" value={date} onChange={e => setDate(e.target.value)} placeholder="dd/mm/yyyy" />
          </label>
          {kind === 'weight' && (
            <label className="field">
              <span className="field-label"><Icon name="scale" size={14} /> Weight ({client.weight_unit})</span>
              <input className="input" value={weight} onChange={e => setWeight(e.target.value)} placeholder="e.g. 80.4" autoFocus />
            </label>
          )}
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1.3rem' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">{kind === 'weight' ? 'Save weight' : 'Mark paid'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

Object.assign(window, { ClientsPage, ClientDetailPage, LogModal });
