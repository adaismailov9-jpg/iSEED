"""NASA FLDAS monthly snow water equivalent (Earth Engine) -> data/snow.json.

Per basin and year 2001-2026: snow water volume in February and March, in km3.
volume = sum over pixels of SWE (mm) / 1000 x pixel area (m2) / 1e9.
Two volumes are kept: the whole basin, and only land above 2,000 m ("high"), because
several basins run far into the lowlands of Kazakhstan and Uzbekistan.
"""
import json
import sys
from datetime import date
from pathlib import Path

import ee

from basins import BASINS, EE_PROJECT, SOUTH, basins_fc

OUT = Path(__file__).resolve().parents[1] / "data" / "snow.json"
FLDAS = "NASA/FLDAS/NOAH01/C/GL/M/V001"
YEARS = list(range(2001, 2027))
HIGH_M = 2000
USE = "high"  # which volume sets the level: "high" or "all"
# Years with a reported irrigation shortage. To be replaced by the years the water manager names.
SHORT_YEARS = {2021: "24.kg, June 2021: farmers in Chui region protest over lack of irrigation water"}


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(share * len(ordered)) - 1))]


def main():
    ee.Initialize(project=EE_PROJECT)
    basins = basins_fc(ee)
    high = ee.Image("USGS/SRTMGL1_003").gte(HIGH_M)
    area = ee.Image.pixelArea()

    def month_image(year, month):
        swe = ee.ImageCollection(FLDAS).filterDate(ee.Date.fromYMD(year, month, 1), ee.Date.fromYMD(year, month, 1).advance(1, "month")).select("SWE_inst").first()
        km3 = swe.multiply(area).divide(1e12)  # mm x m2 -> km3
        return km3.rename("all").addBands(km3.updateMask(high).rename("high"))

    rows = {}
    for month in (2, 3):
        print(f"month {month}", flush=True)
        for year in YEARS:
            # 1 km scale: FLDAS pixels are ~11 km, so basin edges and the 2,000 m line are cut finely
            fc = month_image(year, month).reduceRegions(basins, ee.Reducer.sum(), 1000).select(["id", "all", "high"], None, False)
            for f in fc.getInfo()["features"]:
                p = f["properties"]
                rows[(p["id"], year, month)] = {"all": p["all"], "high": p["high"]}
            print(f"  {year}", flush=True)

    out = {}
    for bid, _ in BASINS.values():
        march = {y: rows[(bid, y, 3)] for y in YEARS}
        feb = {y: rows[(bid, y, 2)] for y in YEARS}
        base = [march[y][USE] for y in YEARS[:-1]]  # 2001-2025
        normal = sum(base) / len(base)
        low, high_t = percentile(base, 1 / 3), percentile(base, 2 / 3)
        level = lambda v: "low" if v < low else "high" if v > high_t else "normal"
        feb_normal = sum(feb[y][USE] for y in YEARS[:-1]) / len(base)
        now = YEARS[-1]
        out[bid] = {
            "basin": bid,
            "south": bid in SOUTH,
            "level": level(march[now][USE]),
            "anomaly": round((march[now][USE] - normal) / normal, 3),
            "volumeKm3": round(march[now][USE], 3),
            "normalKm3": round(normal, 3),
            "month": f"{now}-03",
            "early": {"month": f"{now}-02", "anomaly": round((feb[now][USE] - feb_normal) / feb_normal, 3)},
            "terciles": [round(low, 3), round(high_t, 3)],
            "replayYear": 2021,
            "series": [{"year": y, "volumeKm3": round(march[y][USE], 3), "wholeBasinKm3": round(march[y]["all"], 3),
                        "febKm3": round(feb[y][USE], 3), "level": level(march[y][USE]), "short": y in SHORT_YEARS} for y in YEARS],
        }
    OUT.write_text(json.dumps({
        "source": "NASA FLDAS Noah monthly 0.1 degree (NASA/FLDAS/NOAH01/C/GL/M/V001), band SWE_inst, summed per HydroBASINS level 5 basin",
        "note": f"Volume counts land above {HIGH_M} m (SRTM). FLDAS is a model fed with weather data, not a direct measurement.",
        "normal": "mean of March 2001-2025; levels by terciles of 2001-2025",
        "shortYears": [{"year": y, "source": s} for y, s in SHORT_YEARS.items()],
        "computed": date.today().isoformat(),
        "basins": out,
    }, indent=1))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
