// A quarter as the API sends it ("2026-Q1") shown through the catalogue ("Q1 2026", "T1 2026"). The pooled-year point of a series
// (`pooled_year`, the contract's constant) is shown through its own catalogue key (R-20261031-61, Q111), like `fiche.measure.atPooledYear`.
// An identifier of another shape is shown as received.
import { ANNEE_GROUPEE } from "@mothra/contract/listes-fiche";

const FORME = /^(\d{4})-Q([1-4])$/;

export type Formater = (id: string, valeurs: { year: string; quarter: string }) => string;

export function libelleTrimestre(brut: string, formater: Formater): string {
  // The dashboard and the panels name the grouped row « Last three quarters » (R-20261114-49, design D7). A frozen sheet keeps its former label through
  // `annee-groupee.ts` (design D8), chosen by its window limit code, never here.
  if (brut === ANNEE_GROUPEE) return formater("tableau.quarter.lastThreeQuarters", { year: "", quarter: "" });
  const trouve = FORME.exec(brut);
  if (trouve === null) return brut;
  return formater("tableau.quarter.format", { year: trouve[1], quarter: trouve[2] });
}
