import { useState } from 'react';
import { useI18n } from '../i18n';
import { ALL_DISTRICTS } from '../lib/terrain';

export const ROLES = ['farmer', 'manager'];

// First visit: who is using the phone. Kept on the phone only (no accounts yet).
export default function StartScreen({ onDone }) {
  const { t } = useI18n();
  const [profile, setProfile] = useState({ name: '', role: '', district: '', village: '' });
  const set = (key, value) => setProfile({ ...profile, [key]: value });
  const ready = profile.name.trim() && profile.role && profile.district;
  const byName = (a, b) => t(`districts.${a}`).localeCompare(t(`districts.${b}`));

  function submit(e) {
    e.preventDefault();
    if (ready) onDone({ ...profile, name: profile.name.trim(), village: profile.village.trim() });
  }

  return (
    <div className="screen start">
      <form className="card start-card" onSubmit={submit}>
        <h2>{t('start.title')}</h2>
        <p className="hint">{t('start.hint')}</p>

        <label className="field-label">
          {t('start.name')}
          <input className="input" value={profile.name} onChange={(e) => set('name', e.target.value)} autoComplete="name" />
        </label>

        <div className="field-label">
          {t('start.role')}
          <div className="role-pick">
            {ROLES.map((role) => (
              <button type="button" key={role} className={profile.role === role ? 'role on' : 'role'} onClick={() => set('role', role)}>
                <b>{t(`role.${role}`)}</b>
                <span>{t(`role.${role}Hint`)}</span>
              </button>
            ))}
          </div>
        </div>

        <label className="field-label">
          {t('start.district')}
          <select className="select" value={profile.district} onChange={(e) => set('district', e.target.value)}>
            <option value="" disabled>{t('start.choose')}</option>
            {[...ALL_DISTRICTS].sort(byName).map((id) => <option key={id} value={id}>{t(`districts.${id}`)}</option>)}
          </select>
        </label>

        <label className="field-label">
          {t('start.village')}
          <input className="input" value={profile.village} onChange={(e) => set('village', e.target.value)} />
        </label>

        <button className="btn primary block" disabled={!ready}>{t('start.go')}</button>
        <p className="hint">{t('start.local')}</p>
      </form>
    </div>
  );
}
