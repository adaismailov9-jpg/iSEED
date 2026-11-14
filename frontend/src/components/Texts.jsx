import { useI18n } from '../i18n';
import { fmtInt } from '../lib/format';

// An API error code in words; unknown codes get the general "something went wrong".
export function ErrorText({ code }) {
  const { t } = useI18n();
  if (!code) return null;
  return <p className="error">{t(`errors.${code}`, {}, 'errors.server')}</p>;
}

// Water an option leaves in the canal compared with the farmer's plan (negative = takes more).
export function waterLeftText(m3, t, lang) {
  return t(m3 >= 0 ? 'option.waterLeft' : 'option.waterMore', { m3: fmtInt(Math.abs(m3), lang) });
}
