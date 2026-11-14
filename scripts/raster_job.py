"""Earth Engine -> data/grid/*.bin: terrain, greenness and soil on a 0.005 degree grid (~500 m)
over Kyrgyzstan, so the field check works for any field without calling Earth Engine live.

  elev.i16   mean height, m                      NASA SRTM 30 m
  slope.u8   mean slope, degrees x 4             NASA SRTM 30 m
  green.u8   years 2013-2025 with summer NDVI >= 0.5   NASA MODIS MOD13Q1 250 m
  bare.u8    years 2013-2025 with summer NDVI < 0.3    NASA MODIS MOD13Q1 250 m
  sand.u8, clay.u8   percent, 5-15 cm            SoilGrids 2.0 (ISRIC; not NASA)
Rows run north to south, columns west to east; raw little-endian values.
"""
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import ee
import numpy as np
import requests

from basins import EE_PROJECT

OUT = Path(__file__).resolve().parents[1] / "data" / "grid"
STEP, WEST, NORTH, COLS, ROWS = 0.005, 69.2, 43.3, 2220, 840
TILE_COLS, TILE_ROWS = 111, 84  # small tiles: averaging 30 m SRTM is heavy for Earth Engine
NDVI_YEARS = range(2013, 2026)
BANDS = {"elev": "<i2", "slope": "u1", "green": "u1", "bare": "u1", "sand": "u1", "clay": "u1"}


def image():
    transform = [STEP, 0, WEST, 0, -STEP, NORTH]
    srtm = ee.Image("USGS/SRTMGL1_003")
    mean = lambda img: img.reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(crs="EPSG:4326", crsTransform=transform)
    elev = mean(srtm).rename("elev")
    slope = mean(ee.Terrain.slope(srtm)).multiply(4).min(255).rename("slope")

    ndvi = ee.ImageCollection("MODIS/061/MOD13Q1").select("NDVI")
    summer_max = lambda y: ndvi.filterDate(f"{y}-06-01", f"{y}-09-01").max().multiply(0.0001)
    years = [summer_max(y) for y in NDVI_YEARS]
    green = ee.ImageCollection([y.gte(0.5) for y in years]).sum().rename("green")
    bare = ee.ImageCollection([y.lt(0.3) for y in years]).sum().rename("bare")

    sand = ee.Image("projects/soilgrids-isric/sand_mean").select("sand_5-15cm_mean").divide(10).rename("sand")
    clay = ee.Image("projects/soilgrids-isric/clay_mean").select("clay_5-15cm_mean").divide(10).rename("clay")
    return ee.Image.cat([elev, slope, green, bare, sand, clay]).unmask(0).round().toInt16()


def tile(img, col, row):
    url = img.getDownloadURL({
        "format": "NPY", "crs": "EPSG:4326", "dimensions": [TILE_COLS, TILE_ROWS],
        "crs_transform": [STEP, 0, WEST + col * STEP, 0, -STEP, NORTH - row * STEP],
    })
    for attempt in range(4):
        res = requests.get(url, timeout=600)
        if res.ok:
            return col, row, np.load(io.BytesIO(res.content))
        print(f"  retry tile {col},{row}: {res.status_code} {res.text[:200]}", flush=True)
    res.raise_for_status()


def main():
    ee.Initialize(project=EE_PROJECT)
    img = image()
    full = {name: np.zeros((ROWS, COLS), dtype=kind) for name, kind in BANDS.items()}
    jobs = [(c, r) for r in range(0, ROWS, TILE_ROWS) for c in range(0, COLS, TILE_COLS)]
    with ThreadPoolExecutor(8) as pool:
        for n, (col, row, data) in enumerate(pool.map(lambda j: tile(img, *j), jobs), 1):
            print(f"  tile {n}/{len(jobs)}", flush=True)
            for name in BANDS:
                full[name][row:row + TILE_ROWS, col:col + TILE_COLS] = np.clip(data[name], 0, 32000 if name == "elev" else 255)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, kind in BANDS.items():
        (OUT / f"{name}.{'i16' if name == 'elev' else 'u8'}").write_bytes(full[name].astype(kind).tobytes())
    (OUT / "grid.json").write_text(json.dumps({
        "step": STEP, "west": WEST, "north": NORTH, "cols": COLS, "rows": ROWS,
        "ndviYears": len(NDVI_YEARS), "computed": date.today().isoformat(),
        "sources": {
            "elev": "NASA SRTM 30 m (USGS/SRTMGL1_003), mean per cell",
            "slope": "NASA SRTM 30 m, mean slope per cell, degrees x 4",
            "green": "NASA MODIS MOD13Q1 v6.1, 250 m: years 2013-2025 whose June-August peak NDVI was 0.5 or more",
            "bare": "NASA MODIS MOD13Q1 v6.1, 250 m: years 2013-2025 whose June-August peak NDVI was under 0.3",
            "sand": "SoilGrids 2.0 (ISRIC; not NASA), sand percent at 5-15 cm",
            "clay": "SoilGrids 2.0 (ISRIC; not NASA), clay percent at 5-15 cm",
        },
    }, indent=1))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
