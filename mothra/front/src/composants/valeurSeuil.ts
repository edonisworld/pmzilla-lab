// The display form of the value of a threshold (audit #629, A-10 point 7, R-20261109-08 Q5): the stored value stays the fraction the service
// sends (0.2, 0.8, 1.5); the screen writes it as the reader reads it ("±20 %", "80 %", "1.5×"), and the same form on the card, the method
// face and the line of a threshold modified after reading. A pure display function: it formats the value it is given and computes no share;
// the percentage is the catalogue's own number style (`{value, number, percent}`), so that the language writes it.
// The form is chosen by the code of the threshold in a table typed on the contract's closed list (`CODES_SEUILS`, source), so that a code
// added to the list without its form fails the compilation; a test compares the keys of the table with `TOUS_LES_CODES_SEUILS`. A code
// the table does not know shows the number, as before.
// Replaces: the raw display of the fraction. Removal: permanent while the thresholds are stored as fractions.
import type { IntlShape } from "react-intl";

import type { CodeSeuil } from "@mothra/contract/listes-fiche";

export type FormeSeuil = "plusMinusPercent" | "percent" | "ratio" | "number";

export const FORMES_SEUILS: Record<CodeSeuil, FormeSeuil> = {
  h5_band: "plusMinusPercent",
  h5_double_band: "plusMinusPercent",
  h5_run_rises: "number",
  h5_run_min_cumulative_rise: "percent",
  h5_floor: "percent",
  h5_low_floor: "percent",
  h1_lower: "ratio",
  h1_upper: "ratio",
  attachment_threshold_points: "number",
  sample_median_min_items: "number",
  sample_p85_min_items: "number",
};

export function valeurSeuil(intl: IntlShape, code: string, valeur: number): string {
  const forme: FormeSeuil = Object.hasOwn(FORMES_SEUILS, code) ? FORMES_SEUILS[code as CodeSeuil] : "number";
  if (forme === "plusMinusPercent") return intl.formatMessage({ id: "fiche.thresholdValue.plusMinus" }, { value: valeur });
  if (forme === "percent") return intl.formatMessage({ id: "fiche.thresholdValue.percent" }, { value: valeur });
  if (forme === "ratio") return intl.formatMessage({ id: "fiche.thresholdValue.ratio" }, { value: valeur });
  return intl.formatNumber(valeur);
}
