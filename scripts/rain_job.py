"""NASA GPM IMERG daily rain (served by the NASA POWER API) -> data/rain_weeks.json.

Per grid cell, 2001-2025: for every week of the year, the share of years with at least one
day of heavy rain, and the longest dry spell in June-August. No login needed.
"""
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

from power_job import grid

OUT = Path(__file__).resolve().parents[1] / "data" / "rain_weeks.json"
URL = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=IMERG_PRECTOT&community=AG"
       "&latitude={lat}&longitude={lon}&start=20010101&end=20251231&format=JSON&time-standard=UTC")
YEARS = range(2001, 2026)
HEAVY_MM, RAINY_MM, DRY_MM = 20, 10, 1


def fetch(lat, lon):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(URL.format(lat=lat, lon=lon), timeout=120) as res:
                return json.load(res)["properties"]["parameter"]["IMERG_PRECTOT"]
        except Exception as err:
            if attempt == 3:
                raise
            print(f"  retry {lat},{lon}: {err}", flush=True)
            time.sleep(10 * (attempt + 1))


def summarise(lat, lon, rain):
    heavy, rainy = set(), set()
    dry_spells = []
    for year in YEARS:
        spell = longest = 0
        for k, mm in rain.items():
            if not k.startswith(str(year)) or mm < -900:
                continue
            week = min(51, (date(year, int(k[4:6]), int(k[6:])).timetuple().tm_yday - 1) // 7)
            if mm >= HEAVY_MM:
                heavy.add((year, week))
            if mm >= RAINY_MM:
                rainy.add((year, week))
            if "06" <= k[4:6] <= "08":
                spell = spell + 1 if mm < DRY_MM else 0
                longest = max(longest, spell)
        dry_spells.append(longest)
    n = len(YEARS)
    share = lambda hits: [round(sum((y, w) in hits for y in YEARS) / n, 2) for w in range(52)]
    return {"lat": lat, "lon": lon, "weekHeavyShare": share(heavy), "weekRainyShare": share(rainy),
            "summerDrySpellDays": round(sum(dry_spells) / n)}


def main():
    cells = []
    points = grid()
    for n, (lat, lon) in enumerate(points, 1):
        print(f"{n}/{len(points)} {lat},{lon}", flush=True)
        cells.append(summarise(lat, lon, fetch(lat, lon)))
    OUT.write_text(json.dumps({
        "source": "NASA GPM IMERG daily precipitation (IMERG_PRECTOT), via the NASA POWER daily API, UTC days",
        "window": "2001-2025",
        "heavyMm": HEAVY_MM, "rainyMm": RAINY_MM,
        "note": "weekHeavyShare: share of years with a day of 20 mm or more in that week; weekRainyShare: 10 mm or more. Thresholds are estimates.",
        "computed": date.today().isoformat(),
        "cells": cells,
    }, separators=(",", ":")))
    print(f"wrote {OUT} with {len(cells)} cells")


if __name__ == "__main__":
    main()
