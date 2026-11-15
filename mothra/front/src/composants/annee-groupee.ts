// The label of the grouped row and the note of hypothesis 1 of a sheet, chosen by the window limit code the sheet carries (change of three closed
// quarters, R-20261114-49, design D7 and D8). A sheet frozen before the change carries `views_last_four_quarters` and keeps its former label and note;
// a new sheet carries `views_last_three_closed_quarters`. A sheet that carries neither code, or both, is a caller error: the front shows no grouped row
// and no guessed label (the mention `tableau.panel.mentionMissing`). Never chosen by the data.
// Replaces: the single label « Pooled year » of every sheet. Removal: permanent while frozen sheets are kept (beyond one year).
export interface ClesAnneeGroupee {
  libelle: string;
  note: string;
  marque: string;
}

// The keys of a frozen sheet: also the typed fallback of a branch that only runs once a code is known.
export const CLES_ANNEE_FIGEE: ClesAnneeGroupee = { libelle: "tableau.quarter.pooledYear", note: "conviction.pooledYearNote", marque: "pooled-year" };

export function clesAnneeGroupee(limites: readonly string[]): ClesAnneeGroupee | null {
  const ancienne = limites.includes("views_last_four_quarters");
  const nouvelle = limites.includes("views_last_three_closed_quarters");
  if (ancienne === nouvelle) return null;
  return ancienne
    ? CLES_ANNEE_FIGEE
    : { libelle: "tableau.quarter.lastThreeQuarters", note: "conviction.lastThreeQuartersNote", marque: "last-three-quarters" };
}
