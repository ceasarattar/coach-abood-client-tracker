/* App shell: sidebar nav, hash router, tweaks (accent + density). */

const { useState: useS, useEffect: useE } = React;

/* Curated accent sets — single hex; variants derived via color-mix. */
const ACCENTS = {
  Blue:   '#4f9be8',
  Green:  '#3fb583',
  Violet: '#8f7be0',
  Amber:  '#d79a52',
};

function applyAccent(hex) {
  const r = document.documentElement.style;
  r.setProperty('--accent', hex);
  r.setProperty('--accent-bright', `color-mix(in oklab, ${hex} 80%, white)`);
  r.setProperty('--accent-dim', `color-mix(in srgb, ${hex} 15%, transparent)`);
  r.setProperty('--accent-line', `color-mix(in srgb, ${hex} 42%, transparent)`);
  r.setProperty('--accent-ink', `color-mix(in oklab, ${hex} 20%, #050b12)`);
}

/* ── Router ────────────────────────────────────────────────────────────── */
function parseRoute() {
  const h = (location.hash || '#/').replace(/^#/, '');
  const parts = h.split('/').filter(Boolean); // ['client','Name']
  if (parts.length === 0) return { page: 'clients', params: {} };
  if (parts[0] === 'client') return { page: 'clientDetail', params: { name: parts[1] } };
  if (parts[0] === 'library') {
    if (parts[1] === 'new') return { page: 'programNew', params: {} };
    if (parts[2] === 'edit') return { page: 'programEdit', params: { id: parts[1] } };
    return { page: 'library', params: {} };
  }
  if (parts[0] === 'clients') {
    if (parts[1] === 'new') return { page: 'wizard', params: {} };
    return { page: 'addClient', params: {} };
  }
  return { page: 'clients', params: {} };
}

window.navigate = (hash) => { location.hash = hash; };

function useHashRoute() {
  const [route, setRoute] = useS(parseRoute());
  useE(() => {
    const on = () => { setRoute(parseRoute()); window.scrollTo({ top: 0 }); };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
function Sidebar({ active }) {
  const items = [
    { key: 'clients', label: 'Clients', icon: 'users', hash: '#/' },
    { key: 'library', label: 'Workout Library', icon: 'dumbbell', hash: '#/library' },
    { key: 'add', label: 'Add client', icon: 'userplus', hash: '#/clients/add' },
  ];
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">CA</div>
        <div><div className="brand-name">Coach Abood</div><div className="brand-sub">control panel</div></div>
      </div>
      <div className="nav-group-label">Manage</div>
      {items.map(it => (
        <div key={it.key} className={`nav-item ${active === it.key ? 'active' : ''}`} onClick={() => window.navigate(it.hash)}>
          <Icon name={it.icon} size={18} /> {it.label}
        </div>
      ))}
      <div className="nav-spacer"></div>
      <div className="nav-foot"><span className="dot-live"></span> 127.0.0.1:5000 · Sheets sync</div>
    </aside>
  );
}

/* ── Crumbs ────────────────────────────────────────────────────────────── */
function Crumbs({ route }) {
  const map = {
    clients: ['Clients'],
    clientDetail: ['Clients', decodeURIComponent(route.params.name || '')],
    library: ['Workout Library'],
    programNew: ['Workout Library', 'New program'],
    programEdit: ['Workout Library', 'Edit program'],
    addClient: ['Clients', 'Add client'],
    wizard: ['Clients', 'Add client', 'New setup'],
  };
  const trail = map[route.page] || ['Clients'];
  return (
    <div className="crumbs">
      {trail.map((t, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="sep">/</span>}
          <span style={{ color: i === trail.length - 1 ? 'var(--text-2)' : 'var(--muted)' }}>{t}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

/* ── App ───────────────────────────────────────────────────────────────── */
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#4f9be8",
  "density": "comfortable"
}/*EDITMODE-END*/;

function App() {
  const route = useHashRoute();
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  useE(() => { applyAccent(t.accent); }, [t.accent]);

  const activeNav = ({ clients: 'clients', clientDetail: 'clients', library: 'library',
    programNew: 'library', programEdit: 'library', addClient: 'add', wizard: 'add' })[route.page] || 'clients';

  let Page;
  switch (route.page) {
    case 'clients': Page = <ClientsPage />; break;
    case 'clientDetail': Page = <ClientDetailPage params={route.params} />; break;
    case 'library': Page = <LibraryPage />; break;
    case 'programNew': Page = <ProgramEditorPage params={{}} />; break;
    case 'programEdit': Page = <ProgramEditorPage params={route.params} />; break;
    case 'addClient': Page = <AddClientPage />; break;
    case 'wizard': Page = <NewClientWizard />; break;
    default: Page = <ClientsPage />;
  }

  return (
    <div className="app" data-density={t.density === 'compact' ? 'compact' : 'comfortable'}>
      <Sidebar active={activeNav} />
      <div className="main">
        <div className="topbar"><Crumbs route={route} /></div>
        <div className="content">{Page}</div>
      </div>

      <TweaksPanel>
        <TweakSection label="Appearance" />
        <TweakColor label="Accent" value={t.accent}
          options={Object.values(ACCENTS)} onChange={v => setTweak('accent', v)} />
        <TweakRadio label="Density" value={t.density}
          options={['comfortable', 'compact']} onChange={v => setTweak('density', v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ToastHost><App /></ToastHost>
);
