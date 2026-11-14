# iSEED — frontend

React 18 + Vite, Leaflet. Kyrgyz by default, Russian and English. Works on phones, tablets, laptops and desktops.

## Run

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # checks that ky.json and en.json match, then builds to dist/
```

The app has no calculations of its own: every number comes from the iSEED API (`backend/`, shapes in `../CLAUDE.md`).
Start the API first (`uvicorn iseed.main:app --port 8000`); in dev `/api/*` is proxied to it.

## Screens

0. **Start** — sign up (name, farmer / water manager, district, village, 4-digit PIN) or sign in with name and PIN
   (`POST /register`, `/login`). The token is kept on the phone; the role decides the tabs.
1. **Field** (farmer) — search a village, tap the map (a 1 ha field appears), drag the corners. Fields are refused
   outside Kyrgyzstan, on the main lakes or above 3,000 m (`src/lib/terrain.js`). The card shows the river basin
   with the snow signal (`GET /basin`) and the field check: slope, summer greenness, soil (`POST /fields`, not saved).
   Questions in the shape of `POST /farmer`: last crop → planned crop → winter wheat sown? → water source →
   place on the canal (canal or pump) → is water enough in a normal year → soil.
2. **Planting plan** (farmer) — results of `POST /farmer`, kept in localStorage. The list shows his plan and the other
   options (water saver, soil builder) with "Choose". A result shows the options side by side (water and gross
   income in a normal and a dry year, water left in the canal, soil, pump warning, sowing window with heavy-rain
   weeks and flowering heat), "two crops in one year", the field check, the season (snow, dry year, frost trend),
   the evidence, share as PDF / WhatsApp / Telegram / copy.
3. **Agronomists** (farmer) — the district agronomist (DEMO numbers with the non-existent code 000).
4. **Canal** (water manager) — the canal is described once (`POST /manager`, saved on the server): villages with
   hectares, gravity or pump, usual irrigation turns, main crop. Then: enough water or not, snow vs normal,
   expected turns, which canal positions fall short, and the season message to farmers (`POST /manager/message`;
   farmers of those villages see it).
5. **About the data** — March snow water per basin 2001–2026 (`GET /hindcast`) with shortage years and the MODIS check,
   data sources.

Layout: on phones the tabs are at the bottom and the questions are under the map; from 900 px wide the tabs become
a menu on the left, the questions sit to the left of the map and a plan opens in two columns.
Visual style: fresh green, sun yellow, warm orange; light and dark theme (moon / sun button in the header), Manrope font.

## Files

```
src/
  App.jsx            session, field, answers, plans; calls the API
  api/client.js      the API routes, token, error codes
  data/              ids (crops, basins), districts, border, lakes, demo agronomists
  i18n/              ky.json, ru.json, en.json, translate()
  lib/               geo (area, corners), terrain (Kyrgyzstan, lakes, height, district), format, storage
  components/        FieldMap, Questions, OptionCard, SowingWindow, FieldCheck, Evidence, HindcastChart, PlanShare, Tour…
  screens/           Start, Field, Plan, Agronomist, Manager, About
```
