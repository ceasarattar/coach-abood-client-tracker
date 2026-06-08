/* Pages: Add Client (unified) + New Client Wizard.
   Replaces the old split between /clients/add and /clients/new with one entry. */

/* ── Add client — choose a path ────────────────────────────────────────── */
function AddClientPage() {
  const toast = useToast();
  const [name, setName] = React.useState('');
  const [sheet, setSheet] = React.useState('');
  const [plan, setPlan] = React.useState('');
  const [unit, setUnit] = React.useState('kg');
  const [adv, setAdv] = React.useState(false);
  const [master, setMaster] = React.useState('');

  const submit = (e) => {
    e.preventDefault();
    if (!name.trim() || !sheet.trim()) { toast('Client name and sheet URL are both required.', 'err'); return; }
    toast(`Client “${name}” added.`, 'ok');
    setTimeout(() => window.navigate('#/'), 700);
  };

  return (
    <div>
      <span className="back-link" onClick={() => window.navigate('#/')}><Icon name="arrowleft" size={14} /> Clients</span>
      <div className="page-head">
        <div><h1 className="page-title">Add a client</h1>
          <p className="page-sub">Two ways in — connect a sheet you already built, or set one up from scratch.</p></div>
      </div>

      <div className="two-col" style={{ alignItems: 'stretch' }}>
        {/* Path A — existing sheet */}
        <form className="panel" onSubmit={submit} style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, background: 'var(--accent-dim)', color: 'var(--accent-bright)', display: 'grid', placeItems: 'center' }}><Icon name="sheet" size={18} /></div>
            <div><div style={{ fontWeight: 680 }}>Connect an existing sheet</div><div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>Most common · appears on the dashboard right away</div></div>
          </div>

          <label className="field">
            <span className="field-label">Client name <span className="req">*</span></span>
            <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Alex Morgan" />
            <span className="field-hint">must match the master Payments tab</span>
          </label>
          <label className="field">
            <span className="field-label"><Icon name="link" size={14} /> Google Sheet URL or ID <span className="req">*</span></span>
            <input className="input mono" value={sheet} onChange={e => setSheet(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/…" />
            <span className="field-hint">paste the full URL — the ID is extracted automatically</span>
          </label>
          <div className="field-row">
            <label className="field"><span className="field-label">Monthly plan ($)</span>
              <input className="input num narrow" value={plan} onChange={e => setPlan(e.target.value)} placeholder="150" /></label>
            <label className="field"><span className="field-label">Weight unit</span>
              <div className="seg"><button type="button" className={unit === 'kg' ? 'on' : ''} onClick={() => setUnit('kg')}>kg</button><button type="button" className={unit === 'lbs' ? 'on' : ''} onClick={() => setUnit('lbs')}>lbs</button></div></label>
          </div>

          <button type="button" className="btn btn-ghost btn-sm" style={{ alignSelf: 'flex-start', marginBottom: adv ? '0.8rem' : 0 }} onClick={() => setAdv(a => !a)}>
            <Icon name={adv ? 'chevright' : 'chevright'} size={13} style={{ transform: adv ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }} /> Advanced
          </button>
          {adv && (
            <label className="field">
              <span className="field-label">Master sheet ID (override)</span>
              <input className="input mono" value={master} onChange={e => setMaster(e.target.value)} placeholder="leave blank to use default master" />
            </label>
          )}

          <div style={{ marginTop: 'auto', paddingTop: '1.2rem' }}>
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }}><Icon name="check" size={16} /> Add client</button>
          </div>
        </form>

        {/* Path B — build from scratch */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, background: 'var(--surface-2)', color: 'var(--accent-bright)', display: 'grid', placeItems: 'center' }}><Icon name="sparkles" size={18} /></div>
            <div><div style={{ fontWeight: 680 }}>Build a new client from scratch</div><div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>Program, RIR, targets → generate their sheet</div></div>
          </div>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-2)', lineHeight: 1.6 }}>
            Use the guided setup to define everything in one place. It writes to the master sheet's admin tabs, then you run
            <span className="mono" style={{ color: 'var(--accent-bright)' }}> Coach Tools → Generate Client Template</span> and register the new sheet.
          </p>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.55rem', margin: '1.1rem 0', fontSize: '0.84rem', color: 'var(--muted)' }}>
            {['Client info & billing', 'Pick or build a program', 'Week & RIR progression', 'Nutrition targets'].map((s, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span style={{ width: 20, height: 20, borderRadius: 6, background: 'var(--surface-2)', color: 'var(--accent-bright)', display: 'grid', placeItems: 'center', fontSize: '0.7rem', fontFamily: 'var(--mono)', fontWeight: 700 }}>{i + 1}</span>{s}
              </li>
            ))}
          </ul>
          <div style={{ marginTop: 'auto' }}>
            <button className="btn" style={{ width: '100%' }} onClick={() => window.navigate('#/clients/new')}>Start guided setup <Icon name="arrowright" size={16} /></button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── New client wizard ─────────────────────────────────────────────────── */
