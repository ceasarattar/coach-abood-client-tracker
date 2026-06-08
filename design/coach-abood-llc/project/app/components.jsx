/* Shared UI components for the Coach Abood dashboard prototype.
   Exposed on window at the bottom for use across babel script files. */

const { useState, useEffect, useRef, useMemo } = React;

/* ── Icons (simple line icons, lucide-style) ───────────────────────────── */
const ICON_PATHS = {
  users:    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
  dumbbell: 'M6.5 6.5 17.5 17.5 M21 21l-1-1 M3 3l1 1 M18 22l4-4 M2 6l4-4 M3 10l7-7 M14 21l7-7',
  userplus: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M19 8v6 M22 11h-6',
  plus:     'M12 5v14 M5 12h14',
  chevright:'M9 18l6-6-6-6',
  chevleft: 'M15 18l-6-6 6-6',
  arrowleft:'M19 12H5 M12 19l-7-7 7-7',
  arrowright:'M5 12h14 M12 5l7 7-7 7',
  trend:    'M3 17l6-6 4 4 8-8 M21 7h-6 M21 7v6',
  edit:     'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z',
  trash:    'M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2',
  scale:    'M12 3v18 M5 7h14 M5 7l-3 7a4 4 0 0 0 6 0L5 7 M19 7l-3 7a4 4 0 0 0 6 0l-3-7 M8 21h8',
  dollar:   'M12 1v22 M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
  check:    'M20 6L9 17l-5-5',
  calendar: 'M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z',
  sheet:    'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h8 M8 9h2',
  flame:    'M12 2c1 4 4 5 4 9a4 4 0 0 1-8 0c0-1 .5-2 1-2.5C9 11 9 9 12 2z M8.5 14.5A3.5 3.5 0 0 0 12 18a3.5 3.5 0 0 0 3.5-3.5',
  link:     'M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1.5 1.5 M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1.5-1.5',
  warn:     'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01',
  sliders:  'M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M1 14h6 M9 8h6 M17 16h6',
  sparkles: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M5 3v4 M19 17v4 M3 5h4 M17 19h4',
  copy:     'M9 9h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V11a2 2 0 0 1 2-2z M5 15H4a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1',
  clock:    'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2',
  layers:   'M12 2 2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5',
};

function Icon({ name, size = 18, className = '', style }) {
  const d = ICON_PATHS[name];
  if (!d) return null;
  return (
    <svg className={`ico ${className}`} width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"
      strokeLinejoin="round" style={style} aria-hidden="true">
      {d.split(' M').map((seg, i) => <path key={i} d={(i ? 'M' : '') + seg} />)}
    </svg>
  );
}

/* ── Status + badges ───────────────────────────────────────────────────── */
function StatusDot({ status, title }) {
  return <span className={`dot ${status}`} title={title || `Status: ${status}`}></span>;
}

function Badge({ tone = 'gray', children, className = '' }) {
  return <span className={`badge ${tone} ${className}`}>{children}</span>;
}

/* ── Sparkline (7-pt mini line) ────────────────────────────────────────── */
function Sparkline({ points, height = 46, color }) {
  if (!points || points.length < 2) {
    return <div className="ph" style={{ height }}>no recent data</div>;
  }
  const W = 300, H = height;
  const ys = points.map(p => p.v);
  const min = Math.min(...ys), max = Math.max(...ys);
  const pad = (max - min) * 0.25 || 1;
  const lo = min - pad, hi = max + pad;
  const x = i => (i / (points.length - 1)) * (W - 6) + 3;
  const y = v => H - 6 - ((v - lo) / (hi - lo)) * (H - 12);
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ');
  const area = `${line} L${x(points.length - 1).toFixed(1)},${H} L${x(0).toFixed(1)},${H} Z`;
  const c = color || 'var(--accent)';
  const gid = useMemo(() => 'sg' + Math.random().toString(36).slice(2, 8), []);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={c} stopOpacity="0.22" />
          <stop offset="100%" stopColor={c} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={x(points.length - 1)} cy={y(points[points.length - 1].v)} r="2.6" fill={c} />
    </svg>
  );
}

