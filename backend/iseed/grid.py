"""Reads the 0.005 degree grids in data/grid (scripts/raster_job.py): height, slope, greenness, soil."""
import json
import struct
from functools import lru_cache

from .climate import DATA

GRID = DATA / "grid"
FILES = {"elev": ("elev.i16", "<h"), "slope": ("slope.u8", "B"), "green": ("green.u8", "B"),
         "bare": ("bare.u8", "B"), "sand": ("sand.u8", "B"), "clay": ("clay.u8", "B")}


@lru_cache
def meta():
    path = GRID / "grid.json"
    return json.loads(path.read_text()) if path.exists() else None


def _read(name, row, col):
    file, fmt = FILES[name]
    size = struct.calcsize(fmt)
    with open(GRID / file, "rb") as f:
        f.seek((row * meta()["cols"] + col) * size)
        return struct.unpack(fmt, f.read(size))[0]


def site_at(points):
    """Mean of the grid cells under the given (lat, lon) points. None outside the grid or before it is built."""
    m = meta()
    if not m:
        return None
    cells = set()
    for lat, lon in points:
        row, col = int((m["north"] - lat) / m["step"]), int((lon - m["west"]) / m["step"])
        if 0 <= row < m["rows"] and 0 <= col < m["cols"]:
            cells.add((row, col))
    if not cells:
        return None
    mean = lambda name: sum(_read(name, r, c) for r, c in cells) / len(cells)
    return {
        "elevM": round(mean("elev")),
        "slopeDeg": round(mean("slope") / 4, 1),
        "greenYears": round(mean("green")),
        "bareYears": round(mean("bare")),
        "ndviYears": m["ndviYears"],
        "sandPct": round(mean("sand")),
        "clayPct": round(mean("clay")),
        "cellM": 500,
        "sources": m["sources"],
        "computed": m["computed"],
    }
