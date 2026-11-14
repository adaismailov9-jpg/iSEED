import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { api } from '../api/client';
import Badge from '../components/Badge';
import { BASINS, nearestBasin } from '../data/demo';
import { SOURCES } from '../data/rules';
import { districtCenter } from '../lib/terrain';
import { fmtPct } from '../lib/format';
import { load, save } from '../lib/storage';

// Water manager's tab: the canal is described once, then the season signal for it.
export default function ManagerScreen({ profile }) {
  const { t } = useI18n();
  const [canal, setCanal] = useState(load('canal', null));
  const [editing, setEditing] = useState(!canal);
  const [result, setResult] = useState(null);

  useEffect(() => {
    setResult(null);
    if (canal) api.manager(canal).then(setResult);
  }, [canal]);

  function saveCanal(next) {
    save('canal', next);
    setCanal(next);
    setEditing(false);
  }

  if (editing) {
    const basin = nearestBasin(...districtCenter(profile.district)).id;
    return <CanalForm initial={canal ?? { villages: profile.village, hectares: '', basin, source: 'river', turns: '5' }} onSave={saveCanal} />;
  }

  return (
    <div className="screen">
      <section className="card">
        <div className="row top">
          <h2>{t('canal.title')}</h2>
          <button className="btn small" onClick={() => setEditing(true)}>{t('canal.edit')}</button>
        </div>
        <p className="hint">
          {canal.villages} · {canal.hectares} {t('units.ha')} · {t(`canal.${canal.source}`)} · {t(`basins.${canal.basin}`)}
        </p>
      </section>

      {!result ? <p className="muted">{t('common.loading')}</p> : <CanalSignal result={result} />}
      <SeasonMessageForm profile={profile} canal={canal} />
    </div>
  );
}

function CanalForm({ initial, onSave }) {
  const { t } = useI18n();
  const [canal, setCanal] = useState(initial);
  const set = (key, value) => setCanal({ ...canal, [key]: value });
  const ready = String(canal.villages).trim() && Number(canal.hectares) > 0 && Number(canal.turns) > 0;

  function submit(e) {
    e.preventDefault();
    if (ready) onSave({ ...canal, villages: canal.villages.trim(), hectares: Number(canal.hectares), turns: Number(canal.turns) });
  }

  return (
    <div className="screen">
      <form className="card form" onSubmit={submit}>
        <h2>{t('canal.title')}</h2>
        <p className="hint">{t('canal.once')}</p>
        <label className="field-label">
          {t('canal.villages')}
          <input className="input" value={canal.villages} onChange={(e) => set('villages', e.target.value)} placeholder={t('canal.villagesHint')} />
        </label>
        <label className="field-label">
          {t('canal.hectares')}
          <input className="input" type="number" min="1" value={canal.hectares} onChange={(e) => set('hectares', e.target.value)} />
        </label>
        <label className="field-label">
          {t('canal.basin')}
          <select className="select" value={canal.basin} onChange={(e) => set('basin', e.target.value)}>
            {BASINS.map((b) => <option key={b.id} value={b.id}>{t(`basins.${b.id}`)}</option>)}
          </select>
        </label>
        <div className="field-label">
          {t('canal.water')}
          <div className="chips">
            {['river', 'pump'].map((id) => (
              <button type="button" key={id} className={canal.source === id ? 'chip on' : 'chip'} onClick={() => set('source', id)}>{t(`canal.${id}`)}</button>
            ))}
          </div>
        </div>
        <label className="field-label">
          {t('canal.turns')}
          <input className="input" type="number" min="1" max="20" value={canal.turns} onChange={(e) => set('turns', e.target.value)} />
        </label>
        <button className="btn primary block" disabled={!ready}>{t('canal.save')}</button>
      </form>
    </div>
  );
}

function CanalSignal({ result }) {
  const { t } = useI18n();
  const { snow, turns, positions } = result;
  return (
    <>
      <section className="card">
        <h3>{t('canal.snow')} {snow.demo && <Badge kind="demo" source={SOURCES.snow} />}</h3>
        <span className={`snow-chip snow-${snow.level}`}>{t(`levels.${snow.level}`)} · {fmtPct(snow.anomaly)}</span>
        <p className="hint">{t('canal.snowDate', { date: snow.date, year: snow.year })}</p>
      </section>

      <section className="card">
        <h3>{t('canal.turnsTitle')} <Badge source={SOURCES.turns} /></h3>
        <div className="turns">
          <div><div className="label">{t('canal.usual')}</div><div className="big">{turns.usual}</div></div>
          <div className="turns-arrow">→</div>
          <div><div className="label">{t('canal.thisYear')}</div><div className="big">{turns.expected}</div></div>
        </div>
      </section>

      <section className="card">
        <h3>{t('canal.shortTitle')} <Badge source={SOURCES.canalPosition} /></h3>
        <table className="compare">
          <thead>
            <tr>
              <th>{t('canal.position')}</th>
              {positions[0].crops.map((c) => <th key={c.id}>{t(`crops.${c.id}`)}</th>)}
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.position}>
                <td>{t(`q.canal_${p.position}`)}</td>
                {p.crops.map((c) => (
                  <td key={c.id} className={`level-${c.level}`}><span className="dot" /> {t(`verdict.${c.level}`)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

// The manager's message for the season. Without a server it reaches farmers on this phone only.
function SeasonMessageForm({ profile, canal }) {
  const { t } = useI18n();
  const [sent, setSent] = useState(load('seasonMessage', null));
  const [text, setText] = useState(sent?.text ?? '');

  function send(e) {
    e.preventDefault();
    const message = { text: text.trim(), from: profile.name, villages: canal.villages, date: new Date().toISOString().slice(0, 10) };
    save('seasonMessage', message);
    setSent(message);
  }

  return (
    <form className="card form" onSubmit={send}>
      <h3>{t('message.title')}</h3>
      <p className="hint">{t('message.hint', { villages: canal.villages })}</p>
      <textarea className="input" rows="3" maxLength="300" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('message.placeholder')} />
      <button className="btn primary" disabled={!text.trim() || text.trim() === sent?.text}>{t('message.send')}</button>
      {sent && <p className="hint">✓ {t('message.sent', { date: sent.date })}</p>}
    </form>
  );
}
