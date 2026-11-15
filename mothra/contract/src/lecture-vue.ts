// Reading of the rows of a masked view answer (task 18.4): one place where a cell is read, for the dashboard and for the sheet.
// The answers read here are the output of the masking of the server (`masquerVue`, task 15.3): every count, statistic and share is a
// cell, a value or a masked cell. A plain number where a cell is expected is a fault, never read: the masking would be bypassed.
import type { Cellule } from "./cellule.ts";
import type { Mesure } from "./lead-cycle.ts";
import type { LigneReponse } from "./reponse.ts";

export type CelluleLue = { state: "value"; value: number } | { state: "masked"; threshold: number };

// The cell of a column of a row; `null` when there is no row (the quarter has no row in the view).
export function celluleDe(ligne: LigneReponse | undefined, colonne: string): CelluleLue | null {
  if (ligne === undefined) {
    return null;
  }
  const valeur: Cellule | string | number | null | undefined = ligne[colonne];
  if (typeof valeur === "object" && valeur !== null) {
    if (valeur.state === "masked") {
      return { state: "masked", threshold: valeur.threshold };
    }
    if (valeur.state === "value" && typeof valeur.value === "number") {
      return { state: "value", value: valeur.value };
    }
  }
  throw new TypeError(`cellule attendue dans la colonne ${colonne}`);
}

// A plain text column (the team, the period, the quarter start); anything else is `null`.
export function texteDe(ligne: LigneReponse, colonne: string): string | null {
  const valeur = ligne[colonne];
  return typeof valeur === "string" ? valeur : null;
}

// The cell as it is, or the masked cell of the effective threshold when there is none (nothing is estimated for an absent row).
export function celluleOuMasquee(cellule: CelluleLue | null, seuil: number): CelluleLue {
  return cellule ?? { state: "masked", threshold: seuil };
}

// A statistic (median or P85) with its headcount: masked when the statistic is masked or absent, "insufficient sample" when it is shown
// on fewer items than the reliability size (D22), a value otherwise.
export function mesureDeStatistique(statistique: CelluleLue | null, effectif: CelluleLue | null, taille: number, seuil: number): Mesure {
  if (statistique === null) {
    return { state: "masked", threshold: seuil };
  }
  if (statistique.state === "masked") {
    return { state: "masked", threshold: statistique.threshold };
  }
  if (effectif === null || effectif.state === "masked" || effectif.value < taille) {
    return { state: "insufficient_sample" };
  }
  return { state: "value", value: statistique.value };
}
