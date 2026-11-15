import { useState } from 'react';
import { useI18n } from '../i18n';
import { api } from '../api/client';
import { ErrorText } from '../components/Texts';
import { ALL_DISTRICTS } from '../lib/terrain';

const ROLES = ['farmer', 'manager'];
const STEPS = 3; // 1: name and role · 2: district and village · 3: phone and PIN
const EMPTY = { name: '', role: '', region: '', village: '', phone: '', pin: '' };
// The character beside the form follows the chosen role.
const ART = { farmer: '/art/farmer-full.webp', manager: '/art/mirab-full.webp' };

// A Kyrgyz number: +996 and 9 digits, or 0 and the same 9 digits (+996 700 123 456 / 0700 123 456).
// The 9 digits start with an operator or city code (2–9), never 0 or 1.
export function phoneProblem(phone) {
  const digits = phone.replace(/\D/g, '');
  const local = digits.startsWith('996') ? digits.slice(3) : digits.startsWith('0') ? digits.slice(1) : digits;
  if (local && !/^[2-9]/.test(local)) return { key: 'phoneStart' };
  if (local.length > 9) return { key: 'phoneLong', n: local.length };
  if (local.length < 9) return { key: 'phoneShort', n: local.length };
  return null;
}

// First visit: register in three short steps, or sign in with name and PIN.
export default function StartScreen({ onDone }) {
  const { t } = useI18n();
  const [mode, setMode] = useState('register');
  const [step, setStep] = useState(1);
  const [user, setUser] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [phoneLeft, setPhoneLeft] = useState(false); // the field was left once: now say what is missing
  const set = (key, value) => setUser({ ...user, [key]: value });
  const byName = (a, b) => t(`districts.${a}`).localeCompare(t(`districts.${b}`));

  const pinOk = /^\d{4}$/.test(user.pin);
  const phoneIssue = phoneProblem(user.phone);
  // "Too short" waits until the farmer leaves the field; a wrong start or too many digits shows at once.
  const showPhoneIssue = phoneIssue && user.phone && (phoneLeft || phoneIssue.key !== 'phoneShort');
  const stepOk = {
    1: user.name.trim() && user.role,
    2: user.region && user.village.trim(),
    3: pinOk && !phoneIssue,
  };
  const ready = mode === 'login' ? user.name.trim() && pinOk : stepOk[1] && stepOk[2] && stepOk[3];
  const character = user.role || 'farmer';

  function switchMode(next) {
    setMode(next);
    setStep(1);
    setError(null);
  }

  async function submit(e) {
    e.preventDefault();
    if (mode === 'register' && step < STEPS) {
      if (stepOk[step]) setStep(step + 1);
      return;
    }
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const name = user.name.trim();
      // The phone number is for the demo only: it is not sent or saved (no SMS in this prototype).
      const account = { name, role: user.role, region: user.region, village: user.village.trim(), pin: user.pin };
      onDone(mode === 'login' ? await api.login(name, user.pin) : await api.register(account));
    } catch (err) {
      setError(err.code);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="start">
      <figure className="start-art" aria-hidden="true">
        <img key={character} src={ART[character]} alt="" className={`start-character start-${character}`} />
        <p key={`say-${character}`} className="start-bubble">{t(`start.say.${character}`)}</p>
      </figure>

      <form className="card start-card" onSubmit={submit}>
        <h2>{t('start.title')}</h2>
        <div className="segmented">
          {['register', 'login'].map((m) => (
            <button type="button" key={m} className={mode === m ? 'on' : ''} onClick={() => switchMode(m)}>{t(`start.${m}`)}</button>
          ))}
        </div>

        {mode === 'register' && (
          <ol className="start-steps" aria-label={t('start.stepOf', { n: step, of: STEPS })}>
            {[1, 2, 3].map((n) => (
              <li key={n} className={n === step ? 'on' : n < step ? 'done' : ''}>
                <button type="button" onClick={() => n < step && setStep(n)} disabled={n >= step}>
                  <span className="step-dot">{n < step ? '✓' : n}</span>
                  <span className="step-name">{t(`start.step${n}`)}</span>
                </button>
              </li>
            ))}
          </ol>
        )}

        {(mode === 'login' || step === 1) && (
          <label className="field-label">
            {t('start.name')}
            <input className="input" value={user.name} onChange={(e) => set('name', e.target.value)} autoComplete="username" />
          </label>
        )}

        {mode === 'register' && step === 1 && (
          <div className="field-label">
            {t('start.role')}
            <div className="role-pick">
              {ROLES.map((role) => (
                <button type="button" key={role} className={user.role === role ? 'role on' : 'role'} onClick={() => set('role', role)} aria-pressed={user.role === role}>
                  <b>{t(`role.${role}`)}</b>
                  <span>{t(`role.${role}Hint`)}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {mode === 'register' && step === 2 && (
          <>
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
              <span className="hint">{t(user.role === 'manager' ? 'start.villageManager' : 'start.villageFarmer')}</span>
            </label>
          </>
        )}

        {mode === 'register' && step === 3 && (
          <label className="field-label">
            {t('start.phone')}
            <input className="input" type="tel" inputMode="tel" value={user.phone} maxLength="20"
              onChange={(e) => set('phone', e.target.value.replace(/[^\d+ ]/g, ''))} onBlur={() => setPhoneLeft(true)}
              placeholder="+996 700 123 456" autoComplete="tel" aria-invalid={Boolean(showPhoneIssue)} aria-describedby="phone-rule" />
            <span id="phone-rule" className={showPhoneIssue ? 'hint error' : 'hint'}>
              {showPhoneIssue ? t(`start.${phoneIssue.key}`, { n: phoneIssue.n }) : t('start.phoneRule')}
            </span>
            <span className="demo-note">{t('start.phoneDemo')}</span>
          </label>
        )}

        {(mode === 'login' || step === 3) && (
          <label className="field-label">
            {t('start.pin')}
            <input className="input pin" type="password" inputMode="numeric" maxLength="4" value={user.pin}
              onChange={(e) => set('pin', e.target.value.replace(/\D/g, ''))} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
            {mode === 'register' && <span className="hint">{t('start.pinHint')}</span>}
          </label>
        )}

        <ErrorText code={error} />
        <div className="start-actions">
          {mode === 'register' && step > 1 && (
            <button type="button" className="btn" onClick={() => setStep(step - 1)}>{t('start.back')}</button>
          )}
          {mode === 'register' && step < STEPS ? (
            <button className="btn primary grow" disabled={!stepOk[step]}>{t('start.next')}</button>
          ) : (
            <button className="btn primary grow" disabled={!ready || busy}>{busy ? t('common.loading') : t(`start.${mode}Go`)}</button>
          )}
        </div>
      </form>
    </div>
  );
}
