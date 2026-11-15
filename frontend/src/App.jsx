import { useEffect, useState } from 'react';
import { api, rememberSession } from './api/client';
import Header from './components/Header';
import TabBar from './components/TabBar';
import FieldScreen from './screens/FieldScreen';
import PlanScreen from './screens/PlanScreen';
import AboutScreen from './screens/AboutScreen';
import AgronomistScreen from './screens/AgronomistScreen';
import ManagerScreen from './screens/ManagerScreen';
import StartScreen from './screens/StartScreen';
import Tour from './components/Tour';
import { MIN_POINTS, centroid, toGeoJSON } from './lib/geo';
import { districtAt } from './lib/terrain';
import { load, save } from './lib/storage';

const TABS = { farmer: ['field', 'plan', 'agro', 'about'], manager: ['canal', 'about'] };
const EMPTY_ANSWERS = { previous: '', previous2: '', plan: '', winterWheat: '', source: '', position: '', normalYear: '', soil: '' };

// The farmer's answers in the shape POST /farmer expects.
function farmerRequest(points, a) {
  return {
    geometry: toGeoJSON(points),
    lastCrops: [a.previous, a.previous2].filter((c) => c && c !== 'none'), // last season first
    plan: a.plan,
    winterWheatSown: a.winterWheat === 'yes',
    source: a.source,
    position: a.source === 'well' ? 'start' : a.position, // a well does not depend on the canal
    normalYear: a.normalYear,
    soil: a.soil,
  };
}

export default function App() {
  const [session, setSession] = useState(load('session', null)); // { token, user: { name, role, region, village } }
  const user = session?.user;
  const [tab, setTab] = useState(user ? TABS[user.role][0] : 'field');
  const [points, setPoints] = useState(load('field', []));
  const [answers, setAnswers] = useState(load('farmerAnswers', EMPTY_ANSWERS));
  const [plans, setPlans] = useState(load('farmerPlans', [])); // results of POST /farmer, kept on the phone
  const [openId, setOpenId] = useState(null);
  const [place, setPlace] = useState(null); // { basin, snow, fieldCheck } of the current field, or { error }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null); // error code of the last request
  const [tour, setTour] = useState(!load('tourDone', false)); // shown once, on the first visit

  const hasField = points.length >= MIN_POINTS;
  const district = hasField ? districtAt(centroid(points)) : null; // picks the district agronomist

  useEffect(() => save('field', points), [points]);
  useEffect(() => save('farmerAnswers', answers), [answers]);
  useEffect(() => save('farmerPlans', plans), [plans]);

  // When the field changes: its river basin with the snow signal, and the field check (slope, greenness, soil).
  useEffect(() => {
    setPlace(null);
    if (!hasField) return;
    let current = true;
    Promise.all([api.basin(...centroid(points)), api.checkField(toGeoJSON(points))])
      .then(([basin, field]) => current && setPlace({ basin: basin.basin, snow: basin.snow, fieldCheck: field.fieldCheck }))
      .catch((err) => current && setPlace({ error: err.code }));
    return () => (current = false);
  }, [points, hasField]);

  // Ask the API for the farmer's options; returns null on error.
  async function askFarmer(input) {
    setBusy(true);
    setError(null);
    try {
      return await api.farmer(input);
    } catch (err) {
      if (err.code === 'not_signed_in') sessionEnded(); // the server forgot the session
      setError(err.code);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function addPlan() {
    const input = farmerRequest(points, answers);
    const result = await askFarmer(input);
    if (!result) return;
    const plan = { id: Date.now(), date: new Date().toISOString().slice(0, 10), input, result };
    setPlans([plan, ...plans]);
    setOpenId(plan.id);
    setTab('plan');
  }

  async function updatePlan(id, changes) {
    const plan = plans.find((p) => p.id === id);
    const input = { ...plan.input, ...changes };
    const result = await askFarmer(input);
    if (result) setPlans((all) => all.map((p) => (p.id === id ? { ...p, input, result } : p)));
  }

  // A saved field becomes the current one; like any new field, the questions start again.
  function chooseField(corners) {
    setPoints(corners);
    setAnswers(EMPTY_ANSWERS);
  }

  function signIn(next) {
    rememberSession(next);
    setSession(next);
    setTab(TABS[next.user.role][0]);
  }

  // The session ran out: sign in again, the field and plans stay for the same person.
  function sessionEnded() {
    rememberSession(null);
    setSession(null);
  }

  // The person signs out (the phone may be shared): end the token on the server and forget this account's field and plans.
  function signOut() {
    api.logout().catch(() => {}); // reads the token before it is cleared below
    sessionEnded();
    setPoints([]);
    setAnswers(EMPTY_ANSWERS);
    setPlans([]);
    setOpenId(null);
  }

  function closeTour() {
    setTour(false);
    save('tourDone', true);
  }

  function deletePlan(id) {
    setPlans(plans.filter((p) => p.id !== id));
    setOpenId(null);
  }

  if (!user) {
    return (
      <div className="app app-start">
        <Header />
        <main className="main"><StartScreen onDone={signIn} /></main>
      </div>
    );
  }

  return (
    <div className="app">
      <Header user={user} onSignOut={signOut} showTour={() => setTour(true)} />
      <TabBar tabs={TABS[user.role]} tab={tab} setTab={setTab} />
      <main className={`main main-${tab}`}>
        {tab === 'field' && (
          <FieldScreen
            points={points}
            setPoints={setPoints}
            plans={plans}
            place={place}
            user={user}
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
            user={user}
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
        {tab === 'canal' && <ManagerScreen user={user} onSignOut={sessionEnded} />}
        {tab === 'about' && <AboutScreen basinId={place?.basin} role={user.role} />}
      </main>
      {tour && <Tour onClose={closeTour} />}
    </div>
  );
}