const WIZ_STEPS = ['Client', 'Program', 'Week & RIR', 'Targets', 'Review', 'Generate'];

function NewClientWizard() {
  const toast = useToast();
  const [step, setStep] = React.useState(0);
  const [wrote, setWrote] = React.useState(false);
  const [info, setInfo] = React.useState({ name: '', email: '', program_name: '', goal: '', start_date: '2026-06-08', weight_unit: 'kg', plan_usd: '', billing_day: '1' });
  const [sched, setSched] = React.useState(window.DAYS.map(d => ({ day_name: d, workout_type: 'Rest' })));
  const [rows, setRows] = React.useState([]);
  const [numWeeks, setNumWeeks] = React.useState(10);
  const [rir, setRir] = React.useState({});
  const [targets, setTargets] = React.useState({ calories: '2400', protein: '180', carbs: '240', fat: '70', fiber: '30' });

  const setI = (k, v) => setInfo(s => ({ ...s, [k]: v }));

  const loadPreset = (id) => {
    const p = window.PROGRAMS.find(x => String(x.id) === String(id));
    if (!p) { setRows([]); return; }
    const by = {}; p.schedule.forEach(s => { by[s.day_name] = s.workout_type; });
    setSched(window.DAYS.map(d => ({ day_name: d, workout_type: by[d] || 'Rest' })));
    setRows(p.exercises.map(e => ({ ...e })));
    setI('program_name', p.name);
  };

  // Apply the coach's default RIR scheme from the PDF.
  const applyDefaultRir = () => {
    const r = {};
    for (let w = 1; w <= numWeeks; w++) r[w] = w === 1 ? '1-2' : w <= 5 ? '1' : '0-1';
    setRir(r);
  };
  React.useEffect(() => { if (Object.keys(rir).length === 0) applyDefaultRir(); }, [numWeeks]);

  const generate = () => { setWrote(true); setStep(5); toast('Data written to the master sheet.', 'ok'); };

  const canNext = step === 0 ? info.name.trim() : true;

  return (
    <div>
      <span className="back-link" onClick={() => window.navigate('#/clients/add')}><Icon name="arrowleft" size={14} /> Add client</span>
      <div className="page-head">
        <div><h1 className="page-title">New client setup</h1>
          <p className="page-sub">Define everything, write to the master sheet, generate, then register.</p></div>
      </div>

      {/* Stepper */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {WIZ_STEPS.map((s, i) => (
          <button key={s} onClick={() => i <= step && setStep(i)}
            style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', padding: '0.4rem 0.75rem', borderRadius: 999,
              border: `1px solid ${i === step ? 'var(--accent)' : 'var(--border)'}`, cursor: i <= step ? 'pointer' : 'default',
              background: i === step ? 'var(--accent)' : i < step ? 'var(--surface-2)' : 'transparent',
              color: i === step ? 'var(--accent-ink)' : i < step ? 'var(--text)' : 'var(--faint)', fontSize: '0.8rem', fontWeight: 650 }}>
            <span style={{ width: 18, height: 18, borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: '0.68rem', fontFamily: 'var(--mono)',
              background: i === step ? 'var(--accent-ink)' : 'transparent', color: i === step ? 'var(--accent)' : 'inherit',
              border: i < step ? 'none' : `1px solid ${i === step ? 'transparent' : 'var(--border)'}` }}>
              {i < step ? <Icon name="check" size={11} /> : i + 1}</span>{s}
          </button>
        ))}
      </div>

      <div className="panel" style={{ marginBottom: '1.2rem' }}>
        {step === 0 && (
          <div>
            <div className="panel-title">Step 1 · Client info</div>
            <div className="field-row">
              <label className="field"><span className="field-label">Client name <span className="req">*</span></span><input className="input" value={info.name} onChange={e => setI('name', e.target.value)} placeholder="Full name" /></label>
              <label className="field"><span className="field-label">Email</span><input className="input mono" value={info.email} onChange={e => setI('email', e.target.value)} placeholder="name@email.com" /></label>
            </div>
            <div className="field-row">
              <label className="field"><span className="field-label">Program name</span><input className="input" value={info.program_name} onChange={e => setI('program_name', e.target.value)} placeholder="e.g. PPL / Upper / Lower" /></label>
              <label className="field"><span className="field-label">Goal</span><input className="input" value={info.goal} onChange={e => setI('goal', e.target.value)} placeholder="e.g. Build muscle" /></label>
            </div>
            <div className="field-row">
              <label className="field"><span className="field-label">Start date</span><input className="input mono" type="date" value={info.start_date} onChange={e => setI('start_date', e.target.value)} /></label>
              <label className="field"><span className="field-label">Weight unit</span><div className="seg"><button type="button" className={info.weight_unit === 'kg' ? 'on' : ''} onClick={() => setI('weight_unit', 'kg')}>kg</button><button type="button" className={info.weight_unit === 'lbs' ? 'on' : ''} onClick={() => setI('weight_unit', 'lbs')}>lbs</button></div></label>
              <label className="field"><span className="field-label">Monthly plan ($)</span><input className="input num narrow" value={info.plan_usd} onChange={e => setI('plan_usd', e.target.value)} placeholder="150" /></label>
              <label className="field"><span className="field-label">Billing day</span><input className="input num narrow" value={info.billing_day} onChange={e => setI('billing_day', e.target.value)} placeholder="1" /></label>
            </div>
          </div>
        )}

        {step === 1 && (
          <div>
            <div className="panel-title">Step 2 · Program</div>
            <label className="field" style={{ maxWidth: 360 }}>
              <span className="field-label">Start from a saved program</span>
              <select className="select" onChange={e => loadPreset(e.target.value)} defaultValue="">
                <option value="">— build custom —</option>
                {window.PROGRAMS.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <div style={{ fontSize: '0.7rem', color: 'var(--faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', margin: '1rem 0 0.5rem' }}>Weekly schedule</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '0.6rem' }} className="sched-grid">
              {sched.map((s, i) => (
                <div key={s.day_name}>
                  <div style={{ fontSize: '0.66rem', color: 'var(--faint)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.3rem' }}>{window.DAY_ABBR[s.day_name]}</div>
                  <input className="input" list="wt-list" value={s.workout_type} onChange={e => setSched(sc => sc.map((x, j) => j === i ? { ...x, workout_type: e.target.value } : x))}
                    style={{ padding: '0.42rem 0.45rem', fontSize: '0.78rem', textAlign: 'center', color: s.workout_type === 'Rest' ? 'var(--faint)' : 'var(--accent-bright)', fontWeight: 600 }} />
                </div>
              ))}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', margin: '1.2rem 0 0.5rem' }}>Exercises · {rows.length}</div>
            {rows.length === 0 ? <p className="no-data">Pick a preset above or add exercises manually.</p> : (
              <div style={{ maxHeight: 260, overflowY: 'auto', border: '1px solid var(--border-soft)', borderRadius: 'var(--radius-sm)' }}>
                <table className="table"><thead><tr><th>Type</th><th>Exercise</th><th>Sets</th><th>Reps</th></tr></thead>
                  <tbody>{rows.map((r, i) => <tr key={i}><td className="mono" style={{ color: 'var(--accent-bright)', fontSize: '0.74rem' }}>{r.workout_type}</td><td style={{ color: 'var(--text)' }}>{r.exercise}</td><td className="num">{r.target_sets}</td><td className="num">{r.target_reps}</td></tr>)}</tbody>
                </table>
              </div>
            )}
            <button className="btn btn-sm" style={{ marginTop: '0.8rem' }} onClick={() => setRows(r => [...r, { workout_type: '', exercise: 'New exercise', target_sets: '', target_reps: '', coach_notes: '', tutorial_url: '' }])}><Icon name="plus" size={14} /> Add exercise</button>
          </div>
        )}

        {step === 2 && (
          <div>
            <div className="panel-title">Step 3 · Week & RIR progression</div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '1rem', marginBottom: '1rem' }}>
              <label className="field" style={{ marginBottom: 0 }}><span className="field-label">Number of weeks</span><input className="input num narrow" value={numWeeks} onChange={e => setNumWeeks(Math.max(1, Math.min(52, parseInt(e.target.value) || 1)))} /></label>
              <button className="btn btn-sm" onClick={applyDefaultRir}><Icon name="sparkles" size={14} /> Apply coach default (W1 1-2 → W2-5 1 → W6+ 0-1)</button>
            </div>
            <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid var(--border-soft)', borderRadius: 'var(--radius-sm)' }}>
              <table className="table"><thead><tr><th>Week</th><th>Target RIR</th></tr></thead>
                <tbody>{Array.from({ length: numWeeks }, (_, i) => i + 1).map(w => (
                  <tr key={w}><td style={{ fontWeight: 600, color: 'var(--text)' }}>Week {w}</td>
                    <td><input className="input num narrow" value={rir[w] || ''} onChange={e => setRir(r => ({ ...r, [w]: e.target.value }))} style={{ padding: '0.32rem 0.45rem', fontSize: '0.8rem' }} /></td></tr>
                ))}</tbody></table>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <div className="panel-title">Step 4 · Nutrition targets</div>
            <div className="field-row">
              {[['calories', 'Calories (kcal)'], ['protein', 'Protein (g)'], ['carbs', 'Carbs (g)'], ['fat', 'Fat (g)'], ['fiber', 'Fiber (g)']].map(([k, label]) => (
                <label key={k} className="field"><span className="field-label">{label}</span><input className="input num" value={targets[k]} onChange={e => setTargets(t => ({ ...t, [k]: e.target.value }))} /></label>
              ))}
            </div>
          </div>
        )}

        {step === 4 && (
          <div>
            <div className="panel-title">Step 5 · Review</div>
            <div className="two-col">
              <div>
                <ReviewBlock title="Client" rows={[['Name', info.name || '—'], ['Email', info.email || '—'], ['Program', info.program_name || '—'], ['Goal', info.goal || '—'], ['Start', info.start_date], ['Plan', `$${info.plan_usd || '0'} · billing day ${info.billing_day}`], ['Unit', info.weight_unit]]} />
                <ReviewBlock title="Targets" rows={[['Calories', `${targets.calories} kcal`], ['Macros', `P ${targets.protein} · C ${targets.carbs} · F ${targets.fat} · Fiber ${targets.fiber}`]]} />
              </div>
              <div>
                <ReviewBlock title="Program" rows={[['Training days', String(sched.filter(s => s.workout_type !== 'Rest').length)], ['Exercises', String(rows.length)], ['Schedule', sched.filter(s => s.workout_type !== 'Rest').map(s => `${window.DAY_ABBR[s.day_name]} ${s.workout_type}`).join(', ') || '—']]} />
                <ReviewBlock title="Progression" rows={[['Weeks', String(numWeeks)], ['RIR', `W1 ${rir[1] || '—'} → W${numWeeks} ${rir[numWeeks] || '—'}`]]} />
              </div>
            </div>
          </div>
        )}

        {step === 5 && (
          <div>
            <div className="panel-title">Step 6 · Generate</div>
            {!wrote ? (
              <div>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-2)', lineHeight: 1.6, maxWidth: 560 }}>
                  This writes everything above into the master spreadsheet's admin tabs
                  (<span className="mono" style={{ color: 'var(--accent-bright)' }}>⚙ Client Info</span>, <span className="mono" style={{ color: 'var(--accent-bright)' }}>Program Builder</span>, <span className="mono" style={{ color: 'var(--accent-bright)' }}>Week & RIR</span>, <span className="mono" style={{ color: 'var(--accent-bright)' }}>Targets</span>).
                  Then open the master sheet and run <strong>Coach Tools → Generate Client Template</strong>.
                </p>
                <button className="btn btn-primary" style={{ marginTop: '1.2rem' }} onClick={generate}><Icon name="sheet" size={16} /> Write data to master sheet</button>
              </div>
            ) : (
              <div>
                <div className="toast ok" style={{ position: 'static', marginBottom: '1.2rem', maxWidth: 540 }}><span className="bar"></span><Icon name="check" size={16} style={{ color: 'var(--green)' }} /><span>Written. Now run <strong style={{ margin: '0 0.25rem' }}>Coach Tools → Generate Client Template</strong> in the master sheet.</span></div>
                <div style={{ maxWidth: 520 }}>
                  <div style={{ fontWeight: 680, marginBottom: '0.2rem' }}>Register the generated client</div>
                  <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: '1rem' }}>Paste the new sheet's URL to add {info.name || 'them'} to the dashboard.</p>
                  <label className="field"><span className="field-label"><Icon name="link" size={14} /> New sheet URL or ID</span><input className="input mono" placeholder="https://docs.google.com/spreadsheets/d/…" /></label>
                  <button className="btn btn-primary" onClick={() => { toast(`Client “${info.name || 'New client'}” registered.`, 'ok'); setTimeout(() => window.navigate('#/'), 700); }}><Icon name="check" size={16} /> Register client</button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Nav */}
      {!wrote && (
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <button className="btn btn-ghost" style={{ visibility: step === 0 ? 'hidden' : 'visible' }} onClick={() => setStep(s => s - 1)}><Icon name="arrowleft" size={16} /> Back</button>
          {step < 5 && <button className="btn btn-primary" disabled={!canNext} onClick={() => setStep(s => s + 1)}>Next <Icon name="arrowright" size={16} /></button>}
        </div>
      )}

      <datalist id="wt-list">{window.WORKOUT_TYPES.map(w => <option key={w} value={w} />)}</datalist>
    </div>
  );
}

function ReviewBlock({ title, rows }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--accent-bright)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.5rem' }}>{title}</div>
      <table className="table"><tbody>
        {rows.map(([k, v]) => <tr key={k}><th style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 550, color: 'var(--muted)', fontSize: '0.78rem' }}>{k}</th><td style={{ color: 'var(--text)' }}>{v}</td></tr>)}
      </tbody></table>
    </div>
  );
}

Object.assign(window, { AddClientPage, NewClientWizard });
