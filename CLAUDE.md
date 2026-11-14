# iSEED — shared contracts

Spec: the ТЗ doc "iSEED ТЗ — Technical Specification". If the API table there and this file disagree, this file wins.

## Lanes

- `frontend/` — screens only. No calculation in the browser; every number comes from the API.
- `backend/`, `scripts/`, `data/` — engine, API, NASA data.
- Database lane — a `PostgresStore` with the same methods as `SQLiteStore` in `backend/iseed/storage.py`.
- Frontend and backend meet only at the routes below.

## Run

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn iseed.main:app --reload --port 8000    # API; users go to backend/iseed.db
.venv/bin/python -m pytest                               # engine and API tests
cd frontend && npm install && npm run dev                # VITE_USE_MOCK=false uses the API
```

Data jobs (only to rebuild `data/`; the results are committed):

```bash
python3 scripts/power_job.py     # NASA POWER -> data/climate.json (no login)
python3 scripts/rain_job.py      # NASA GPM IMERG -> data/rain_weeks.json (no login)
cd scripts && ../backend/.venv/bin/pip install earthengine-api numpy   # then: earthengine authenticate
../backend/.venv/bin/python build_basins.py   # HydroBASINS -> data/basins.geojson
../backend/.venv/bin/python snow_job.py       # NASA FLDAS -> data/snow.json
../backend/.venv/bin/python raster_job.py     # SRTM, MODIS NDVI, SoilGrids -> data/grid/
```

## API rules

- JSON, camelCase keys. Errors: `{ "code": "...", "message": "..." }` with codes `bad_input`, `not_signed_in`, `wrong_role`, `wrong_login`, `name_taken`, `no_basin`, `no_field`, `data_missing`.
- Every route answers at `/x` (Vite dev proxy strips `/api`) and at `/api/x` (Vercel).
- Signed-in requests send `Authorization: Bearer <token>`.
- The API returns codes and numbers (`"kind": "saver"`, `"level": "careful"`); the frontend turns codes into text through i18n keys.
- A value that is `null` means "not known here": show "not ready" or "price unknown here", never a made-up number.
- Crop ids: `beans alfalfa maize sugarbeet potato wheat barley safflower`.
- Basin ids: `talas chuy issykkul naryn karadarya syrdarya_south saryjaz alay aksay karkyra`.

## Accounts

- `POST /register` `{ name, role: "farmer" | "manager", region, village, pin: "1234" }` → `{ token, user: { id, name, role, region, village } }`. `409 name_taken`.
- `POST /login` `{ name, pin }` → same. `401 wrong_login`.

A farmer sees the season message of the manager whose village, or one of whose canal villages, has the same name as the farmer's village (case and spaces ignored).

## Field

### POST /fields
Request: `{ "geometry": <GeoJSON Polygon> }` or `{ "lat", "lon", "areaHa" }`. Signed in → saved, and the answer has an `id`.

```json
{ "id": 1, "lat": 42.5205, "lon": 72.3005, "areaHa": 0.91, "elevM": 1268, "basin": "talas",
  "site": { "elevM": 1268, "slopeDeg": 1.5, "greenYears": 12, "bareYears": 0, "ndviYears": 13,
            "sandPct": 30, "clayPct": 22, "cellM": 500, "sources": {...}, "computed": "2026-11-14" },
  "fieldCheck": { "verdict": "good | careful | no",
                  "checks": [{ "id": "slope | green | soil | frost | heavyRain", "level": "good | careful | no", "value": ..., "source": "srtm | modis | soilgrids | farmer | power | imerg" }] },
  "geometry": {...} }
```
`site` describes the ~500 m around the field, not the field alone: say so on screen. `site` and `fieldCheck` are `null` outside the grid. Here `fieldCheck` has slope, greenness and soil; `/farmer` adds frost and heavy rain for the planned crop.

### GET /fields
Signed in → `{ "fields": [ ...as above ] }`.

### GET /basin?lat=&lon=
`{ "basin": "talas", "snow": { ...as GET /snow } }`; `404 no_basin` outside Kyrgyzstan's river basins.

## Farmer

### POST /farmer
Request: the field as `{ "fieldId": 1 }`, or `{ "geometry" }`, or `{ "lat", "lon", "areaHa" }`, plus:
```json
{ "position": "start | middle | end", "source": "gravity | pump | well",
  "normalYear": "enough | sometimes | often | unknown",
  "soil": "sandy | medium | clay | unknown",
  "lastCrops": ["beans", "wheat"], "plan": "beans" }
