"""Reads data/climate.json (NASA POWER, written by scripts/power_job.py). The API never calls NASA."""
import json
import math
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"


@lru_cache
def load(name):
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def climate_at(lat, lon, elev_m):
    """Nearest POWER cell, at the height band closest to the field. None if the data is not built."""
    data = load("climate.json")
    if not data:
        return None
    k = math.cos(math.radians(lat))
    cell = min(data["cells"], key=lambda c: (c["lat"] - lat) ** 2 + ((c["lon"] - lon) * k) ** 2)
    elev = cell["cellElevM"] if elev_m is None else elev_m
    band = min(cell["bands"], key=lambda b: abs(b["elevM"] - elev))
    return {
        **band,
        "seasonRainMm": cell["seasonRainMm"],
        "seasonDays": data["seasonDays"],
        "cell": {"lat": cell["lat"], "lon": cell["lon"], "elevM": cell["cellElevM"]},
        "heightKnown": elev_m is not None,
        "source": data["source"],
        "window": data["window"],
        "computed": data["computed"],
    }


def _in_ring(lat, lon, ring):
    inside = False
    for (lon1, lat1), (lon2, lat2) in zip(ring, ring[1:] + ring[:1]):
        if (lat1 > lat) != (lat2 > lat) and lon < (lon2 - lon1) * (lat - lat1) / (lat2 - lat1) + lon1:
            inside = not inside
    return inside


def basin_at(lat, lon):
    """Id of the HydroBASINS level 5 basin the point is in, or None."""
    for f in (load("basins.geojson") or {"features": []})["features"]:
        for outer, *holes in f["geometry"]["coordinates"]:
            if _in_ring(lat, lon, outer) and not any(_in_ring(lat, lon, h) for h in holes):
                return f["properties"]["id"]
    return None
