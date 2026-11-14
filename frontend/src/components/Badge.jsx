import { useState } from 'react';
import { useI18n } from '../i18n';

// Grey "estimate" / orange "demo data" badge. Tap it to see the source.
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
