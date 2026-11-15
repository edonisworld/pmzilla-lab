// The computed body of a sheet for real (mothra-slices D30, task 18.4): the implementation of the port `calculerCorps` of the sheet routes.
// It reads the five views of the slice through the one masked path of the service (`lireVueMasquee`, the same as the route of the views),
// the threshold history from the storage, and hands both to `corpsDepuisVues` of the contract, which alone calls the verdict functions.
// Nothing is computed here: no verdict, no state, no share. The fingerprint of what was read is the only value made here.
import { corpsDepuisVues, verifierCreation as verifierCreationDuContrat } from "@mothra/contract";
import type { Contrat, Vue } from "@mothra/contract";

import type { AccesVues } from "../db/acces.ts";
import { avecPartsDAttente, lireVueMasquee, servirCorps } from "../service.ts";
import type { ModeDonnees } from "../service.ts";
import { empreinte } from "./depot.ts";
import type { CorpsCalcule, DepotFiches, DepotSeuils } from "./depot.ts";
import { verifierFenetre } from "./fenetre.ts";

// A sheet kind not served on real data (Q48 (a)): the route answers 404 NOT_FOUND.
export class FicheNonServie extends Error {
  constructor() {
    super("sheet kind not served");
    this.name = "FicheNonServie";
  }
}

export const VUES_DE_LA_FICHE = {
  leadCycle: "v_team_lead_time_throughput",
  sansEquipe: "v_task_without_team_share",
  nonPlanifie: "v_unplanned_share",
  fileEnAttente: "v_team_ready_queue",
  bloque: "v_team_blocked_share",
} as const;

export interface DependancesCorps {
  acces: AccesVues;
  contrat: Contrat;
  seuil: number; // the effective threshold of the views (contract, setting)
  depot: DepotSeuils & Pick<DepotFiches, "creeeLe">;
  identifiantEquipe: (nom: string) => string;
  // The dataset and the constant of the contract (task 19.5): on real data with counts not allowed, the body is reduced here, in the
  // service layer. Mandatory (task 19.8, R-20261031-24 Q55): a call without it is refused, never served in the complete form.
  // Replaces: the default "absent, the body stays the contract's" of task 19.5. Removal: permanent (a default to the complete form is a leak).
  mode: ModeDonnees;
}

function vueDuContrat(contrat: Contrat, nom: string): Vue {
  const vue = contrat.views.find((v) => v.name === nom);
  if (vue === undefined) {
    throw new Error(`vue absente du contrat : ${nom}`);
  }
  return vue;
}

export function creerCalculCorps(dep: DependancesCorps): {
  calculerCorps(contexte: { id: string; chart: string; scope: string; dataDate: string }): Promise<CorpsCalcule>;
  verifierCreation(entree: { chart: string; scope: string }): Promise<void>;
  // The bars of the share of waiting (D3b), added at each reading by the routes; spread with the others into the options of the sheet routes.
  completer<T extends CorpsCalcule>(corps: T): T;
} {
  // Refusal by default: no mode, no computed body (the runtime check holds where the types do not, a caller from a script or a double).
  // A mode whose dataset is neither "real" nor "synthetic", or whose constant is not a boolean, is refused as well.
  const donne = (dep as Partial<DependancesCorps>).mode as Partial<ModeDonnees> | undefined;
  if (donne === undefined || donne === null || (donne.jeu !== "real" && donne.jeu !== "synthetic") || typeof donne.comptesAutorises !== "boolean") {
    throw new Error("mode obligatoire : le corps d'une fiche n'est jamais construit sans le jeu de données explicite");
  }
  const mode = dep.mode;
  return {
    async calculerCorps(contexte) {
      const historique = await dep.depot.seuils();
      const premiereLecture = await dep.depot.creeeLe(contexte.id);
      const lire = (nom: string) => lireVueMasquee(dep.acces, vueDuContrat(dep.contrat, nom), dep.seuil);
      const [leadCycle, sansEquipe, nonPlanifie, fileEnAttente, bloque] = await Promise.all([
        lire(VUES_DE_LA_FICHE.leadCycle),
        lire(VUES_DE_LA_FICHE.sansEquipe),
        lire(VUES_DE_LA_FICHE.nonPlanifie),
        lire(VUES_DE_LA_FICHE.fileEnAttente),
        lire(VUES_DE_LA_FICHE.bloque),
      ]);
      // A66 (R-20261112-30): the rows read are those of the window of the data date, else the quarter changed since the route's check.
      for (const lue of [leadCycle, sansEquipe, nonPlanifie, fileEnAttente, bloque]) verifierFenetre(lue, contexte.dataDate);
      const vues = { leadCycle, sansEquipe, nonPlanifie, fileEnAttente, bloque };
      const corps = corpsDepuisVues({
        chart: contexte.chart,
        scope: contexte.scope,
        dataDate: contexte.dataDate,
        premiereLecture,
        historique: historique.map((h) => ({ code: h.code, value: h.value, setOn: h.setOn })),
        vues,
        identifiantEquipe: dep.identifiantEquipe,
        empreinte: empreinte(vues),
      });
      // Task 19.5: the dataset code on every body and, on real data, the reduction to statistics (D34). The mode is explicit (task 19.8).
      return servirCorps(corps, mode);
    },
    // Not part of `calculerCorps`, so that the freeze never stores `waitShares` (Q151, R-20261101-32): the routes call it when they answer.
    completer: avecPartsDAttente,
    // Before a sheet is created: a chart outside the closed list (GraphiqueInconnu) or a threshold not fixed (SeuilsNonFixes) is refused.
    async verifierCreation(entree) {
      // Q48 (a) of R-20261031-19: the sheet of hypothesis 5 is not validated by the oracle (R-20261031-07, Q17 (a)); on real data it is not
      // created (the route answers the existing 404 NOT_FOUND, nothing stored). Replaces: nothing. Removal: falls with the author's decision of
      // 12 November (R-20261031-18, option (b) of Q17).
      if (mode.jeu === "real" && entree.chart === "lead_cycle_h5") {
        throw new FicheNonServie();
      }
      verifierCreationDuContrat(entree.chart, await dep.depot.seuils(), entree.scope);
    },
  };
}
