// The life cycle of the sheets in the interface (audit #629, A-04): the sheets in progress listed by state, and the review and the publication
// of one sheet. The source is injected by the entry of the bundle (the real one is `sourceCycleFicheHttp`), as the dashboard source and the
// reader of a sheet are; the pages read it and compute nothing. The list answers an opaque identifier, the kind, the scope code, the data date and
// the state of each sheet: no text, no count, no verdict.
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import type { EtatFiche, ResultatAction } from "./fiche.ts";

// The states a sheet is "in progress" in: a draft waits for a review, a reviewed sheet waits for its publication. A published sheet is frozen.
export const ETATS_EN_COURS = ["draft", "reviewed"] as const satisfies readonly EtatFiche[];
export type EtatEnCours = (typeof ETATS_EN_COURS)[number];

export interface ResumeFiche {
  id: string;
  chart: GraphiqueDeFiche;
  // `team.<opaque identifier>`, as the sheet holds it.
  scope: string;
  dataDate: string;
  state: EtatFiche;
}

export type ListeurFiches = (etat: EtatEnCours) => Promise<ResumeFiche[]>;

// What the two pages read and write through. The actions give back the result of the route: success, or the code of the refusal.
export interface SourceCycleFiche {
  lister: ListeurFiches;
  relire: (id: string) => Promise<ResultatAction>;
  publier: (id: string) => Promise<ResultatAction>;
}

// The cache key of the lists: `["sheets"]` is the prefix an action invalidates, so that a list is read again after a review or a publication.
export const CLE_LISTES_FICHES = ["sheets"] as const;

// One key per state, no retry: an error code is an answer, not a fault to hide (as the dashboard and the sheet).
export function optionsListeFiches(lister: ListeurFiches, etat: EtatEnCours) {
  return {
    queryKey: [...CLE_LISTES_FICHES, etat],
    queryFn: () => lister(etat),
    retry: false,
    // A refusal stays the answer for this list: the page does not ask again by itself on mount (as the sheet).
    retryOnMount: false,
    refetchOnWindowFocus: false,
  };
}