/* ── Weight line chart (value + 7-day MA) ──────────────────────────────── */
function shortDate(iso) {
  const d = new Date(iso + 'T00:00:00');
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
function WeightChart({ series, unit }) {
  if (!series || series.length < 2) return <div className="ph" style={{ height: 230 }}>no weight data in range</div>;
  const W = 760, H = 250, m = { t: 16, r: 16, b: 28, l: 40 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const vals = series.flatMap(p => [p.v, p.ma7]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.3 || 1; lo -= pad; hi += pad;
  const x = i => m.l + (i / (series.length - 1)) * iw;
  const y = v => m.t + ih - ((v - lo) / (hi - lo)) * ih;
  const path = key => series.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join(' ');
  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => lo + (i / ticks) * (hi - lo));
  const xIdx = [0, Math.floor(series.length / 3), Math.floor(2 * series.length / 3), series.length - 1];
  const last = series[series.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', overflow: 'visible' }}>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke="var(--border-soft)" strokeWidth="1" />
          <text x={m.l - 8} y={y(t) + 3.5} textAnchor="end" fontSize="10.5" fill="var(--faint)" fontFamily="var(--mono)">{t.toFixed(0)}</text>
        </g>
      ))}
      {xIdx.map((idx, i) => (
        <text key={i} x={x(idx)} y={H - 8} textAnchor="middle" fontSize="10.5" fill="var(--faint)" fontFamily="var(--mono)">{shortDate(series[idx].d)}</text>
      ))}
      <path d={path('ma7')} fill="none" stroke="var(--amber)" strokeWidth="2" strokeDasharray="4 4" strokeLinecap="round" />
      <path d={path('v')} fill="none" stroke="var(--accent)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      {series.map((p, i) => <circle key={i} cx={x(i)} cy={y(p.v)} r="2" fill="var(--accent)" opacity="0.55" />)}
      <circle cx={x(series.length - 1)} cy={y(last.v)} r="3.6" fill="var(--accent)" stroke="var(--surface)" strokeWidth="1.5" />
      <g transform={`translate(${m.l + 4},${m.t})`} fontSize="10.5" fontFamily="var(--mono)">
        <line x1="0" x2="18" y1="0" y2="0" stroke="var(--accent)" strokeWidth="2.4" /><text x="24" y="3.5" fill="var(--muted)">weight ({unit})</text>
        <line x1="120" x2="138" y1="0" y2="0" stroke="var(--amber)" strokeWidth="2" strokeDasharray="4 4" /><text x="144" y="3.5" fill="var(--muted)">7-day avg</text>
      </g>
    </svg>
  );
}

/* ── Calorie bar chart with target line ────────────────────────────────── */
function CalorieChart({ series, target }) {
  if (!series || series.length < 1) return <div className="ph" style={{ height: 210 }}>no nutrition data in range</div>;
  const W = 760, H = 230, m = { t: 16, r: 16, b: 28, l: 44 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const hi = Math.max(target * 1.25, ...series.map(p => p.v)) * 1.05;
  const bw = Math.min(20, iw / series.length - 3);
  const x = i => m.l + (i + 0.5) * (iw / series.length);
  const y = v => m.t + ih - (v / hi) * ih;
  const yTicks = [0, hi * 0.5, hi];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', overflow: 'visible' }}>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke="var(--border-soft)" strokeWidth="1" />
          <text x={m.l - 8} y={y(t) + 3.5} textAnchor="end" fontSize="10.5" fill="var(--faint)" fontFamily="var(--mono)">{Math.round(t)}</text>
        </g>
      ))}
      {series.map((p, i) => {
        const over = p.v > target * 1.08;
        return <rect key={i} x={x(i) - bw / 2} y={y(p.v)} width={bw} height={m.t + ih - y(p.v)} rx="2.5"
          fill={over ? 'var(--amber)' : 'var(--accent)'} opacity={over ? 0.8 : 0.85} />;
      })}
      <line x1={m.l} x2={W - m.r} y1={y(target)} y2={y(target)} stroke="var(--green)" strokeWidth="1.6" strokeDasharray="5 4" />
      <text x={W - m.r} y={y(target) - 5} textAnchor="end" fontSize="10.5" fill="var(--green)" fontFamily="var(--mono)">target {target}</text>
    </svg>
  );
}

/* ── Toast system ──────────────────────────────────────────────────────── */
const ToastCtx = React.createContext(() => {});
function ToastHost({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = (msg, kind = 'ok') => {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3200);
  };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-wrap">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.kind}`}>
            <span className="bar"></span>
            <Icon name={t.kind === 'ok' ? 'check' : 'warn'} size={16}
              style={{ color: t.kind === 'ok' ? 'var(--green)' : 'var(--red)' }} />
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
function useToast() { return React.useContext(ToastCtx); }

Object.assign(window, {
  Icon, StatusDot, Badge, Sparkline, WeightChart, CalorieChart,
  ToastHost, useToast, shortDate,
});
