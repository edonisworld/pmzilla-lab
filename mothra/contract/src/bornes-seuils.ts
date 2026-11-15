// The bounds of the thresholds of the dated history (audit #629, A-63 / L3-04, decision R-20261107-20 order 4): the closed list of the codes,
// the bounds of each code, the pair that must stay ordered. Pure: no I/O, no clock. The server refuses a write outside them (400), and the
// reading of a history that is already inconsistent gives a declared error (SeuilsIncoherents), never a raw RangeError.
// Replaces: the free code and the free value of POST /api/thresholds (a code matching a pattern, any finite number). Removal: permanent
// while the history is written by the author through the route; the bounds change only on a decision of the author.
// The values are bounds of validity, not adopted values: the adopted values come from the history (D21), never from this package.
import { PLANCHER } from "./plancher.ts";

interface Borne {
  min: number;
  max: number;
  entier: boolean;
}

// Ratios and bands: from 0 to 10 (a relative gap above ten times the reference is not a threshold); counts: whole numbers.
const RATIO: Borne = { min: 0, max: 10, entier: false };
// The sample size of a median or a P85: a whole number, never under the floor of five of the contract (plancher.ts): a published count is at
// least five, a sample under it is never reliable, and a size of 0 would remove the guard (A-63). A size above 10000 is not a sample.
const TAILLE: Borne = { min: Math.max(1, PLANCHER), max: 10_000, entier: true };

export const BORNES_SEUILS: Readonly<Record<string, Borne>> = {
  h5_band: RATIO,
  h5_double_band: RATIO,
  h5_run_rises: { min: 1, max: 100, entier: true },
  h5_run_min_cumulative_rise: RATIO,
  h5_floor: RATIO,
  h5_low_floor: RATIO,
  h1_lower: { min: 0, max: 100, entier: false },
  h1_upper: { min: 0, max: 100, entier: false },
  attachment_threshold_points: { min: 0, max: 100, entier: false },
  sample_median_min_items: TAILLE,
  sample_p85_min_items: TAILLE,
};

// The keys above are the codes of the closed list CODES_SEUILS (listes-fiche.ts), which is the source; a gap between the two is detected by
// contract/test/bornes-seuils.test.ts (same keys as TOUS_LES_CODES_SEUILS).
export function codeDeSeuilConnu(code: string): boolean {
  return Object.hasOwn(BORNES_SEUILS, code);
}

// Whether a value is inside the bounds of its code (an unknown code has no bound: false).
export function seuilDansLesBornes(code: string, value: number): boolean {
  if (!codeDeSeuilConnu(code) || !Number.isFinite(value)) {
    return false;
  }
  const borne = BORNES_SEUILS[code];
  return value >= borne.min && value <= borne.max && (!borne.entier || Number.isInteger(value));
}

// The pairs (lower, upper) that must stay ordered (R-20261107-29 decision 7): the two thresholds of hypothesis 1 (twoThresholds), strictly;
// the pairs of hypothesis 5, band under double band and low floor under floor, equal values allowed (third item: strictly ordered or not).
export const COUPLES_SEUILS: ReadonlyArray<readonly [string, string, boolean]> = [
  ["h1_lower", "h1_upper", true],
  ["h5_band", "h5_double_band", false],
  ["h5_low_floor", "h5_floor", false],
];

// Same rounding as the verdict service, so that "equal" means the same thing there and here.
const arrondi = (x: number): number => Math.round(x * 1e9) / 1e9;

// The codes of the pairs that are not ordered in the history (the latest value of each code, the order of the date, then of the insertion).
export function couplesIncoherents(historique: ReadonlyArray<{ code: string; value: number; setOn: string }>): string[] {
  const dernier = (code: string): number | null => {
    const propres = historique.filter((h) => h.code === code).sort((a, b) => (a.setOn < b.setOn ? -1 : a.setOn > b.setOn ? 1 : 0));
    return propres.length === 0 ? null : propres[propres.length - 1].value;
  };
  const codes: string[] = [];
  for (const [bas, haut, strict] of COUPLES_SEUILS) {
    const vBas = dernier(bas);
    const vHaut = dernier(haut);
    if (vBas !== null && vHaut !== null && !(strict ? arrondi(vBas) < arrondi(vHaut) : arrondi(vBas) <= arrondi(vHaut))) {
      codes.push(bas, haut);
    }
  }
  return codes;
}