```
`lastCrops` is last season first; may be empty. `soil` is optional (SoilGrids is the default).

Response:
```json
{ "input": {...},
  "field": { "lat", "lon", "areaHa", "elevM", "basin" },
  "message": { "text": "...", "date": "2026-11-14", "manager": "..." },
  "fieldCheck": { "verdict": "careful", "checks": [...] },
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
                "flowering": { "date": "06-20", "hotDays": 0.3, "tooHot": false },
                "heavyRain": { "maxShare": 0.08, "suggested": "05-13", "riskyWeeks": [] } },
    "pumpGap": null
  }],
  "planEarnsMost": true,
  "basin": "talas",
  "snow": { ...as GET /snow },
  "evidence": { "rules": {...}, "prices": {...}, "climate": {...}, "rain": {...}, "site": {...}, "formula": "..." } }
```
- `options[0]` is always his plan. `saver` and `builder` may be absent (for example when his plan is already the least thirsty crop): show the ones that exist.
- `normal` / `dry`: a normal year and a low-snow year at his place on the canal. `income` is gross income in som for the whole field; `null` when `priceKnown` is false.
- `waterLeftM3` is against his plan; negative = the option takes more water.
- `sowing` is `null` for winter wheat. Dates are `MM-DD`. `heavyRain.maxShare` is the share of years with a day of 20 mm or more in the sowing weeks; `riskyWeeks` are week starts at 30% or more.
- `pumpGap` is `heavy | cut | light | unknown` when the source is a pump, else `null`.
- `message` is `null` when not signed in or no manager has posted for his village.
- `evidence.rules[x]` is `{ value, estimate, source }`: this feeds the "estimate" badges.

## Water manager

### POST /manager
Request: `{ "lat": 42.52, "lon": 72.3, "source": "gravity | pump", "normalTurns": 6, "mainCrop": "beans", "villages": [{ "name": "…", "ha": 120 }] }`. Signed in as a manager → the canal is saved.

Response: `{ s, normalTurns, expectedTurns, totalHa, demandM3, expectedM3, shortM3, enough, mainCrop, basin, positions: [{ position, fit, short }], snow: {...}, evidence }`. `enough` is the headline.

- `GET /manager` → `{ "canal": {...} | null }`, the saved canal of the signed-in manager.
- `POST /manager/message` `{ text }` (1–280 characters, manager only) → `{ text, date }`
- `GET /message?village=` → `{ "message": { text, date, manager } | null }`

## Snow

- `GET /snow?basin=talas` → `{ basin, south, level: "low | normal | high", anomaly, volumeKm3, normalKm3, month: "2026-03", early: { month, anomaly }, terciles: [a, b], replayYear }`. When `south` is true, show the note that reservoirs and interstate agreements matter as much as snow. Call it a signal, never a forecast.
- `GET /hindcast?basin=talas` → the same plus `series: [{ year, volumeKm3, wholeBasinKm3, febKm3, level, short }]` (2001–2026) and `shortYears: [{ year, source }]`.
- `GET /health` → `{ version, data: { climate, snow, rain_weeks } }` (dates computed). `GET /crops` → `{ crops, prices, rules }`.

## Data files (`data/`, committed; the API never calls NASA)

| File | Script | Source |
|---|---|---|
| `climate.json` | `power_job.py` | NASA POWER daily 1981–2025, 0.5° grid; temperature shifted to field height by 6.5 °C per km (estimate) |
| `rain_weeks.json` | `rain_job.py` | NASA GPM IMERG daily 2001–2025 (through the POWER API), same grid |
| `snow.json` | `snow_job.py` | NASA FLDAS monthly snow water, land above 2,000 m, per basin, 2001–2026 |
| `basins.geojson` | `build_basins.py` | HydroBASINS level 5 |
| `grid/*` | `raster_job.py` | NASA SRTM (height, slope), NASA MODIS MOD13Q1 (summer greenness 2013–2025), SoilGrids (sand, clay; not NASA), 0.005° cells |

## Numbers

Every factor is in `backend/iseed/data/rules.json`, `crops.csv`, `prices.json` with its source. Change numbers there, never in code.
