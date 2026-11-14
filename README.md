# iSEED

NASA Space Apps Bishkek 2026, challenge "Field Shift: Adapting Farms with NASA Data".

## The problem

In Kyrgyzstan irrigation water comes from mountain snow. A water manager shares it between villages by turns, and in a low-snow year the fields at the end of the canal run short first. In January 2026 the ministry warned of a shortage and told farmers to plant less thirsty crops, with no numbers: not how short, not for which basin, not which crops.

## What iSEED does

Two users, one set of NASA numbers.

- **Water manager** — sees how the snow in his river basin compares with a normal year, how many water turns to expect, and which places on his canal fall short. He posts a short season message to the farmers in his villages.
- **Farmer** — draws his field, answers a few questions and gets three options for next season: his own plan, a water-saver and a soil-builder. Each shows gross income in a normal and a low-snow year, the water it leaves in the canal for the farmers at the end, a sowing window and a field check.

iSEED is a risk signal, not a forecast: it never predicts river flow, a storm or a price.

## What the data shows

- Snow water in March 2026 was below normal in every basin of Kyrgyzstan: Talas −20%, Naryn −31%, Chüy −41%, Issyk-Kul −49%.
- FLDAS marks 2021 as a low-snow year in Talas and Chüy. In June 2021 farmers in Chüy protested over the lack of irrigation water (24.kg).
- The satellite check agrees only partly. MODIS March snow cover above 2,000 m correlates with the FLDAS volume at r = 0.45 in Talas and 0.43 in Chüy (0.42–0.82 across basins), and it does not mark 2021 as low. Cover is not depth: in March most land above 2,000 m is white in any year. So the snow signal is not yet validated.
- A typical low-snow year in Talas has half the normal snow water.

## NASA data

Everything is pulled by the scripts in `scripts/` and committed under `data/`. The API never calls NASA at request time.

| Data | Product | Used for | Script → file |
|---|---|---|---|
| Snow water | NASA FLDAS Noah, monthly, 0.1° (`NASA/FLDAS/NOAH01/C/GL/M/V001`, `SWE_inst`) | Snow volume per basin, March 2001–2026 | `snow_job.py` → `snow.json` |
| Snow cover | NASA MODIS MOD10A1 v6.1, daily, 500 m | Satellite check on FLDAS | `modis_job.py` → `snow_check.json` |
| Temperature | NASA POWER daily, `T2M_MAX`, `T2M_MIN`, 1981–2025 | Frost dates, sowing window, hot weeks | `power_job.py` → `climate.json` |
| Rain | NASA POWER `PRECTOTCORR`; NASA GPM IMERG daily 2001–2025 | Crop water need; heavy-rain weeks | `power_job.py`, `rain_job.py` → `rain_weeks.json` |
| Terrain | NASA SRTM, 30 m | Field height and slope | `raster_job.py` → `grid/` |
| Greenness | NASA MODIS MOD13Q1 v6.1, 250 m, 2013–2025 | Has the land been green in summer? | `raster_job.py` → `grid/` |
| Soil | SoilGrids 2.0, ISRIC (not NASA), CC BY 4.0 | Default soil texture | `raster_job.py` → `grid/` |
| Basins | HydroBASINS level 5, HydroSHEDS (not NASA), free with attribution | Which basin a field is in | `build_basins.py` → `basins.geojson` |

NASA data is open; we cite NASA POWER, FLDAS (NASA GSFC / GES DISC), MODIS (NSIDC, LP DAAC), SRTM and GPM. FLDAS, MODIS, SRTM, SoilGrids and HydroBASINS are read through Google Earth Engine.

## How the numbers are made

All rules are in `backend/iseed/engine.py`. Every factor is in `backend/iseed/data/rules.json`, `crops.csv` and `prices.json` with its source, and is marked as an estimate where it is one.

**Snow signal, per basin**

```
volume (km³)  = Σ over pixels above 2,000 m:  SWE (mm) ÷ 1,000 × pixel area (m²) ÷ 10⁹
normal        = mean March volume, 2001–2025
anomaly       = (this March − normal) ÷ normal
level         = low / normal / high by the terciles of 2001–2025
```

Only land above 2,000 m is counted because several basins run far into the lowlands of Kazakhstan and Uzbekistan.

**From snow to water on a field**

