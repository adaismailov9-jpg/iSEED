// Small illustrations drawn in code, in the style of the characters: thick dark outline, flat colours.
const INK = '#2b2118';
const S = { stroke: INK, strokeWidth: 2.4, strokeLinejoin: 'round', strokeLinecap: 'round' };

function Frame({ size = 40, children, label }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {children}
    </svg>
  );
}

// One drawing per crop id the API uses (plus "none" for an empty field).
const CROPS = {
  beans: (
    <>
      <path d="M12 26c-2-7 4-13 10-11 4 1 4 5 1 7-3 2-3 6 1 7 5 2 3 9-4 8-5-1-7-5-8-11z" fill="#c0392b" {...S} />
      <path d="M26 18c2-6 10-7 13-1 2 5-2 8-5 7-3-1-5 1-5 4 0 5-7 5-8 0-1-4 3-6 5-10z" fill="#e05a47" {...S} />
      <path d="M16 22c1-2 3-3 5-3M30 16c2-1 4-1 5 1" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" opacity=".7" />
    </>
  ),
  alfalfa: (
    <>
      <path d="M24 44V20M24 30c-6-1-9-5-9-9 5 0 9 3 9 9zM24 26c6-1 9-5 9-9-5 0-9 3-9 9z" fill="#6fae3e" {...S} />
      <circle cx="24" cy="12" r="6" fill="#8e6cc6" {...S} />
      <circle cx="21" cy="10" r="1.6" fill="#c7b2ec" />
    </>
  ),
  maize: (
    <>
      <path d="M24 6c6 0 9 8 9 18s-4 16-9 16-9-6-9-16 3-18 9-18z" fill="#f2b632" {...S} />
      <path d="M19 14h10M17 20h14M17 26h14M18 32h12M24 7v32" fill="none" stroke="#c98a12" strokeWidth="1.6" />
      <path d="M15 24c-6 4-7 12-3 18 4-3 7-8 8-13M33 24c6 4 7 12 3 18-4-3-7-8-8-13" fill="#8bc34a" {...S} />
    </>
  ),
  sugarbeet: (
    <>
      <path d="M20 16c-4-6-2-11 3-12 1 4 0 8-3 12zM28 16c4-6 2-11-3-12-1 4 0 8 3 12z" fill="#6fae3e" {...S} />
      <path d="M14 22c0-5 5-7 10-7s10 2 10 7c0 9-6 18-10 22-4-4-10-13-10-22z" fill="#efe3c2" {...S} />
      <path d="M20 24c2 1 6 1 8 0M21 30c2 1 4 1 6 0" fill="none" stroke="#b9a46e" strokeWidth="1.6" strokeLinecap="round" />
    </>
  ),
  potato: (
    <>
      <path d="M9 26c0-9 8-15 17-14 9 1 14 7 13 15-1 9-8 13-16 12-8-1-14-5-14-13z" fill="#c69253" {...S} />
      <circle cx="18" cy="22" r="1.6" fill={INK} /><circle cx="28" cy="20" r="1.6" fill={INK} />
      <circle cx="31" cy="30" r="1.6" fill={INK} /><circle cx="20" cy="32" r="1.6" fill={INK} />
    </>
  ),
  wheat: (
    <>
      <path d="M24 44V14" fill="none" {...S} />
      {[0, 1, 2, 3].map((i) => (
        <g key={i}>
          <ellipse cx="19.5" cy={14 + i * 6} rx="4.5" ry="2.6" transform={`rotate(-35 19.5 ${14 + i * 6})`} fill="#e3b24f" {...S} />
          <ellipse cx="28.5" cy={14 + i * 6} rx="4.5" ry="2.6" transform={`rotate(35 28.5 ${14 + i * 6})`} fill="#e3b24f" {...S} />
        </g>
      ))}
      <ellipse cx="24" cy="9" rx="2.8" ry="4.5" fill="#e3b24f" {...S} />
    </>
  ),
  barley: (
    <>
      <path d="M24 44V16" fill="none" {...S} />
      {[0, 1, 2].map((i) => (
        <g key={i}>
          <ellipse cx="20" cy={16 + i * 7} rx="4" ry="2.4" transform={`rotate(-30 20 ${16 + i * 7})`} fill="#d8c06a" {...S} />
          <ellipse cx="28" cy={16 + i * 7} rx="4" ry="2.4" transform={`rotate(30 28 ${16 + i * 7})`} fill="#d8c06a" {...S} />
          <path d={`M17 ${14 + i * 7}l-6-6M31 ${14 + i * 7}l6-6`} fill="none" stroke={INK} strokeWidth="1.4" strokeLinecap="round" />
        </g>
      ))}
    </>
  ),
  safflower: (
    <>
      <path d="M24 44V24M24 34c-5-1-8-4-8-8 4 0 8 3 8 8z" fill="#6fae3e" {...S} />
      <path d="M17 22c0-4 3-6 7-6s7 2 7 6-3 6-7 6-7-2-7-6z" fill="#7fb24a" {...S} />
      <path d="M17 17c1-6 4-9 7-10 3 1 6 4 7 10" fill="#f28c28" {...S} />
      <path d="M20 16l-2-6M24 15V7M28 16l2-6" fill="none" stroke="#f2b632" strokeWidth="2.4" strokeLinecap="round" />
    </>
  ),
  none: (
    <>
      <path d="M6 34c6-8 30-8 36 0v4H6z" fill="#a5743f" {...S} />
      <path d="M14 34l2-2M24 33l2-2M33 34l2-2" fill="none" stroke="#7a5228" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
};

export function CropIcon({ id, size = 40, label }) {
  return <Frame size={size} label={label}>{CROPS[id] ?? CROPS.none}</Frame>;
}

// Where the water comes from.
const SOURCES = {
  gravity: (
    <>
      <path d="M4 18l9-10 7 7 6-6 18 15H4z" fill="#9fb3d9" {...S} />
      <path d="M13 8l3 4-3 2-3-3zM26 9l3 4-3 1-2-2z" fill="#fff" />
      <path d="M4 30h40v12H4z" fill="#5aa9e6" {...S} />
      <path d="M8 35c3-2 5-2 8 0s5 2 8 0 5-2 8 0 5 2 8 0" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </>
  ),
  pump: (
    <>
      <path d="M8 40h32" fill="none" {...S} />
      <rect x="12" y="18" width="16" height="22" rx="3" fill="#7d8b99" {...S} />
      <path d="M28 24h8v6c0 3 2 4 4 4" fill="none" {...S} />
      <circle cx="20" cy="26" r="4" fill="#f2b632" {...S} />
      <path d="M40 36c2 2 2 4 0 5-2-1-2-3 0-5z" fill="#5aa9e6" {...S} />
      <path d="M16 18v-6h8v6" fill="none" {...S} />
    </>
  ),
  well: (
    <>
      <path d="M10 22h28l-3-10H13z" fill="#c0392b" {...S} />
      <path d="M14 22v6M34 22v6M24 12V8" fill="none" {...S} />
      <rect x="10" y="28" width="28" height="14" rx="2" fill="#b0a493" {...S} />
      <path d="M10 34h28M19 28v6M29 34v8" fill="none" stroke={INK} strokeWidth="1.6" />
      <path d="M24 20c2 2 2 4 0 5-2-1-2-3 0-5z" fill="#5aa9e6" {...S} />
    </>
  ),
};

export function SourceIcon({ id, size = 40 }) {
  return <Frame size={size}>{SOURCES[id] ?? null}</Frame>;
}

// Soil texture as a little heap of soil.
const SOIL = { sandy: '#e6c98f', medium: '#a8743e', clay: '#8a4b2f', unknown: '#c9c2b4' };
export function SoilIcon({ id, size = 40 }) {
  return (
    <Frame size={size}>
      <path d="M6 38c4-14 32-14 36 0z" fill={SOIL[id]} {...S} />
      {id === 'sandy' && [14, 22, 30, 18, 27].map((x, i) => <circle key={i} cx={x} cy={i < 3 ? 33 : 28} r="1.3" fill="#b8975a" />)}
      {id === 'clay' && <path d="M14 32c3-2 6 2 9 0s6 2 9 0" fill="none" stroke="#5e2f1c" strokeWidth="1.6" strokeLinecap="round" />}
      {id === 'unknown' && <text x="24" y="35" textAnchor="middle" fontSize="12" fontWeight="900" fill={INK}>?</text>}
    </Frame>
  );
}

// The canal from the mountain to the end, with three fields. `you` marks the farmer's place;
// `fits` (start / middle / end, 0-1) fills each field with the water that reaches it.
export function CanalDiagram({ you, fits, labels, width = 300 }) {
  const places = ['start', 'middle', 'end'];
  const xs = { start: 92, middle: 168, end: 244 };
  return (
    <svg viewBox="0 0 300 120" width={width} height={(width * 120) / 300} role="img" aria-label={labels?.title}>
      <path d="M4 70l26-44 14 18 12-14 28 40z" fill="#9fb3d9" stroke={INK} strokeWidth="2.4" strokeLinejoin="round" />
      <path d="M30 26l7 10-7 4-6-6zM56 30l5 7-5 3-4-4z" fill="#fff" />
      <path d="M60 70C120 70 180 74 296 74" fill="none" stroke="#5aa9e6" strokeWidth="9" strokeLinecap="round" />
      <path d="M60 70C120 70 180 74 296 74" fill="none" stroke={INK} strokeWidth="2" strokeDasharray="1 14" strokeLinecap="round" opacity=".35" />
      {places.map((p) => {
        const fit = fits?.[p];
        const fill = fit == null ? '#8bc34a' : fit >= 0.9 ? '#6fae3e' : fit >= 0.75 ? '#e0b43c' : '#e0703c';
        return (
          <g key={p}>
            <rect x={xs[p] - 30} y="82" width="60" height="30" rx="6" fill={fill} stroke={INK} strokeWidth="2.4" opacity={you && you !== p ? 0.45 : 1} />
            {fit != null && <text x={xs[p]} y="102" textAnchor="middle" fontSize="14" fontWeight="900" fill={INK}>{Math.round(fit * 100)}%</text>}
            {you === p && (
              <g>
                <path d={`M${xs[p]} 60l-9-16a10 10 0 1 1 18 0z`} fill="#c0392b" stroke={INK} strokeWidth="2.2" strokeLinejoin="round" />
                <circle cx={xs[p]} cy="40" r="3.5" fill="#fff" />
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// A mountain whose snow cap grows and shrinks with the snow against normal (-0.2 = 20% less).
export function SnowMountain({ anomaly = 0, size = 96, label }) {
  const share = Math.max(0.15, Math.min(1.15, 1 + anomaly)); // 1 = a normal year
  const bottom = 14 + 34 * share; // the snow line: lower = more snow
  const half = (bottom - 14) * 0.774; // the mountain's slope
  const steps = 4;
  const zigzag = Array.from({ length: steps + 1 }, (_, i) => {
    const x = 50 - half + (2 * half * i) / steps;
    return `${x.toFixed(1)} ${(i % 2 ? bottom - 5 : bottom).toFixed(1)}`;
  });
  return (
    <svg viewBox="0 0 100 80" width={size} height={size * 0.8} role="img" aria-label={label}>
      <path d="M2 76L50 14l48 62z" fill="#8fa3c9" stroke={INK} strokeWidth="2.6" strokeLinejoin="round" />
      <path d={`M50 14L${zigzag.join('L')}z`} fill="#fbfdff" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}
