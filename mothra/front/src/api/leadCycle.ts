// The answer of the dashboard "lead time against cycle time" (design D19, D24) and the request that makes a sheet of it (design D29).
// Slice 1 reads these through a simulated reader and a simulated route (src/simule/): the real routes come with group 18. A median or a
// P85 is a measure with three states: a value, a masked cell (under the confidentiality threshold, D22) or an insufficient sample
// (under the reliability threshold, D22). A masked or insufficient measure carries no value at all.
import type { Brouillon, Cellule, DemandeFiche, ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";

import type { ModificationFiche } from "./fiche.ts";

// The answer types live in @mothra/contract (D30, one data layer, task 18.0): this module declares none of them.
// A count of items: the contract's cell (a value or a masked cell).
export type Effectif = Cellule;

// The complete answer (synthetic dataset) or the reduced one (real data, D34): the screen renders both.
export type LecteurLeadCycle = () => Promise<ReponseLeadCycle | ReponseLeadCycleReduite>;

// The cache key of the dashboard answer: the sheet reads the answer in memory by it (D35, N2 (a)), without a second request.
export const CLE_LEAD_CYCLE = ["lead-cycle"];

// One key, no retry: an error code is an answer, not a fault to hide (as the views).
export function optionsLeadCycle(lire: LecteurLeadCycle) {
  return {
    queryKey: CLE_LEAD_CYCLE,
    queryFn: lire,
    retry: false,
    refetchOnWindowFocus: false,
  };
}

// The request of the creation: chart, scope and data date, and the three optional fields of the draft (design D29). A refusal of the
// service is raised as a `RefusFiche` (api/fiche.ts); any other failure is an internal error.
export type DemandeCreation = DemandeFiche & ModificationFiche;
export type CreerFiche = (demande: DemandeCreation) => Promise<Brouillon>;

// What the dashboard reads and writes through, injected by the entry of the bundle: the reader of the answer, the route of the
// sheet and whether both are simulated. The screen shows its "simulated data" notice from `simulee` only.
export interface SourceLeadCycle {
  lire: LecteurLeadCycle;
  creer: CreerFiche;
  simulee: boolean;
}
