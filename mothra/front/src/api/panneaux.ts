// The answers of the panels of the product-scope dashboard (mothra-slices D35, task 37.2) and the reader that fetches them. The answer types
// live in @mothra/contract (D30, one data layer, task 18.0): this module declares none of them. The real reader is in http.ts, the
// simulated one in src/simule/. A panel is read for one scope, the whole product or one team, over a range of closed quarters; the key of a
// query holds both, so changing a filter reads again.
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the panels leave the dashboard.
import type { CodePanneau, PanneauComplet, PanneauReduit } from "@mothra/contract";
import { scopeFiche } from "@mothra/contract/equipe";

import type { FiltresEcran } from "./filtres.ts";
import type { CodeErreur } from "./vue.ts";

// The complete answer (synthetic dataset) or the reduced one (real data, D34): the screen renders both.
export type ReponsePanneau = PanneauComplet | PanneauReduit;
export type LecteurPanneau = (code: CodePanneau, filtres: FiltresEcran) => Promise<ReponsePanneau>;

// What the second screen reads its panels through, injected by the entry of the bundle: the reader and whether it is simulated.
export interface SourcePanneaux {
  lire: LecteurPanneau;
  simulee: boolean;
}

// The refusals of the panel routes that the other routes do not have (task 31.1, D35): a scope that is not one team or the whole product, a
// range that is not whole closed quarters. The code is the server's, the front translates it (`error.<code>`); any other refusal is a code of
// `CODES_ERREUR`. Kept apart from that list: it is the list of the sheet routes, with its own tests.
export const CODES_REFUS_FILTRES = ["SCOPE_INVALID", "RANGE_INVALID"] as const;
export type CodeRefusFiltres = (typeof CODES_REFUS_FILTRES)[number];

export function estRefusFiltres(valeur: unknown): valeur is CodeRefusFiltres {
  return typeof valeur === "string" && (CODES_REFUS_FILTRES as readonly string[]).includes(valeur);
}

// A refusal of a panel route, carried as its code.
export class RefusPanneau extends Error {
  code: CodeErreur | CodeRefusFiltres;

  constructor(code: CodeErreur | CodeRefusFiltres) {
    super(code);
    this.name = "RefusPanneau";
    this.code = code;
  }
}

// One key, no retry: an error code is an answer, not a fault to hide (as the views and the dashboard).
export function optionsPanneau(code: CodePanneau, filtres: FiltresEcran, lire: LecteurPanneau) {
  return {
    queryKey: ["panel", code, filtres.team ?? "product", filtres.from, filtres.to],
    queryFn: () => lire(code, filtres),
    retry: false,
    refetchOnWindowFocus: false,
  };
}

// The scope the screen asked for, as the answers state theirs: `product` or `team.<identifier>`.
export function porteeDemandee(filtres: FiltresEcran): string {
  return filtres.team === undefined ? "product" : scopeFiche({ kind: "team", team: filtres.team });
}

// A panel asked for a team and served for the product (a product panel, D35) says so: the screen only compares the two codes.
export function porteeServieDiffere(demandee: string, servie: string): boolean {
  return demandee !== servie;
}

// A reduced answer (real data) carries the code `reduced_form` and no point.
export function estReduit(reponse: ReponsePanneau): reponse is PanneauReduit {
  return "limits" in reponse;
}
