import { useState } from 'react';
import { useI18n } from '../i18n';
import { api } from '../api/client';
import { ErrorText } from '../components/Texts';
import { ALL_DISTRICTS } from '../lib/terrain';

const ROLES = ['farmer', 'manager'];
const EMPTY = { name: '', role: '', region: '', village: '', pin: '' };

// First visit: register (name, role, district, village, PIN) or sign in with name and PIN.
export default function StartScreen({ onDone }) {
  const { t } = useI18n();
  const [mode, setMode] = useState('register');
  const [user, setUser] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key, value) => setUser({ ...user, [key]: value });
  const byName = (a, b) => t(`districts.${a}`).localeCompare(t(`districts.${b}`));

  const pinOk = /^\d{4}$/.test(user.pin);
  const ready = user.name.trim() && pinOk && (mode === 'login' || (user.role && user.region && user.village.trim()));

  async function submit(e) {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const name = user.name.trim();
      onDone(mode === 'login' ? await api.login(name, user.pin) : await api.register({ ...user, name, village: user.village.trim() }));
    } catch (err) {
      setError(err.code);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen start">
      <form className="card start-card" onSubmit={submit}>
        <h2>{t('start.title')}</h2>
        <div className="segmented">
          {['register', 'login'].map((m) => (
            <button type="button" key={m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>{t(`start.${m}`)}</button>
          ))}
        </div>

        <label className="field-label">
          {t('start.name')}
          <input className="input" value={user.name} onChange={(e) => set('name', e.target.value)} autoComplete="username" />
        </label>

        {mode === 'register' && (
          <>
            <div className="field-label">
              {t('start.role')}
              <div className="role-pick">
                {ROLES.map((role) => (
                  <button type="button" key={role} className={user.role === role ? 'role on' : 'role'} onClick={() => set('role', role)}>
                    <b>{t(`role.${role}`)}</b>
                    <span>{t(`role.${role}Hint`)}</span>
                  </button>
                ))}
              </div>
            </div>
            <label className="field-label">
              {t('start.district')}
              <select className="select" value={user.region} onChange={(e) => set('region', e.target.value)}>
                <option value="" disabled>{t('start.choose')}</option>
                {[...ALL_DISTRICTS].sort(byName).map((id) => <option key={id} value={id}>{t(`districts.${id}`)}</option>)}
              </select>
            </label>
            <label className="field-label">
              {t('start.village')}
              <input className="input" value={user.village} onChange={(e) => set('village', e.target.value)} />
            </label>
          </>
        )}

        <label className="field-label">
          {t('start.pin')}
          <input className="input pin" type="password" inputMode="numeric" maxLength="4" value={user.pin}
            onChange={(e) => set('pin', e.target.value.replace(/\D/g, ''))} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          {mode === 'register' && <span className="hint">{t('start.pinHint')}</span>}
        </label>

        <ErrorText code={error} />
        <button className="btn primary block" disabled={!ready || busy}>{busy ? t('common.loading') : t(`start.${mode}Go`)}</button>
      </form>
    </div>
  );
}
