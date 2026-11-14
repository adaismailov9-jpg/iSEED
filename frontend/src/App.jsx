import { useEffect, useState } from 'react';
import { useI18n } from './i18n';
import { api } from './api/client';
import Header from './components/Header';
import TabBar from './components/TabBar';
import FieldScreen from './screens/FieldScreen';
import PlanScreen from './screens/PlanScreen';
import AboutScreen from './screens/AboutScreen';
import AgronomistScreen from './screens/AgronomistScreen';
import { MIN_POINTS, centroid, toGeoJSON } from './lib/geo';
import { districtAt } from './lib/terrain';
import { load, save } from './lib/storage';

const EMPTY_ANSWERS = { previous: '', source: '', well: '', soil: '', priority: '' };

export default function App() {
  const { lang } = useI18n();
  const [tab, setTab] = useState('field');
  const [points, setPoints] = useState(load('field', []));
  const [answers, setAnswers] = useState(load('answers', EMPTY_ANSWERS));
  const [plans, setPlans] = useState(load('plans', [])); // the planting plan, kept on the phone
  const [openId, setOpenId] = useState(null);
  const [basin, setBasin] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  const hasField = points.length >= MIN_POINTS;
  const district = hasField ? districtAt(centroid(points)) : null; // picks the district agronomist

  useEffect(() => save('field', points), [points]);
  useEffect(() => save('answers', answers), [answers]);
  useEffect(() => save('plans', plans), [plans]);

  // Look up the basin when the field changes.
  useEffect(() => {
    setBasin(null);
    if (hasField) api.getBasin(...centroid(points)).then(setBasin);
  }, [points, hasField]);

  // Ask the API for a verdict; returns null on error.
  async function check(input) {
    setBusy(true);
    setError(false);
    try {
      return await api.check(input, lang);
    } catch {
      setError(true);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function addPlan() {
    const { previous, source, well, soil, priority } = answers;
    const input = { geometry: toGeoJSON(points), previous, source, well, soil, priority, season: 'current' };
    const result = await check(input);
    if (!result) return;
    const plan = { id: Date.now(), date: new Date().toISOString().slice(0, 10), input, result };
    setPlans([plan, ...plans]);
    setOpenId(plan.id);
    setTab('plan');
  }

  async function updatePlan(id, changes) {
    const plan = plans.find((p) => p.id === id);
    const input = { ...plan.input, ...changes };
    const result = await check(input);
    if (result) setPlans((all) => all.map((p) => (p.id === id ? { ...p, input, result } : p)));
  }

  // A saved field becomes the current one; like any new field, the questions start again.
  function chooseField(corners) {
    setPoints(corners);
    setAnswers(EMPTY_ANSWERS);
  }

  function deletePlan(id) {
    setPlans(plans.filter((p) => p.id !== id));
    setOpenId(null);
  }

  return (
    <div className="app">
      <Header />
      <TabBar tab={tab} setTab={setTab} />
      <main className={`main main-${tab}`}>
        {tab === 'field' && (
          <FieldScreen
            points={points}
            setPoints={setPoints}
            plans={plans}
            basin={basin}
            answers={answers}
            setAnswers={setAnswers}
            resetAnswers={() => setAnswers(EMPTY_ANSWERS)}
            onSubmit={addPlan}
            busy={busy}
            error={error}
          />
        )}
        {tab === 'plan' && (
          <PlanScreen
            plans={plans}
            openId={openId}
            setOpenId={setOpenId}
            updatePlan={updatePlan}
            deletePlan={deletePlan}
            busy={busy}
            error={error}
            goField={() => setTab('field')}
          />
        )}
        {tab === 'agro' && (
          <AgronomistScreen
            hasField={hasField}
            district={district}
            points={points}
            plans={plans}
            chooseField={chooseField}
            goField={() => setTab('field')}
          />
        )}
        {tab === 'about' && <AboutScreen basinId={basin?.id} />}
      </main>
    </div>
  );
}
