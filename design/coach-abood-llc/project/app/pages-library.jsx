/* Pages: Workout Library list + Program editor (schedule + exercise table). */

const WORKOUT_TYPES = ['Push', 'Pull', 'Legs', 'Upper', 'Lower', 'Full Body',
  'Chest', 'Back', 'Shoulders', 'Arms', 'Core', 'Cardio', 'Conditioning', 'Rest'];
const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const DAY_ABBR = { Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed', Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat', Sunday: 'Sun' };

function typeTone(t) {
  if (!t || t === 'Rest') return 'rest';
  return 'work';
}

/* ── Library list ──────────────────────────────────────────────────────── */
function LibraryPage() {
  const toast = useToast();
  const [programs, setPrograms] = React.useState(window.PROGRAMS);
  const del = (id, name) => {
    if (!confirm(`Delete program “${name}”? This cannot be undone.`)) return;
    setPrograms(p => p.filter(x => x.id !== id));
    toast(`Program “${name}” deleted.`, 'ok');
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Workout Library</h1>
          <p className="page-sub">{programs.length} reusable program{programs.length !== 1 ? 's' : ''} · stored locally, never in a client sheet</p>
        </div>
        <button className="btn btn-primary" onClick={() => window.navigate('#/library/new')}><Icon name="plus" size={16} /> New program</button>
      </div>

      {programs.length === 0 ? (
        <div className="empty"><Icon name="dumbbell" /><p>No programs yet.</p>
          <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => window.navigate('#/library/new')}>Create your first program</button></div>
      ) : (
        <div className="stack">
          {programs.map(p => {
            const days = p.schedule.filter(s => s.workout_type && s.workout_type !== 'Rest');
            return (
              <div key={p.id} className="panel" style={{ display: 'flex', alignItems: 'center', gap: '1.2rem', padding: '1.1rem 1.3rem' }}>
                <div style={{ width: 44, height: 44, borderRadius: 12, background: 'var(--surface-2)', display: 'grid', placeItems: 'center', color: 'var(--accent-bright)', flexShrink: 0 }}>
                  <Icon name="layers" size={20} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 680, fontSize: '1rem' }}>{p.name}</span>
                    <span className="pill mono">{p.training_days} days/wk</span>
                    <span className="pill mono">{p.exercise_count} exercises</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.6rem', flexWrap: 'wrap' }}>
                    {p.schedule.map(s => (
                      <span key={s.day_order} title={`${s.day_name}: ${s.workout_type}`}
                        style={{ fontSize: '0.66rem', fontFamily: 'var(--mono)', padding: '0.16rem 0.4rem', borderRadius: 6, whiteSpace: 'nowrap',
                          background: typeTone(s.workout_type) === 'rest' ? 'transparent' : 'var(--accent-dim)',
                          color: typeTone(s.workout_type) === 'rest' ? 'var(--faint)' : 'var(--accent-bright)',
                          border: `1px solid ${typeTone(s.workout_type) === 'rest' ? 'var(--border-soft)' : 'var(--accent-line)'}` }}>
                        {DAY_ABBR[s.day_name]} · {s.workout_type === 'Rest' ? '—' : s.workout_type}
                      </span>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
                  <button className="btn btn-sm" onClick={() => window.navigate(`#/library/${p.id}/edit`)}><Icon name="edit" size={14} /> Edit</button>
                  <button className="btn btn-sm btn-danger" onClick={() => del(p.id, p.name)}><Icon name="trash" size={14} /></button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Program editor ────────────────────────────────────────────────────── */
function ProgramEditorPage({ params }) {
  const toast = useToast();
  const editing = params.id ? window.PROGRAMS.find(p => String(p.id) === String(params.id)) : null;

  const [name, setName] = React.useState(editing ? editing.name : '');
  const [notes, setNotes] = React.useState(editing ? editing.notes : '');
  const [sched, setSched] = React.useState(() => {
    const by = {};
    (editing ? editing.schedule : []).forEach(s => { by[s.day_name] = s.workout_type; });
    return DAYS.map(d => ({ day_name: d, workout_type: by[d] || 'Rest' }));
  });
  const [rows, setRows] = React.useState(() =>
    editing ? editing.exercises.map(e => ({ ...e })) : [{ workout_type: '', exercise: '', target_sets: '', target_reps: '', coach_notes: '', tutorial_url: '' }]
  );

  const setRow = (i, key, val) => setRows(r => r.map((row, j) => j === i ? { ...row, [key]: val } : row));
  const addRow = () => setRows(r => [...r, { workout_type: '', exercise: '', target_sets: '', target_reps: '', coach_notes: '', tutorial_url: '' }]);
  const dupRow = (i) => setRows(r => [...r.slice(0, i + 1), { ...r[i] }, ...r.slice(i + 1)]);
  const delRow = (i) => setRows(r => r.filter((_, j) => j !== i));

  const save = () => {
    if (!name.trim()) { toast('Program name is required.', 'err'); return; }
    toast(`Program “${name}” ${editing ? 'saved' : 'created'}.`, 'ok');
    window.navigate('#/library');
  };

  // Group exercise rows by workout type for visual section headers.
  return (
    <div>
      <span className="back-link" onClick={() => window.navigate('#/library')}><Icon name="arrowleft" size={14} /> Library</span>
      <div className="page-head">
        <div><h1 className="page-title">{editing ? 'Edit program' : 'New program'}</h1>
          <p className="page-sub">{editing ? editing.notes ? editing.notes.slice(0, 90) + (editing.notes.length > 90 ? '…' : '') : 'Reusable program template' : 'Build a reusable program template'}</p></div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-ghost" onClick={() => window.navigate('#/library')}>Cancel</button>
          <button className="btn btn-primary" onClick={save}><Icon name="check" size={16} /> {editing ? 'Save changes' : 'Create program'}</button>
        </div>
      </div>

      <div className="stack">
        <div className="panel">
          <div className="field-row">
            <label className="field" style={{ flex: 2 }}>
              <span className="field-label">Program name <span className="req">*</span></span>
              <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. PPL Hypertrophy" />
            </label>
            <label className="field" style={{ flex: 3 }}>
              <span className="field-label">Notes</span>
              <input className="input" value={notes} onChange={e => setNotes(e.target.value)} placeholder="RIR progression, intent, etc." />
            </label>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Weekly schedule</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '0.6rem' }} className="sched-grid">
            {sched.map((s, i) => (
              <div key={s.day_name}>
                <div style={{ fontSize: '0.68rem', color: 'var(--faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.35rem' }}>{DAY_ABBR[s.day_name]}</div>
                <input className="input" list="wt-list" value={s.workout_type}
                  onChange={e => setSched(sc => sc.map((x, j) => j === i ? { ...x, workout_type: e.target.value } : x))}
                  style={{ padding: '0.45rem 0.5rem', fontSize: '0.8rem', textAlign: 'center',
                    color: s.workout_type === 'Rest' ? 'var(--faint)' : 'var(--accent-bright)', fontWeight: 600 }} />
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Exercises <span className="pill mono">{rows.length}</span></div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ minWidth: 760 }}>
              <thead>
                <tr><th style={{ width: 110 }}>Day / type</th><th>Exercise</th><th style={{ width: 60 }}>Sets</th><th style={{ width: 80 }}>Reps</th><th>Coach notes</th><th style={{ width: 130 }}>Tutorial</th><th style={{ width: 70 }}></th></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td><input className="input" list="wt-list" value={r.workout_type} onChange={e => setRow(i, 'workout_type', e.target.value)} placeholder="day" style={{ padding: '0.38rem 0.5rem', fontSize: '0.8rem' }} /></td>
                    <td><input className="input" value={r.exercise} onChange={e => setRow(i, 'exercise', e.target.value)} placeholder="Exercise name" style={{ padding: '0.38rem 0.5rem', fontSize: '0.82rem' }} /></td>
                    <td><input className="input num" value={r.target_sets} onChange={e => setRow(i, 'target_sets', e.target.value)} placeholder="2" style={{ padding: '0.38rem 0.4rem', fontSize: '0.8rem', textAlign: 'center' }} /></td>
                    <td><input className="input num" value={r.target_reps} onChange={e => setRow(i, 'target_reps', e.target.value)} placeholder="8,6" style={{ padding: '0.38rem 0.4rem', fontSize: '0.8rem', textAlign: 'center' }} /></td>
                    <td><input className="input" value={r.coach_notes} onChange={e => setRow(i, 'coach_notes', e.target.value)} placeholder="cue / setup" style={{ padding: '0.38rem 0.5rem', fontSize: '0.8rem' }} /></td>
                    <td><input className="input mono" value={r.tutorial_url} onChange={e => setRow(i, 'tutorial_url', e.target.value)} placeholder="url" style={{ padding: '0.38rem 0.5rem', fontSize: '0.72rem' }} /></td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.2rem' }}>
                        <button className="btn btn-sm btn-ghost" title="Duplicate" onClick={() => dupRow(i)} style={{ padding: '0.3rem' }}><Icon name="copy" size={13} /></button>
                        <button className="btn btn-sm btn-danger" title="Remove" onClick={() => delRow(i)} style={{ padding: '0.3rem' }}><Icon name="trash" size={13} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="btn btn-sm" style={{ marginTop: '0.9rem' }} onClick={addRow}><Icon name="plus" size={14} /> Add exercise</button>
        </div>
      </div>

      <datalist id="wt-list">{WORKOUT_TYPES.map(w => <option key={w} value={w} />)}</datalist>
    </div>
  );
}

Object.assign(window, { LibraryPage, ProgramEditorPage, WORKOUT_TYPES, DAYS, DAY_ABBR });
