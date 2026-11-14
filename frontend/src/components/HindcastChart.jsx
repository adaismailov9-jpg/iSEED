import { useI18n } from '../i18n';

// Bar chart of Feb–Mar snow per year. Triangles mark known water-shortage years.
const W = 360;
const H = 230;
const PAD = { left: 34, right: 10, top: 22, bottom: 26 };

export default function HindcastChart({ data }) {
  const { t } = useI18n();
  const { series, norm, terciles, shortageYears, currentYear } = data;

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const yMax = Math.ceil(Math.max(...series.map((s) => s.value)) * 11.5) / 10;
  const step = plotW / series.length;
  const x = (i) => PAD.left + (i + 0.5) * step;
  const y = (v) => PAD.top + plotH - (v / yMax) * plotH;

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t('about.chart')}>
        <rect className="band" x={PAD.left} width={plotW} y={y(terciles[1])} height={y(terciles[0]) - y(terciles[1])} />

        {[0, yMax / 2, yMax].map((v) => (
          <g key={v}>
            <line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} />
            <text className="axis" x={PAD.left - 5} y={y(v) + 3} textAnchor="end">{Math.round(v * 100)}%</text>
          </g>
        ))}

        {series.map((s, i) => (
          <g key={s.year}>
            <rect className={`bar bar-${s.level} ${s.year === currentYear ? 'bar-current' : ''}`}
              x={x(i) - step / 3} width={step / 1.5} y={y(s.value)} height={y(0) - y(s.value)} rx="1.5">
              <title>{`${s.year}: ${Math.round(s.value * 100)}%`}</title>
            </rect>
            {shortageYears.includes(s.year) && <path className="mark" d={`M${x(i) - 4.5},${y(s.value) - 10} h9 l-4.5,7 z`} />}
            {(i % 4 === 0 || s.year === currentYear) && (
              <text className="axis" x={x(i)} y={H - PAD.bottom + 15} textAnchor="middle">{s.year}</text>
            )}
          </g>
        ))}

        <line className="norm" x1={PAD.left} x2={W - PAD.right} y1={y(norm)} y2={y(norm)} />
      </svg>

      <figcaption className="legend">
        {['low', 'normal', 'high', 'norm', 'shortage'].map((key) => (
          <span key={key}><i className={`swatch swatch-${key}`} />{t(`about.${key}`)}</span>
        ))}
      </figcaption>
    </figure>
  );
}
