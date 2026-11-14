// Mirror of backend crops.csv (source: FAO-56 Tables 11–12, FAO Crop Calendar for Kyrgyzstan).
// income: 1 low, 2 medium, 3 high — a DEMO estimate, to be replaced with real farm budgets.
// pumpStop: loss if the pump stops for 10 days in July — heavy, cut (one hay cut lost) or light. DEMO estimate.
export const CROPS = [
  { id: 'barley', group: 'cereal', days: 120, needMm: 450, income: 1, pumpStop: 'light' },
  { id: 'maize', group: 'cereal', days: 140, needMm: 600, income: 2, pumpStop: 'heavy' },
  { id: 'potato', group: 'root', days: 130, needMm: 550, income: 3, pumpStop: 'heavy' },
  { id: 'sunflower', group: 'oilseed', days: 130, needMm: 550, income: 2, pumpStop: 'light' },
  { id: 'beans', group: 'legume', days: 100, needMm: 400, income: 3, pumpStop: 'heavy' },
  { id: 'chickpea', group: 'legume', days: 110, needMm: 350, income: 2, pumpStop: 'light' },
  { id: 'sugarbeet', group: 'root', days: 180, needMm: 650, income: 3, pumpStop: 'heavy' },
  { id: 'alfalfa', group: 'fodder', days: 150, needMm: 800, income: 2, pumpStop: 'cut' },
];
