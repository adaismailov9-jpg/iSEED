// Where a field may NOT be placed: outside Kyrgyzstan, on a lake or reservoir, or too high in the mountains.
import KYRGYZSTAN from '../data/kyrgyzstan.json'; // border, OpenStreetMap via geoBoundaries
import WATER from '../data/water.json'; // main lakes and reservoirs, OpenStreetMap
import DISTRICTS from '../data/districts.json'; // districts (raions), geoBoundaries
import { inPolygon } from './geo';

export const ALL_DISTRICTS = DISTRICTS.districts.map(({ id }) => id);

// Id of the district the point is in. Cities such as Bishkek or Batken are gaps in the district map:
// there the district with the closest border point is taken.
export function districtAt(point) {
  const inside = DISTRICTS.districts.find((d) => d.polygons.some((polygon) => inPolygon(point, polygon)));
  if (inside) return inside.id;

  const distance = (d) => Math.min(...d.polygons.flat(2).map(([lat, lng]) => (lat - point[0]) ** 2 + (lng - point[1]) ** 2));
  return DISTRICTS.districts.reduce((best, d) => (distance(d) < distance(best) ? d : best)).id;
}

export const MAX_FIELD_ELEVATION = 3000; // metres; above this Kyrgyzstan has almost no ploughland

export const insideKyrgyzstan = (point) => KYRGYZSTAN.polygons.some((polygon) => inPolygon(point, polygon));

const onWater = (point) => WATER.lakes.some((lake) => lake.polygons.some((polygon) => inPolygon(point, polygon)));

// Height above sea level (Open-Meteo, Copernicus DEM 90 m). null when there is no internet.
async function elevation([lat, lng]) {
  try {
    const res = await fetch(`https://api.open-meteo.com/v1/elevation?latitude=${lat}&longitude=${lng}`);
    return (await res.json()).elevation[0];
  } catch {
    return null;
  }
}

// Why a field cannot go here ({ reason, height }), or null if the spot is fine.
export async function whyNotHere(point) {
  if (!insideKyrgyzstan(point)) return { reason: 'outside' };
  if (onWater(point)) return { reason: 'water' };
  const height = await elevation(point);
  if (height > MAX_FIELD_ELEVATION) return { reason: 'high', height };
  return null;
}
