// Test helper of lot 1b of mothra-demo-habillage (D15, R-20261031-61): a sheet answer built by `corpsDepuisVues` of the contract from synthetic
// view rows, never an object written by hand. Same construction as the one of composition.test.ts (kept there as it was, its tests being
// unchanged but for R-20261101-43); here for the tests of `partsDAttente` and of the server.
import { corpsDepuisVues } from "../src/corps-fiche.ts";
import type { EntreeCorps, EntreeHistorique } from "../src/corps-fiche.ts";
import { identifiantEquipe, scopeFiche } from "../src/equipe.ts";
import type { LigneReponse, ReponseVue } from "../src/reponse.ts";
import { DEPART_ECHANTILLON, DEPART_H1, DEPART_H5, DEPART_RATTACHEMENT } from "./depart.ts";

export const M = { state: "masked" as const, threshold: 5 };
export type Entier = number | "m";
const c = (x: Entier) => (x === "m" ? M : { state: "value" as const, value: x });

const DATE = "2026-10-05";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
const EQUIPE = "team-a";
export const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe(EQUIPE) });

export interface Opts {
  ltN?: number;
  ctN?: number;
  lm?: Entier;
  lp?: Entier;
  cm?: Entier;
  cp?: Entier;
}

function ligne(debut: string | null, o: Opts): LigneReponse {
  return {
    team: EQUIPE,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: c(30),
    items_lt: c(o.ltN ?? 30),
    items_ct: c(o.ctN ?? 30),
    items_old: c(5),
    items_without_commitment: c(5),
    lead_median_days: c(o.lm ?? 15),
    lead_p85_days: c(o.lp ?? 30),
    cycle_median_days: c(o.cm ?? 10),
    cycle_p85_days: c(o.cp ?? 20),
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: c(o.lm ?? 15),
    lead_p85_days_excl_old: c(o.lp ?? 30),
    cycle_median_days_excl_old: c(o.cm ?? 10),
    cycle_p85_days_excl_old: c(o.cp ?? 20),
  };
}

function reponse(view: string, rows: LigneReponse[]): ReponseVue {
  return { view, threshold: 5, columns: [], rows, sources: ["flow"] };
}

function historique(over: Record<string, number> = {}): EntreeHistorique[] {
  const base: Array<[string, number]> = [
    ["h5_band", DEPART_H5.band],
    ["h5_double_band", DEPART_H5.doubleBand],
    ["h5_run_rises", DEPART_H5.runRises],
    ["h5_run_min_cumulative_rise", DEPART_H5.runMinCumulativeRise],
    ["h5_floor", DEPART_H5.floor],
    ["h5_low_floor", DEPART_H5.lowFloor],
    ["h1_lower", DEPART_H1.lower],
    ["h1_upper", DEPART_H1.upper],
    ["attachment_threshold_points", DEPART_RATTACHEMENT.thresholdPoints],
    ["sample_median_min_items", DEPART_ECHANTILLON.medianMinItems],
    ["sample_p85_min_items", DEPART_ECHANTILLON.p85MinItems],
  ];
  return base.map(([code, value]) => ({ code, value: over[code] ?? value, setOn: "2026-10-27" }));
}

// trimestres: one option set per quarter of the window (null: no row); annee: the pooled-year row; seuils: thresholds that replace the starting ones.
export function fiche(chart: "lead_cycle_h1" | "lead_cycle_h5", trimestres: Array<Opts | null>, annee: Opts = {}, seuils: Record<string, number> = {}) {
  const rows: LigneReponse[] = [];
  trimestres.forEach((o, i) => {
    if (o !== null) rows.push(ligne(DEBUTS[i], o));
  });
  rows.push(ligne(null, annee));
  const vues: EntreeCorps["vues"] = {
    leadCycle: reponse("v_team_lead_time_throughput", rows),
    sansEquipe: reponse(
      "v_task_without_team_share",
      DEBUTS.map((d) => ({ quarter_start: d, tasks_done: c(30), share_percent: c(10) })),
    ),
    nonPlanifie: reponse(
      "v_unplanned_share",
      DEBUTS.map((d) => ({ quarter_start: d, unplanned_n: c(30), share_percent: c(12) })),
    ),
    fileEnAttente: reponse("v_team_ready_queue", [{ team: EQUIPE, quarter_start: DEBUTS[2], ready: c(12) }]),
    bloque: reponse("v_team_blocked_share", [{ team: EQUIPE, quarter_start: DEBUTS[2], blocked_n: c(30), blocked: c(9), share_percent: c(30) }]),
  };
  const corps = corpsDepuisVues({
    chart,
    scope: SCOPE,
    dataDate: DATE,
    premiereLecture: "2026-10-30",
    historique: historique(seuils),
    vues,
    identifiantEquipe,
    empreinte: "f".repeat(64),
  });
  return { id: "s1", ...corps };
}

// The window of a sheet: three closed quarters since R-20261114-49 (renamed from QUATRE, rename only).
export const TROIS: Opts[] = [{}, {}, {}];
