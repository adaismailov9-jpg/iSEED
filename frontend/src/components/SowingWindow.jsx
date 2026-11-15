import { useI18n } from '../i18n';
import { fmtDay, fmtDec, fmtShare } from '../lib/format';
import { SourceBadge } from './Badge';

// When to sow: the safe window, the suggested date away from heavy-rain weeks, and the flowering heat.
export default function SowingWindow({ sowing }) {
  const { t, lang } = useI18n();
  if (!sowing) return <p className="hint">{t('sowing.winter')}</p>;
  const { earliest, latest, fits, flowering } = sowing;
  const heavyRain = sowing.heavyRain ?? null; // absent when the rain data is not built

  return (
    <div className="sowing">
      <div className="label">{t('sowing.title')} <SourceBadge id="power" /></div>
      {fits ? (
        <p>
          <b>{fmtDay(earliest, lang)} – {fmtDay(latest, lang)}</b>
          {heavyRain?.suggested && <> · {t('sowing.best', { date: fmtDay(heavyRain.suggested, lang) })}</>}
        </p>
      ) : (
        <p className="error">{t('sowing.noWindow')}</p>
      )}
      {heavyRain && (
        <div className="weeks">
          <span>{t('sowing.heavyRain', { pct: fmtShare(heavyRain.maxShare) })} <SourceBadge id="imerg" /></span>
          {(heavyRain.riskyWeeks ?? []).map((week) => <span key={week} className="week risky">{t('sowing.riskyWeek', { date: fmtDay(week, lang) })}</span>)}
        </div>
      )}
      {flowering && (
        <p className={flowering.tooHot ? 'verdict-note warn' : 'hint'}>
          {t(flowering.tooHot ? 'sowing.tooHot' : 'sowing.flowering', { date: fmtDay(flowering.date, lang), days: fmtDec(flowering.hotDays, 1, lang) })}
        </p>
      )}
    </div>
  );
}
