// The dashboard "lead time against cycle time" for real (mothra-slices D24, D30, task 19.6): the implementation of the port `calculerTableau`
// of the dashboard route. It reads the lead time view through the one masked path of the service (`lireVueMasquee`), the reliability sizes
// from the threshold history, and hands both to `tableauLeadCycle` of the contract, the function the sheet body reads too (one data layer).
// Nothing is computed here. The reduction on real data is NOT done here: it is the service's `servirTableau`, called by the route.
import { lireSeuils, tableauLeadCycle } from "@mothra/contract";
import type { Contrat, ReponseLeadCycle } from "@mothra/contract";

import type { AccesVues } from "../db/acces.ts";
import { lireVueMasquee } from "../service.ts";
import { VUES_DE_LA_FICHE } from "./corps.ts";
import type { DepotSeuils } from "./depot.ts";

export interface DependancesTableau {
  acces: AccesVues;
  contrat: Contrat;
  seuil: number; // the effective threshold of the views
  depot: DepotSeuils;
  identifiantEquipe: (nom: string) => string;
  // The data date of the answer: the day of the reading (an ISO date), given by the caller so that a test fixes it.
  aujourdhui: () => string;
}

export function creerCalculTableau(dep: DependancesTableau): { calculerTableau(): Promise<ReponseLeadCycle> } {
  return {
    async calculerTableau() {
      const vue = dep.contrat.views.find((v) => v.name === VUES_DE_LA_FICHE.leadCycle);
      if (vue === undefined) {
        throw new Error(`vue absente du contrat : ${VUES_DE_LA_FICHE.leadCycle}`);
      }
      // The reliability sizes of D22: a size missing from the history is THRESHOLDS_NOT_SET (409), as for the sheets.
      const historique = await dep.depot.seuils();
      const [mediane, p85] = lireSeuils(
        historique.map((h) => ({ code: h.code, value: h.value, setOn: h.setOn })),
        ["sample_median_min_items", "sample_p85_min_items"],
        null,
      );
      const reponse = await lireVueMasquee(dep.acces, vue, dep.seuil);
      return tableauLeadCycle(reponse, { medianMinItems: mediane.value, p85MinItems: p85.value }, dep.aujourdhui(), dep.identifiantEquipe);
    },
  };
}
