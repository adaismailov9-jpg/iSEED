"""NASA POWER daily point API -> data/climate.json.

For each cell: Apr-Sep rain (2001-2025), and per height band the frost dates in 9 years
out of 10 and weekly frost / heat / temperature (1981-2025). No login needed.

  python scripts/power_job.py                  # 0.5 degree grid over Kyrgyzstan
  python scripts/power_job.py 42.52 72.24      # one point (Talas), merged into the file
"""
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "climate.json"
BORDER = ROOT / "frontend" / "src" / "data" / "kyrgyzstan.json"
URL = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M_MAX,T2M_MIN,PRECTOTCORR"
       "&community=AG&latitude={lat}&longitude={lon}&start=19810101&end=20251231&format=JSON")
YEARS = range(1981, 2026)
RAIN_YEARS = range(2001, 2026)
HOT_C = 35
BANDS = range(600, 3001, 300)  # field heights, metres
LAPSE_C_PER_M = 0.0065


def fetch(lat, lon):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(URL.format(lat=lat, lon=lon), timeout=120) as res:
                return json.load(res)
        except Exception as err:  # the API is sometimes busy
            if attempt == 3:
                raise
            print(f"  retry {lat},{lon}: {err}", flush=True)
            time.sleep(10 * (attempt + 1))


def percentile(values, share):
    """Nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(share * len(ordered)) - 1))]


def summarise(lat, lon, res):
    """POWER's cell is ~50 km wide and averages valley and mountains, so its temperature is
    that of the cell's mean height. Each band shifts it to a field's height by the standard
    lapse rate (6.5 C per km, an estimate)."""
    p, cell_elev = res["properties"]["parameter"], res["geometry"]["coordinates"][2]
    tmax, tmin, rain = p["T2M_MAX"], p["T2M_MIN"], p["PRECTOTCORR"]
    ok = lambda v: v is not None and v > -900
    days = []  # (year, day of year, week, tmax, tmin)
    season_rain = {y: 0.0 for y in RAIN_YEARS}
    for k in tmin:
        year = int(k[:4])
        if year in season_rain and "04" <= k[4:6] <= "09" and ok(rain[k]):
            season_rain[year] += rain[k]
        if ok(tmin[k]) and ok(tmax[k]):
            doy = date(year, int(k[4:6]), int(k[6:])).timetuple().tm_yday
            days.append((year, doy, min(51, (doy - 1) // 7), tmax[k], tmin[k]))

    n = len(YEARS)
    bands = []
    for elev in BANDS:
        shift = LAPSE_C_PER_M * (cell_elev - elev)
        last_spring = {y: 1 for y in YEARS}
        first_autumn = {y: 366 for y in YEARS}
        frost_weeks = set()
        hot = [0] * 52
        temp_sum, temp_n = [0.0] * 52, [0] * 52
        for year, doy, week, hi, lo in days:
            hi, lo = hi + shift, lo + shift
            if lo < 0:
                frost_weeks.add((year, week))
                if doy < 183:
                    last_spring[year] = max(last_spring[year], doy)
                else:
                    first_autumn[year] = min(first_autumn[year], doy)
            if hi > HOT_C:
                hot[week] += 1
            temp_sum[week] += (hi + lo) / 2
            temp_n[week] += 1
        frost = [sum((y, w) in frost_weeks for y in YEARS) for w in range(52)]
        spring, autumn = percentile(last_spring.values(), 0.9), percentile(first_autumn.values(), 0.1)
        bands.append({
            "elevM": elev,
            "lastSpringFrostDoy": spring,  # later in only 1 year out of 10
            "firstAutumnFrostDoy": autumn,  # earlier in only 1 year out of 10
            "frostFreeDays": max(0, autumn - spring - 1),
            "lastSpringFrostByYear": list(last_spring.values()),  # 1981-2025, for the trend
            "weekFrostShare": [round(c / n, 2) for c in frost],
            "weekHotDays": [round(c / n, 1) for c in hot],  # mean days above 35 C
            "weekMeanTempC": [round(s / c, 1) if c else None for s, c in zip(temp_sum, temp_n)],
        })
    return {
        "lat": lat,
        "lon": lon,
        "cellElevM": round(cell_elev),
        "seasonRainMm": round(sum(season_rain.values()) / len(season_rain)),
        "bands": bands,
    }


def in_ring(lat, lon, ring):
    inside = False
    for (lat1, lon1), (lat2, lon2) in zip(ring, ring[1:] + ring[:1]):
        if (lat1 > lat) != (lat2 > lat) and lon < (lon2 - lon1) * (lat - lat1) / (lat2 - lat1) + lon1:
            inside = not inside
    return inside


def grid():
    polygons = json.loads(BORDER.read_text())["polygons"]
    inside = lambda la, lo: any(in_ring(la, lo, poly[0]) for poly in polygons)
    cells = []
    for i in range(78, 88):  # 39.0 .. 43.5
        for j in range(138, 162):  # 69.0 .. 80.5
            lat, lon = i / 2, j / 2
            if inside(lat, lon):
                cells.append((lat, lon))
    return cells


def main():
    points = [(float(sys.argv[1]), float(sys.argv[2]))] if len(sys.argv) == 3 else grid()
    old = json.loads(OUT.read_text())["cells"] if OUT.exists() else []
    cells = {(c["lat"], c["lon"]): c for c in old}
    for n, (lat, lon) in enumerate(points, 1):
        print(f"{n}/{len(points)} {lat},{lon}", flush=True)
        cells[(lat, lon)] = summarise(lat, lon, fetch(lat, lon))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "NASA POWER daily point API (AG community), T2M_MAX, T2M_MIN, PRECTOTCORR",
        "window": "1981-2025 (frost, heat, temperature); 2001-2025 (rain)",
        "note": "Temperature is shifted from the POWER cell's mean height to each band by 6.5 C per km (estimate); rain is the cell value",
        "computed": date.today().isoformat(),
        "seasonDays": 183,
        "cells": list(cells.values()),
    }, separators=(",", ":")))
    print(f"wrote {OUT} with {len(cells)} cells")


if __name__ == "__main__":
    main()
