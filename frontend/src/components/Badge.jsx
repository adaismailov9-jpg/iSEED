import { useState } from 'react';
import { useI18n } from '../i18n';

// Grey "estimate" / orange "demo data" / green data-source badge. Tap it to see the source.
// "estimate" is only for numbers that are a guess (canal losses, turns, prices, FAO typical values);
// numbers computed from NASA data get a SourceBadge instead.
// `label` replaces the badge text (e.g. "NASA SRTM" for a data source).
export default function Badge({ kind = 'estimate', source, label }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <span className="badge-wrap">
      <button className={`badge badge-${kind}`} onClick={() => setOpen(!open)}>
        {label ?? t(`badge.${kind}`)}
      </button>
      {open && (
        <span className="badge-pop">
          <b>{t('badge.source')}:</b> {source}
        </span>
      )}
    </span>
  );
}

// A data source by its id in `sources.*`: shows "NASA POWER", tap for the full line.
export function SourceBadge({ id }) {
  const { t } = useI18n();
  const full = t(`sources.${id}`);
  return <Badge kind="source" label={full.split(' — ')[0]} source={full} />;
}
