// Points are [lat, lng]. GeoJSON uses [lng, lat].
export const MIN_POINTS = 4;

const EARTH_R = 6371008.8;
const toRad = (d) => (d * Math.PI) / 180;

export function centroid(points) {
  const sum = points.reduce(([a, b], [lat, lng]) => [a + lat, b + lng], [0, 0]);
  return [sum[0] / points.length, sum[1] / points.length];
}

// Shoelace formula on a local flat projection: accurate for fields of a few km.
export function areaHa(points) {
  if (points.length < 3) return 0;
  const k = Math.cos(toRad(centroid(points)[0]));
  const xy = points.map(([lat, lng]) => [toRad(lng) * EARTH_R * k, toRad(lat) * EARTH_R]);
  let sum = 0;
  xy.forEach(([x1, y1], i) => {
    const [x2, y2] = xy[(i + 1) % xy.length];
    sum += x1 * y2 - x2 * y1;
  });
  return Math.abs(sum) / 2 / 10000;
}

export const midpoint = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];

// Ray casting: is the point inside the ring?
function inRing([lat, lng], ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [lat1, lng1] = ring[i];
    const [lat2, lng2] = ring[j];
    const crosses = lat1 > lat !== lat2 > lat && lng < ((lng2 - lng1) * (lat - lat1)) / (lat2 - lat1) + lng1;
    if (crosses) inside = !inside;
  }
  return inside;
}

// A polygon is [outerRing, ...holes].
export const inPolygon = (point, [outer, ...holes]) => inRing(point, outer) && !holes.some((hole) => inRing(point, hole));

// A square of `ha` hectares around a point (4 corners).
export function squareAround([lat, lng], ha = 1) {
  const dLat = (Math.sqrt(ha * 10000) / 2 / EARTH_R) * (180 / Math.PI);
  const dLng = dLat / Math.cos(toRad(lat));
  return [
    [lat + dLat, lng - dLng],
    [lat + dLat, lng + dLng],
    [lat - dLat, lng + dLng],
    [lat - dLat, lng - dLng],
  ];
}

export function toGeoJSON(points) {
  const ring = points.map(([lat, lng]) => [lng, lat]);
  return { type: 'Polygon', coordinates: [[...ring, ring[0]]] };
}

export const fromGeoJSON = (geometry) => geometry.coordinates[0].slice(0, -1).map(([lng, lat]) => [lat, lng]);
