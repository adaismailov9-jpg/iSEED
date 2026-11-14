# iSEED — shared contracts

Spec: the ТЗ doc "iSEED ТЗ — Technical Specification". If the API table there and this file disagree, this file wins.

## Lanes

- `frontend/` — screens only. No calculation in the browser; every number comes from the API.
- `backend/`, `scripts/`, `data/` — engine, API, NASA data.
- Frontend and backend meet only at the routes below.

## Run

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn iseed.main:app --reload --port 8000    # API
.venv/bin/python -m pytest                               # engine tests
cd frontend && npm install && npm run dev                # VITE_USE_MOCK=false uses the API
python3 scripts/power_job.py                             # NASA POWER -> data/climate.json
cd scripts && ../backend/.venv/bin/python snow_job.py    # FLDAS (Earth Engine login needed) -> data/snow.json
```

## API rules

- JSON, camelCase keys. Errors: `{ "code": "bad_input" | "data_missing" | ..., "message": "..." }`.
- Every route answers at `/x` (Vite dev proxy strips `/api`) and at `/api/x` (Vercel).
- `503 data_missing` means the NASA file for that answer is not built yet. Show "not ready", never a made-up number.
- The API returns codes and numbers (`"kind": "saver"`, `"pumpGap": "heavy"`); the frontend turns codes into text through i18n keys.
- Crop ids: `beans alfalfa maize sugarbeet potato wheat barley safflower`.

## Routes that work now

### GET /health
`{ "version": "0.1.0", "data": { "climate": "2026-11-14", "snow": null } }` — dates the data files were computed; `null` = not built.

### GET /crops
`{ "crops": [{ id, family, fixesN, winter, perennial, days, needMm, ky, minSowTempC, daysToFlower, source }], "prices": {...}, "rules": {...} }`
Each rule is `{ value, estimate, source }`: this feeds the "estimate" badges.

### POST /farmer
Request:
```json
{ "lat": 42.52, "lon": 72.24, "elevM": 1237, "areaHa": 2.0, "basin": "talas",
  "position": "start | middle | end", "source": "gravity | pump | well",
  "normalYear": "enough | sometimes | often | unknown",
  "lastCrops": ["beans", "wheat"], "plan": "beans" }
```
`elevM` (field height, metres) is optional but matters: without it frost dates are for the mountain-averaged POWER cell. `lastCrops` is last season first; may be empty. `basin` is optional.

Response:
```json
{ "input": { ... },
  "options": [{
    "kind": "plan | saver | builder", "crop": "beans", "highlight": false,
    "netNeedMm": 344.5,
    "normal": { "fit": 0.99, "yieldFactor": 0.989, "supplyMm": 341.1, "income": { "low": 148275, "high": 363768 } },
    "dry":    { "fit": 0.495, "yieldFactor": 0.419, "supplyMm": 170.5, "income": { "low": 62888, "high": 154284 } },
    "priceKnown": true,
    "waterLeftM3": 0,
    "soil": { "nitrogen": true, "bareMonths": 8, "rotation": "warning | plus | none" },
    "frostOk": true,
    "sowing": { "earliest": "05-06", "latest": "06-24", "fits": true,
                "flowering": { "date": "06-20", "hotDays": 0.3, "tooHot": false } },
    "pumpGap": null
  }],
  "planEarnsMost": true,
  "snow": null,
  "evidence": { "rules": {...}, "prices": {...}, "climate": {...}, "formula": "..." } }
```
- `options[0]` is always his plan. `saver` and `builder` may be absent (for example when his plan is already the least thirsty crop): show the ones that exist.
- `income` is gross income in som for the whole field; `null` when `priceKnown` is false → show "price unknown here".
- `waterLeftM3` is against his plan; negative = the option takes more water.
- `sowing` is `null` for winter wheat and crops with no sowing temperature. Dates are `MM-DD`.
- `pumpGap` is `heavy | cut | light | unknown` when the source is a pump, else `null`.
- `basin` and `snow` (same shape as GET /snow) are found from `lat`, `lon`; `null` outside the basins.

### POST /manager
Request: `{ "basin": "talas", "lat": 42.52, "lon": 72.24, "elevM": 1237, "source": "gravity | pump", "normalTurns": 6, "mainCrop": "beans", "villages": [{ "name": "…", "ha": 120 }] }`

Response: `{ s, normalTurns, expectedTurns, totalHa, demandM3, expectedM3, shortM3, enough, mainCrop, positions: [{ position, fit, short }], snow: {...}, evidence }`
`enough` is the headline. `basin` is optional: it is found from `lat`, `lon`.

### GET /basin?lat=&lon=
`{ "basin": "talas", "snow": { ...as GET /snow } }`; `404 no_basin` outside Kyrgyzstan's river basins.
Basin ids: `talas chuy issykkul naryn karadarya syrdarya_south saryjaz alay aksay karkyra`. When `snow.south` is true, show the note that reservoirs and interstate agreements matter as much as snow.

### GET /snow?basin=talas and GET /hindcast?basin=talas
Real FLDAS data, March 2001-2026. Shapes are the `snow.json` basin entry below (`/snow` without `series`).

## Routes not built yet (shape agreed, mock them)

- `POST /register` `{ name, role: "farmer" | "manager", region, village, pin }` → `{ token, user: { id, name, role, region, village } }`
- `POST /login` `{ name, pin }` → same. Later requests send `Authorization: Bearer <token>`.
- `POST /fields` `{ geometry: <GeoJSON Polygon> }` or `{ lat, lon, areaHa }` → `{ id, areaHa, lat, lon, elevM, basin, fieldCheck: null | { verdict: "good | careful | no", checks: [{ id, level, value }] } }`
- `POST /manager/message` `{ text }` (max 280) → `{ text, date }`
- `GET /message?village=` → `{ text, date, manager }` or `null`

## Data files (`data/`, committed; the API never calls NASA)

- `climate.json` — `scripts/power_job.py`, NASA POWER 1981–2025. `{ source, window, note, computed, seasonDays, cells: [{ lat, lon, cellElevM, seasonRainMm, bands: [{ elevM, lastSpringFrostDoy, firstAutumnFrostDoy, frostFreeDays, lastSpringFrostByYear, weekFrostShare[52], weekHotDays[52], weekMeanTempC[52] }] }] }`
- `basins.geojson` — `scripts/build_basins.py`, HydroBASINS level 5.
- `snow.json` — `scripts/snow_job.py`, NASA FLDAS snow water, land above 2,000 m. `{ source, note, normal, shortYears, computed, basins: { "<id>": { basin, level: "low | normal | high", anomaly, volumeKm3, normalKm3, month, early: { month, anomaly }, terciles: [a, b], replayYear, series: [{ year, volumeKm3, level, short }] } } }`

## Numbers

Every factor is in `backend/iseed/data/rules.json`, `crops.csv`, `prices.json` with its source. Change numbers there, never in code.
