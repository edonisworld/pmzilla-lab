// The data date of a sheet and the quarters the views serve (audit #629, A-66, R-20261112-30, design D29). The views compute their window of three
// closed quarters from the clock of the database; a sheet is labelled by its data date. The rules are the pure functions of the contract
// (`dateDonneesAdmise`, `fichePerimee`, `fenetreConforme`, in `trimestres.ts`); this module is the server's layer that calls them with the UTC day
// of the request, never a route's formatting. None of the checks reads a view:
//   - at creation, the data date is not after the UTC day and lies in the current UTC quarter (`dataDateAcceptee`);
//   - a draft whose quarter is no longer the current one is stale: no body is computed for it (`donneesPerimees`);
//   - the rows a view gave must be those of the window of the data date (`verifierFenetre`), else a quarter change happened between the
//     check of the route and the read of the view (midnight race): the answer is the same refusal, nothing is served nor frozen.
// Replaces: « date réelle seulement » (a real calendar date, with no other bound). Removal: permanent (R-20261112-30).
import { dateDonneesAdmise, fenetreConforme, fichePerimee } from "@mothra/contract";
import type { ReponseVue } from "@mothra/contract";

// The rows of a view do not give the window of the date they are read for: the code of the answer is DATA_DATE_STALE (409), nothing else said.
export class FenetreDeVuesDecalee extends Error {
  constructor() {
    super("window of the views is not the one of the date");
    this.name = "FenetreDeVuesDecalee";
  }
}

export function dataDateAcceptee(dataDate: string, aujourdhui: string): boolean {
  return dateDonneesAdmise(dataDate, aujourdhui);
}

export function donneesPerimees(dataDate: string, aujourdhui: string): boolean {
  return fichePerimee(dataDate, aujourdhui);
}

// Every `quarter_start` a view gave lies in the window of `date`; a row without one (the pooled year) is not concerned.
export function verifierFenetre(reponse: ReponseVue, date: string): void {
  const debuts: string[] = [];
  for (const ligne of reponse.rows) {
    const debut = ligne.quarter_start;
    if (typeof debut === "string") debuts.push(debut);
  }
  if (!fenetreConforme(debuts, date)) {
    throw new FenetreDeVuesDecalee();
  }
}
