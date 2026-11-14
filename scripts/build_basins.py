"""HydroBASINS level 5 (Earth Engine) -> data/basins.geojson, simplified for point lookups."""
import json
from pathlib import Path

import ee

from basins import BASINS, EE_PROJECT, SOUTH, basins_fc

OUT = Path(__file__).resolve().parents[1] / "data" / "basins.geojson"

ee.Initialize(project=EE_PROJECT)
towns = {v[0]: v[1] for v in BASINS.values()}
features = basins_fc(ee).map(lambda f: f.simplify(1000)).getInfo()["features"]
out = []
for f in features:
    bid = f["properties"]["id"]
    geom = f["geometry"]
    parts = geom["geometries"] if geom["type"] == "GeometryCollection" else [geom]  # simplify can leave stray lines
    polys = [p for g in parts if g["type"] in ("Polygon", "MultiPolygon")
             for p in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]])]
    polys = [[[[round(x, 3), round(y, 3)] for x, y in ring] for ring in poly] for poly in polys]
    out.append({"type": "Feature", "properties": {"id": bid, "hybasId": f["properties"]["HYBAS_ID"], "towns": towns[bid],
                                                   "areaKm2": round(f["properties"]["SUB_AREA"]), "south": bid in SOUTH},
                "geometry": {"type": "MultiPolygon", "coordinates": polys}})
OUT.write_text(json.dumps({"type": "FeatureCollection", "source": "HydroBASINS level 5 (HydroSHEDS, WWF), via Earth Engine",
                           "features": sorted(out, key=lambda f: f["properties"]["id"])}, separators=(",", ":")))
print(f"wrote {OUT}: {[f['properties']['id'] for f in out]}")
