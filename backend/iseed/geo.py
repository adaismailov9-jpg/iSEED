"""Field geometry. GeoJSON is [lon, lat]; everything else here is (lat, lon)."""
import math

EARTH_R = 6371008.8


def ring_of(geometry):
    """The outer ring of a GeoJSON Polygon as (lat, lon) points, without the closing point."""
    ring = geometry["coordinates"][0]
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    return [(lat, lon) for lon, lat in ring]


def centroid(points):
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def area_ha(points):
    """Shoelace formula on a local flat projection: accurate for fields of a few km."""
    k = math.cos(math.radians(centroid(points)[0]))
    xy = [(math.radians(lon) * EARTH_R * k, math.radians(lat) * EARTH_R) for lat, lon in points]
    total = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))
    return abs(total) / 2 / 10000
