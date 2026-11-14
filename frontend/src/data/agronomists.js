// DEMO district agronomists. The numbers use the code (000), which no operator has, so nobody real is called.
// Replace with the Ministry of Agriculture's list of district agronomists.
import DISTRICTS from './districts.json';

export const AGRONOMISTS = Object.fromEntries(
  DISTRICTS.districts.map((district, i) => [
    district.id,
    { phone: `+996 000 ${String(101 + i)} 000`, hours: '9:00–18:00', demo: true },
  ])
);

export const MINISTRY_HOTLINE = '1210';
