import { useI18n } from '../i18n';
import { fmtDay, fmtDec, fmtShare } from '../lib/format';
import Badge from './Badge';

// When to sow: the safe window, the suggested date away from heavy-rain weeks, and the flowering heat.
export default function SowingWindow({ sowing }) {
  const { t, lang } = useI18n();
  if (!sowing) return <p className="hint">{t('sowing.winter')}</p>;
  const { earliest, latest, fits, flowering, heavyRain } = sowing;

  return (
    <div className="sowing">
      <div className="label">{t('sowing.title')} <Badge source={t('sources.power')} /></div>
      {fits ? (
        <p><b>{fmtDay(earliest, lang)} – {fmtDay(latest, lang)}</b> · {t('sowing.best', { date: fmtDay(heavyRain.suggested, lang) })}</p>
      ) : (
        <p className="error">{t('sowing.noWindow')}</p>
      )}
      <div className="weeks">
        <span>{t('sowing.heavyRain', { pct: fmtShare(heavyRain.maxShare) })} <Badge source={t('sources.imerg')} /></span>
        {heavyRain.riskyWeeks.map((week) => <span key={week} className="week risky">{t('sowing.riskyWeek', { date: fmtDay(week, lang) })}</span>)}
      </div>
      {flowering && (
        <p className={flowering.tooHot ? 'verdict-note warn' : 'hint'}>
          {t(flowering.tooHot ? 'sowing.tooHot' : 'sowing.flowering', { date: fmtDay(flowering.date, lang), days: fmtDec(flowering.hotDays, 1, lang) })}
        </p>
      )}
    </div>
  );
}
