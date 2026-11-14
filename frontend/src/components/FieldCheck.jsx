import { useI18n } from '../i18n';
import { fmtDec, fmtShare } from '../lib/format';
import Badge from './Badge';

// The numbers each check's sentence needs; `value` differs per check (see CLAUDE.md, POST /fields).
function textVars({ id, value }, t, lang) {
  if (id === 'slope') return { value: fmtDec(value, 1, lang) }; // degrees
  if (id === 'green') return value; // { greenYears, bareYears, years }
  if (id === 'soil') return { soil: t(`soil.${value}`) };
  if (id === 'frost') return { days: Math.abs(value) }; // days to spare, negative = short
  return { pct: fmtShare(value) }; // heavyRain: share of years
}

// "Can I plant here?" — the verdict is the worst of the checks; each check in plain words.
export default function FieldCheck({ check }) {
  const { t, lang } = useI18n();
  if (!check) return <p className="hint">{t('check.none')}</p>;

  return (
    <div className={`field-check level-${check.verdict}`}>
      <b className="check-verdict"><span className="dot" /> {t(`check.verdict.${check.verdict}`)}</b>
      <ul>
        {check.checks.map((c) => (
          <li key={c.id} className={`level-${c.level}`}>
            <span className="dot" /> {t(`check.${c.id}.${c.level}`, textVars(c, t, lang))} <Badge kind="source" label={t(`sources.${c.source}`).split(' — ')[0]} source={t(`sources.${c.source}`)} />
          </li>
        ))}
      </ul>
      <p className="hint">{t('check.around')}</p>
    </div>
  );
}
