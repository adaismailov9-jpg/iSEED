import { useI18n } from '../i18n';
import Icon from './Icon';
import { areaHa, centroid, fromGeoJSON, toGeoJSON } from '../lib/geo';
import { districtAt } from '../lib/terrain';
import { fmtDec } from '../lib/format';

// Fields from the planting plan, each listed once. Tap one to make it the current field.
export default function SavedFields({ plans, points, onPick }) {
  const { t, lang } = useI18n();
  const current = points.length ? JSON.stringify(toGeoJSON(points)) : '';
  const seen = new Set();
  const fields = plans
    .map((plan) => JSON.stringify(plan.input.geometry))
    .filter((key) => !seen.has(key) && seen.add(key));

  if (fields.length === 0) return null;
  return (
    <div className="saved-fields">
      <div className="label">{t('field.saved')}</div>
      <div className="chips">
        {fields.map((key) => {
          const corners = fromGeoJSON(JSON.parse(key));
          return (
            <button key={key} className={key === current ? 'chip on' : 'chip'} onClick={() => onPick(corners)}>
              <Icon name="pin" size={16} />
              {fmtDec(areaHa(corners), 2, lang)} {t('units.ha')} · {t(`districts.${districtAt(centroid(corners))}`)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
