"""NASA MODIS snow cover (Earth Engine) -> data/snow_check.json: a satellite check on FLDAS.

FLDAS snow water is a model fed with weather data. MODIS MOD10A1 sees snow directly (cover,
not depth). For each basin and year 2001-2026 this takes the mean share of land above 2,000 m
that is snow covered (NDSI >= 40, clouds left out) in two windows, and how well each agrees
with the FLDAS March snow water volume:

  march   - March cover. Weak test: in March most high land is white in any year.
  spring  - April-May cover: a deep snowpack lasts longer into the melt season, so if FLDAS is
            right, its big-snow years should stay white longer. Chosen before looking at the
            result, as the one stronger test; no other windows were tried.
"""
import json
from datetime import date
from pathlib import Path

import ee

from basins import EE_PROJECT, basins_fc
from snow_job import HIGH_M, YEARS

DATA = Path(__file__).resolve().parents[1] / "data"
WINDOWS = {"march": ("03-01", "04-01"), "spring": ("04-01", "06-01")}


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return cov / (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5


def compare(basin, modis):
    """Correlation with FLDAS and which low years (lower tercile of 2001-2025) the two share."""
    fldas = [p["volumeKm3"] for p in basin["series"]]
    third = sorted(modis[:-1])[len(modis[:-1]) // 3 - 1]
    low_fldas = {p["year"] for p in basin["series"] if p["level"] == "low"}
    low_modis = {y for y, v in zip(YEARS, modis) if v < third}
    return {
        "r": round(pearson(fldas, modis), 2),
        "lowInBoth": sorted(low_fldas & low_modis),
        "lowInFldasOnly": sorted(low_fldas - low_modis),
        "lowInModisOnly": sorted(low_modis - low_fldas),
        "series": [{"year": y, "snowCoverPct": round(v * 100, 1)} for y, v in zip(YEARS, modis)],
    }


def main():
    ee.Initialize(project=EE_PROJECT)
    basins = basins_fc(ee)
    high = ee.Image("USGS/SRTMGL1_003").gte(HIGH_M)
    cover = {}
    for window, (start, end) in WINDOWS.items():
        for year in YEARS:
            days = ee.ImageCollection("MODIS/061/MOD10A1").filterDate(f"{year}-{start}", f"{year}-{end}").select("NDSI_Snow_Cover")
            share = days.map(lambda img: img.gte(40)).mean().updateMask(high)
            fc = share.reduceRegions(basins, ee.Reducer.mean(), 2000).select(["id", "mean"], None, False)
            for f in fc.getInfo()["features"]:
                cover[(window, f["properties"]["id"], year)] = f["properties"]["mean"]
            print(window, year, flush=True)

    snow = json.loads((DATA / "snow.json").read_text())["basins"]
    out = {}
    for bid, basin in snow.items():
        out[bid] = {window: compare(basin, [cover[(window, bid, y)] for y in YEARS]) for window in WINDOWS}
        # Top level keeps the March check, the shape the API and the screen already read.
        out[bid].update(out[bid]["march"])
        print(bid, {w: out[bid][w]["r"] for w in WINDOWS}, flush=True)
    (DATA / "snow_check.json").write_text(json.dumps({
        "source": "NASA MODIS MOD10A1 v6.1 daily snow cover, 500 m (MODIS/061/MOD10A1), NDSI_Snow_Cover >= 40",
        "note": f"Mean share of land above {HIGH_M} m that is snow covered: in March, and in April-May (how long the snow lasts). "
                "r is the Pearson correlation with the FLDAS March snow water volume, 2001-2026. Cover is not depth.",
        "computed": date.today().isoformat(),
        "basins": out,
    }, indent=1))
    print("wrote data/snow_check.json")


if __name__ == "__main__":
    main()
