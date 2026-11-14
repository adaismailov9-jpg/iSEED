import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { api } from '../api/client';
import { ErrorText } from '../components/Texts';
import Badge from '../components/Badge';
import { CROP_IDS } from '../data/ids';
import { districtCenter } from '../lib/terrain';
import { fmtInt, fmtPct, fmtShare } from '../lib/format';

// Water manager's tab: the canal is described once (saved on the server), then the season signal for it.
export default function ManagerScreen({ user, onSignOut }) {
  const { t } = useI18n();
  const [loaded, setLoaded] = useState(false);
  const [canal, setCanal] = useState(null); // null = not described yet
  const [editing, setEditing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  function fail(err) {
    if (err.code === 'not_signed_in') onSignOut();
    setError(err.code);
  }

  // The canal saved on the server, if any.
  useEffect(() => {
    api.myCanal().then((res) => setCanal(res.canal)).catch(fail).finally(() => setLoaded(true));
  }, []);

  // Its season signal (POST /manager also saves the canal).
  useEffect(() => {
    setResult(null);
    if (canal) api.manager(canal).then(setResult).catch(fail);
  }, [canal]);

  function saveCanal(next) {
    setError(null);
    setCanal(next);
    setEditing(false);
  }

  if (!loaded) return <div className="screen"><p className="muted">{t('common.loading')}</p></div>;

  if (!canal || editing) {
    const [lat, lon] = districtCenter(user.region);
    const initial = canal ?? { lat, lon, source: 'gravity', normalTurns: 6, mainCrop: 'beans', villages: [{ name: user.village, ha: '' }] };
    return <CanalForm initial={initial} onSave={saveCanal} error={error} />;
  }

  return (
    <div className="screen">
      <section className="card">
        <div className="row top">
          <h2>{t('canal.title')}</h2>
          <button className="btn small" onClick={() => setEditing(true)}>{t('canal.edit')}</button>
        </div>
        <p className="hint">
          {canal.villages.map((v) => v.name).join(', ')} · {t(`canal.${canal.source}`)} · {t('canal.mainCropIs', { crop: t(`crops.${canal.mainCrop}`) })}
        </p>
      </section>

      <ErrorText code={error} />
      {result && <CanalSignal result={result} />}
      {!result && !error && <p className="muted">{t('common.loading')}</p>}
      <SeasonMessageForm user={user} villages={canal.villages} onError={fail} />
    </div>
  );
}

function CanalForm({ initial, onSave, error }) {
  const { t } = useI18n();
  const [canal, setCanal] = useState(initial);
  const set = (key, value) => setCanal({ ...canal, [key]: value });
  const setVillage = (i, key, value) => set('villages', canal.villages.map((v, j) => (j === i ? { ...v, [key]: value } : v)));
  const villagesOk = canal.villages.length > 0 && canal.villages.every((v) => v.name.trim() && Number(v.ha) > 0);
  const ready = villagesOk && Number(canal.normalTurns) > 0;

  function submit(e) {
    e.preventDefault();
    if (!ready) return;
    const villages = canal.villages.map((v) => ({ name: v.name.trim(), ha: Number(v.ha) }));
    onSave({ ...canal, villages, normalTurns: Number(canal.normalTurns) });
  }

  return (
    <div className="screen">
      <form className="card form" onSubmit={submit}>
        <h2>{t('canal.title')}</h2>
        <p className="hint">{t('canal.once')}</p>

        <div className="field-label">
          {t('canal.villages')}
          {canal.villages.map((v, i) => (
            <div key={i} className="village-row">
              <input className="input" value={v.name} onChange={(e) => setVillage(i, 'name', e.target.value)} placeholder={t('canal.villageName')} aria-label={t('canal.villageName')} />
              <input className="input ha" type="number" min="1" value={v.ha} onChange={(e) => setVillage(i, 'ha', e.target.value)} placeholder={t('units.ha')} aria-label={t('canal.villageHa')} />
              {canal.villages.length > 1 && (
                <button type="button" className="btn small" onClick={() => set('villages', canal.villages.filter((_, j) => j !== i))} aria-label={t('canal.remove')}>×</button>
              )}
            </div>
          ))}
          <button type="button" className="btn small" onClick={() => set('villages', [...canal.villages, { name: '', ha: '' }])}>+ {t('canal.addVillage')}</button>
        </div>

        <div className="field-label">
          {t('canal.water')}
          <div className="chips">
            {['gravity', 'pump'].map((id) => (
              <button type="button" key={id} className={canal.source === id ? 'chip on' : 'chip'} onClick={() => set('source', id)}>{t(`canal.${id}`)}</button>
            ))}
          </div>
        </div>
        <label className="field-label">
          {t('canal.turns')}
          <input className="input" type="number" min="1" max="20" value={canal.normalTurns} onChange={(e) => set('normalTurns', e.target.value)} />
        </label>
        <label className="field-label">
          {t('canal.mainCrop')}
          <select className="select" value={canal.mainCrop} onChange={(e) => set('mainCrop', e.target.value)}>
            {CROP_IDS.map((id) => <option key={id} value={id}>{t(`crops.${id}`)}</option>)}
          </select>
        </label>

        <ErrorText code={error} />
        <button className="btn primary block" disabled={!ready}>{t('canal.save')}</button>
      </form>
    </div>
  );
}

function CanalSignal({ result }) {
  const { t, lang } = useI18n();
  const { snow, normalTurns, expectedTurns, totalHa, demandM3, expectedM3, shortM3, enough, positions, mainCrop } = result;
  const m3 = (n) => `${fmtInt(n, lang)} ${t('units.m3')}`;

  return (
    <>
      <section className={`card headline level-${enough ? 'fits' : 'short'}`}>
        <h3><span className="dot" /> {t(enough ? 'canal.enough' : 'canal.notEnough', { crop: t(`crops.${mainCrop}`) })}</h3>
        <p className="hint">{t('canal.water3', { total: m3(expectedM3), need: m3(demandM3), ha: fmtInt(totalHa, lang) })}</p>
        {shortM3 > 0 && <p><b>{t('canal.short', { m3: m3(shortM3) })}</b></p>}
      </section>

      <section className="card">
        <h3>{t('canal.snow')} <Badge source={t('sources.fldas')} /></h3>
        <span className={`snow-chip snow-${snow.level}`}>{t(`levels.${snow.level}`)} · {fmtPct(snow.anomaly)}</span>
        <p className="hint">{t('canal.snowDate', { month: snow.month })}</p>
        {snow.south && <p className="verdict-note">{t('season.south')}</p>}
      </section>

      <section className="card">
        <h3>{t('canal.turnsTitle')} <Badge source={t('canal.turnsSource')} /></h3>
        <div className="turns">
          <div><div className="label">{t('canal.usual')}</div><div className="big">{normalTurns}</div></div>
          <div className="turns-arrow">→</div>
          <div><div className="label">{t('canal.thisYear')}</div><div className="big">{expectedTurns}</div></div>
        </div>
      </section>

      <section className="card">
        <h3>{t('canal.positionsTitle', { crop: t(`crops.${mainCrop}`) })} <Badge source={t('canal.positionSource')} /></h3>
        <table className="compare">
          <tbody>
            {positions.map((p) => (
              <tr key={p.position} className={`level-${p.short ? 'short' : 'fits'}`}>
                <td>{t(`position.${p.position}`)}</td>
                <td className="num">{t('option.water', { pct: fmtShare(p.fit) })}</td>
                <td className="status"><span className="dot" /> {t(p.short ? 'canal.posShort' : 'canal.posOk')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

// The season message for farmers of the canal's villages (POST /manager/message).
function SeasonMessageForm({ user, villages, onError }) {
  const { t } = useI18n();
  const [sent, setSent] = useState(null);
  const [text, setText] = useState('');

  useEffect(() => {
    api.message(user.village).then((res) => {
      setSent(res.message);
      setText(res.message?.text ?? '');
    }).catch(() => {});
  }, [user.village]);

  async function send(e) {
    e.preventDefault();
    try {
      setSent(await api.postMessage(text.trim()));
    } catch (err) {
      onError(err);
    }
  }

  return (
    <form className="card form" onSubmit={send}>
      <h3>{t('message.title')}</h3>
      <p className="hint">{t('message.hint', { villages: villages.map((v) => v.name).join(', ') })}</p>
      <textarea className="input" rows="3" maxLength="280" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('message.placeholder')} />
      <button className="btn primary" disabled={!text.trim() || text.trim() === sent?.text}>{t('message.send')}</button>
      {sent && <p className="hint">✓ {t('message.sent', { date: sent.date })}</p>}
    </form>
  );
}
