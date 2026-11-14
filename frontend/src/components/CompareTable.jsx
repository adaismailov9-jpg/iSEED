import { useI18n } from '../i18n';
import { fmtM3, fmtRatio } from '../lib/format';

// Every crop for this field and this year, best fit first. Tap a crop to check it.
export default function CompareTable({ rows, chosenId, onPick, disabled }) {
  const { t, lang } = useI18n();
  return (
    <table className="compare">
      <thead>
        <tr>
          <th>{t('compare.crop')}</th>
          <th className="num">{t('compare.need')}</th>
          <th className="num">{t('compare.ratio')}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((crop) => (
          <tr key={crop.id} className={`level-${crop.level} ${crop.id === chosenId ? 'chosen' : ''}`}>
            <td>
              <button className="link" onClick={() => onPick(crop.id)} disabled={disabled || crop.id === chosenId}>
                <span className="dot" /> {t(`crops.${crop.id}`)}
              </button>
            </td>
            <td className="num">{fmtM3(crop.needM3, lang)}</td>
            <td className="num">{crop.frostOk ? fmtRatio(crop.ratio, lang) : t('compare.frost')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