```
S (season)   = 1 + 0.5 × anomaly, kept between 0.5 and 1.1
               pump on a big river: S = 1 − 0.5 × (1 − S);   well: S = 1
P (position) = share of the allocation reaching the field: start 1.0, middle 1.0 → 0.85, end 0.9 → 0.6
               (normal year → low-snow year, a straight line between S = 1 and S = 0.75)
need         = Σ over the crop's season:  Kc (FAO-56) × ET0                (mm)
               ET0 by Hargreaves from NASA POWER daily Tmax, Tmin and latitude, 2001–2025
net need     = need − 0.7 × rain over the same days                      (mm)
supply       = net need of his usual crop × A × S × P                    (A: is water enough in a normal year?)
fit          = min(1, supply ÷ net need of the crop)
yield        = 1 − Ky × (1 − fit)                                        (FAO Irrigation and Drainage Paper 33)
income       = yield (t/ha) × price × hectares                           (gross; costs are not counted)
water left   = (net need of his plan − net need of the option) × ha × 10 ÷ 0.6
```

The factor 0.5 in S says that half of a snow deficit shows up as a water deficit; glaciers, rain and reservoirs supply the rest. It is set so that a typical low-snow year in Talas and Chüy (50% below normal in FLDAS) gives S = 0.75.

**Sowing window** — earliest: after the last spring frost in 9 years out of 10, once the weekly mean temperature reaches the crop's minimum. Latest: the crop still matures before the first autumn frost in 9 years out of 10.

**Frost trend** — the last spring frost date of each year 1981–2025, tested with Mann–Kendall; a change is reported only when p < 0.05.

**Two crops in one year** — winter wheat, then a short crop, offered only where the days between the wheat harvest and the first autumn frost cover the second crop plus 10 days.

**Field check** — slope, summer greenness, soil, frost margin and heavy rain each give good / careful / not recommended; the verdict is the worst of them.

**Height correction** — a NASA POWER cell is about 50 km wide and averages valley and mountains. The cell over Talas has a mean height of 2,154 m; the town is at 1,237 m. We shift temperature to the field's height by 6.5 °C per km. Without it Talas would have 82 frost-free days; with it, 149.

## What is estimated, and what we do not know

- **Factors:** the snow sensitivity (0.5), the canal position factors, the normal-year factor, field efficiency (0.6) and all field-check thresholds are assumptions. They need a water manager and an agronomist.
- **Crop water need** uses FAO's typical stage lengths and crop coefficients (FAO-56 Tables 11–12), not values measured in Kyrgyzstan, and the Hargreaves formula, which needs only temperature.
- **Prices and yields** are known only for beans in Talas (news reports, autumn 2026). For other crops the result shows water and soil only.
- **FLDAS is a model**, not a measurement, and mountain snowfall is hard to model. The MODIS snow-cover check agrees with it only moderately (see above), and there is no river-gauge check yet.
- **Only one short year (2021) is confirmed** by a report. The other low-snow years are not checked against what farmers saw.
- **Resolution:** the field check describes the ~500 m around a field; climate comes from a ~50 km cell; heavy rain is a daily total and misses short, sharp storms.
- **In the south** (Kara-Darya, Syr-Darya) reservoirs and interstate agreements matter as much as snow.

## Run

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/uvicorn iseed.main:app --reload --port 8000   # API

cd frontend && npm install && npm run dev               # http://localhost:5173
```

To rebuild the data: `python3 scripts/power_job.py` and `python3 scripts/rain_job.py` need no login. The others need `pip install -r scripts/requirements.txt`, a Google Earth Engine account (`earthengine authenticate`) and your project id in `scripts/basins.py`.

The API contract is in `CLAUDE.md`.

## Built with

Python 3.12, FastAPI, pytest, SQLite; React, Vite, Leaflet; Google Earth Engine Python API, NumPy. Map data: OpenStreetMap (ODbL), geoBoundaries.

AI tools: Claude (Anthropic) was used to help write code and documents. The data, sources and formulas above were checked by the team.

## Sources

- FAO Irrigation and Drainage Paper 33 (yield response to water); FAO Irrigation Water Management Training Manual 3 (crop water needs)
- Ministry warns farmers of possible water shortage in 2026 (kaktus.media, 16 January 2026)
- Lack of irrigation water: farmers protest in Chui region (24.kg, June 2021)
- Red bean prices fall to 50–53 som (naq.media, 12 October 2026); state buys Talas beans (economist.kg, 23 December 2025)
- Bean area, harvest and yield 2023–2024 (topnews.kg)
