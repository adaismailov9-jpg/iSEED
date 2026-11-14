# iSEED — frontend

React 18 + Vite, Leaflet. Kyrgyz by default, Russian and English. Works on phones, tablets, laptops and desktops.

## Run

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # checks that ky.json and en.json match, then builds to dist/
```

The app uses a **built-in mock API** (`src/api/mock.js`) with demo snow, basin and climate numbers,
labelled "demo data" in the UI. To use the FastAPI backend: `.env.local` → `VITE_USE_MOCK=false`
(`/api/*` is proxied to `localhost:8000` in dev).

## Screens

1. **Field** — search a village (Photon on OpenStreetMap data, Kyrgyzstan only, up to 3 suggestions while typing),
   switch satellite / ordinary map, tap the map where the field is (a 1 ha field with 4 corners appears)
   or use "I'm on my field". A new or cleared field resets the questions.
   Only Kyrgyzstan: other countries are masked and the map can't be moved away. A field is refused (with a warning)
   outside Kyrgyzstan (incl. the neighbours' enclaves), on the main lakes and reservoirs, or above 3,000 m
   (`src/lib/terrain.js`). Border: `src/data/kyrgyzstan.json` (geoBoundaries / OpenStreetMap, ODbL);
   water: `src/data/water.json` (8 main lakes and reservoirs, OpenStreetMap, ODbL); height: Open-Meteo Elevation API. Drag a corner to move it, drag the dot in the
   middle of an edge to add a corner, tap a corner to remove it. The area updates while you drag.
   Step-by-step questions (one open at a time): previous crop → water source → (well enough?) → soil → priority
   (saving water / income / soil health) → "Pick a crop and add to plan".
2. **Planting plan** — every saved field (kept in localStorage, opens offline). The engine recommends a crop:
   season long enough → enough water → good rotation after the previous crop → the priority. A plan shows the verdict,
   2026 vs. 2023 (low snow) switch, two other options (tap "Choose" to switch), compare table, evidence.
3. **Agronomists** — the agronomist of the field's district is picked automatically (`districtAt` in
   `src/lib/terrain.js`; districts: `src/data/districts.json`, geoBoundaries ADM2, CC BY-SA 3.0). Any other district
   can be chosen; ministry hotline 1210. Contacts in `src/data/agronomists.js` are DEMO numbers with the
   non-existent code (000) — replace them with the ministry's list.
4. **About the data** — snow chart 2003–2026 with shortage years marked, data sources.

Layout: on phones the tabs are at the bottom and the questions are under the map; from 900 px wide the tabs become
a menu on the left, the questions sit to the left of the map and a plan opens in two columns.
Visual style: cream background, forest-green pill buttons, sage search bar, clay "add to plan" button, Manrope font.

## Files

```
src/
  App.jsx            state: field, answers, verdict; calls the API
  api/               client.js (mock or real backend), mock.js (same JSON as the backend)
  engine/engine.js   the deterministic rules from spec section 4 (used by the mock)
  data/              crops, rules, demo snow + climate
  i18n/              ky.json, en.json, translate()
  lib/               geo (area, corners), format (numbers), storage (localStorage)
  components/        FieldMap, Questions, Verdict, Alternatives, CompareTable, Evidence, HindcastChart…
  screens/           FieldScreen, CheckScreen, AboutScreen
```
