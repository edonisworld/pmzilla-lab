// The one test helper of the front for answers of the server (R-20261031-61, rule 2 of the testing practice): SYNTHETIC rows of the views, run
// through the pure functions of the contract that the server calls (masquerVue, tableauLeadCycle, servirTableau, corpsDepuisVues). Every
// server-shaped value of a new front test comes out of here, never out of a hand-written object. Every name and figure is invented (three
// generic teams, closed quarters, one pooled-year row per team).
//
// What the rows hold (counts equal on a row, so that the relations between cells of the contract keep them all shown, except where said):
//   team-a: three quarters of 40 items, pooled year of 120 (40 + 40 + 40; before: four quarters, 160);
//   team-b: the quarter 2026-Q1 holds 3 items (under the floor of 5): its cells are masked, and so is the pooled year (series rule);
//   team-c: the quarter 2026-Q2 holds 8 items (shown, but under the reliability size of 10): an insufficient sample.
//
// Copy named, gap not detected: the line `{ view, threshold, columns, rows, sources }` below is the last line of `composerReponse` of
// server/src/service.ts (server code, not importable here). The relation T3 (weekly rows) is not played: `hebdo` is left out of `masquerVue`.
// Removal: with the migration of the front tests after 19/11 (R-20261031-61, Q112), when the doubling of the old tests ends.
import {
  PorteeProduitRefusee,
  celluleDe,
  chargerContrat,
  corpsDepuisVues,
  etiquetteTrimestre,
  masquerVue,
  panneauBlockedShare,
  panneauCorrectionShare,
  panneauDefectsInout,
  panneauStoriesInout,
  servirPanneau,
  servirTableau,
  tableauLeadCycle,
  verifierFiltres,
} from "@mothra/contract";
import type {
  CorpsDepuisVues,
  EntreeBloque,
  EntreeCorps,
  EntreeFlux,
  LigneBrute,
  ModeDonnees,
  Portee,
  ReponseLeadCycle,
  ReponseLeadCycleReduite,
  ReponseVue,
  Vue,
} from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import { RefusPanneau } from "../src/api/panneaux.ts";
import type { LecteurPanneau, SourcePanneaux } from "../src/api/panneaux.ts";

export const SEUIL = 5;
export const DATE_DONNEES = "2026-10-05";
export const CONFIG_ECHANTILLON = { medianMinItems: 10, p85MinItems: 20 };
export const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
export const EQUIPES = ["team-a", "team-b", "team-c"] as const;

export const MODE_SYNTHETIQUE: ModeDonnees = { jeu: "synthetic", comptesAutorises: false };
export const MODE_REEL: ModeDonnees = { jeu: "real", comptesAutorises: false };

const CONTRAT = chargerContrat(new URL("../../../contrats/vues.json", import.meta.url));

function vueDuContrat(nom: string): Vue {
  const vue = CONTRAT.views.find((v) => v.name === nom);
  if (vue === undefined) throw new Error(`vue absente du contrat : ${nom}`);
  return vue;
}

// The masked answer of a view, as the service hands it to the contract's functions: the rows masked by `masquerVue`.
function reponseMasquee(nom: string, lignes: LigneBrute[]): ReponseVue {
  const vue = vueDuContrat(nom);
  const rows = masquerVue(vue, lignes, SEUIL);
  return { view: vue.name, threshold: SEUIL, columns: [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns], rows, sources: [vue.schema] };
}

interface Statistiques {
  lm: number;
  lp: number;
  cm: number;
  cp: number;
}

// A row of v_team_lead_time_throughput as read from the database: the five counts equal to `n`, the four statistics given.
function ligne(equipe: string, debut: string | null, n: number, s: Statistiques): LigneBrute {
  return {
    team: equipe,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: n,
    items_lt: n,
    items_ct: n,
    items_old: 0, // R-20261106-66 : valait l'effectif n, donc une taille de H1 nulle
    items_without_commitment: n,
    lead_median_days: s.lm,
    lead_p85_days: s.lp,
    cycle_median_days: s.cm,
    cycle_p85_days: s.cp,
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: s.lm,
    lead_p85_days_excl_old: s.lp,
    cycle_median_days_excl_old: s.cm,
    cycle_p85_days_excl_old: s.cp,
  };
}

const STATISTIQUES: Record<(typeof EQUIPES)[number], Statistiques> = {
  "team-a": { lm: 41, lp: 80, cm: 9, cp: 20 },
  "team-b": { lm: 20, lp: 45, cm: 6, cp: 12 },
  "team-c": { lm: 29, lp: 60, cm: 7, cp: 15 },
};
const EFFECTIFS: Record<(typeof EQUIPES)[number], readonly [number, number, number]> = {
  "team-a": [40, 40, 40],
  "team-b": [3, 40, 40],      // 2026-Q1 holds 3 items (the first of the three closed quarters)
  "team-c": [40, 8, 40],      // 2026-Q2 holds 8 items (the second of the three closed quarters)
};

// The rows of v_team_lead_time_throughput: three closed quarters and the pooled year of each of the three teams.
export function lignesLeadCycle(): LigneBrute[] {
  return EQUIPES.flatMap((equipe) => {
    const effectifs = EFFECTIFS[equipe];
    const s = STATISTIQUES[equipe];
    return [
      ...DEBUTS.map((debut, i) => ligne(equipe, debut, effectifs[i], s)),
      ligne(equipe, null, effectifs.reduce((a, b) => a + b, 0), s),
    ];
  });
}

// The answer of the view v_team_lead_time_throughput after masking (what the contract's `tableauLeadCycle` and `corpsDepuisVues` read).
export function reponseVueLeadCycle(lignes: LigneBrute[] = lignesLeadCycle()): ReponseVue {
  return reponseMasquee("v_team_lead_time_throughput", lignes);
}

// The answer of the dashboard as the route serves it: masking, `tableauLeadCycle`, then `servirTableau` (dataset code, then reduction on real
// data), all three being the functions of the contract that the server calls.
export function reponseServie(mode: ModeDonnees, lignes: LigneBrute[] = lignesLeadCycle()): ReponseLeadCycle | ReponseLeadCycleReduite {
  return servirTableau(tableauLeadCycle(reponseVueLeadCycle(lignes), CONFIG_ECHANTILLON, DATE_DONNEES, identifiantEquipe), mode);
}

// The complete answer of the synthetic dataset (the only one that holds counts).
export function reponseComplete(lignes: LigneBrute[] = lignesLeadCycle()): ReponseLeadCycle {
  return reponseServie(MODE_SYNTHETIQUE, lignes) as ReponseLeadCycle;
}

// ---- The body of a sheet ------------------------------------------------------------------------------------------------------------

const SEUILS: Array<[string, number]> = [
  ["h5_band", 0.2],
  ["h5_double_band", 0.4],
  ["h5_run_rises", 2],
  ["h5_run_min_cumulative_rise", 0.1],
  ["h5_floor", 0.8],
  ["h5_low_floor", 0.6],
  ["h1_lower", 1.5],
  ["h1_upper", 3],
  ["attachment_threshold_points", 10],
  ["sample_median_min_items", 10],
  ["sample_p85_min_items", 20],
];

// The scope of the sheets below: team-a, by its opaque identifier.
export const PORTEE_FICHE = scopeFiche({ kind: "team", team: identifiantEquipe("team-a") });

export function entreeCorps(chart: "lead_cycle_h5" | "lead_cycle_h1"): EntreeCorps {
  const parts = (colonnes: (v: number) => LigneBrute): LigneBrute[] => DEBUTS.map((debut, i) => ({ quarter_start: debut, ...colonnes(i) }));
  return {
    chart,
    scope: PORTEE_FICHE,
    dataDate: DATE_DONNEES,
    premiereLecture: "2026-10-30",
    historique: SEUILS.map(([code, value]) => ({ code, value, setOn: "2026-10-27" })),
    vues: {
      leadCycle: reponseVueLeadCycle(),
      sansEquipe: reponseMasquee("v_task_without_team_share", parts(() => ({ tasks_done: 40, tasks_without_team: 10, share_percent: 25 }))),
      nonPlanifie: reponseMasquee("v_unplanned_share", parts(() => ({ unplanned_n: 40, unplanned: 12, share_percent: 30 }))),
      fileEnAttente: reponseMasquee("v_team_ready_queue", [{ team: "team-a", quarter_start: DEBUTS[2], ready: 12 }]),
      bloque: reponseMasquee("v_team_blocked_share", [{ team: "team-a", quarter_start: DEBUTS[2], blocked_n: 40, blocked: 8, share_percent: 20 }]),
    },
    identifiantEquipe,
    empreinte: "f".repeat(64),
  };
}

// The body of a sheet as the contract builds it from the masked views (the function the server calls).
export function corpsReel(chart: "lead_cycle_h5" | "lead_cycle_h1"): CorpsDepuisVues {
  return corpsDepuisVues(entreeCorps(chart));
}

// ---- The panels (R-20261031-61, rule 1; review of 37.4) -----------------------------------------------------------------------------
// Rows of v_team_flow_inout and v_team_blocked_share, masked by `masquerVue`, then the panel functions of the contract (37.1) and
// `servirPanneau` (dataset code, then reduction on real data), as the server's `calculerPanneau` and the panel route do.
// Copy named, gap not detected: `retenue`, `lignesDeFlux` and `lignesDeBlocage` below are the adapter of server/src/fiches/panneaux.ts
// (server code that reads a database access, not importable here). The refusals are turned into codes as the route does (422 SCOPE_INVALID,
// RANGE_INVALID). Removal: with the migration of the front tests after 19/11 (Q112).
const PRODUIT = "(produit)";
const SANS_EQUIPE = "(sans équipe)";

// Stories per team and quarter: 30 created, 28 done (the product row 90 and 84); team-b's quarter 2026-Q1 holds 3 created (masked, so is the
// product cell of that quarter and group). Defects carry no team (D33): the product row and the row without a team only, 20 and 18 against 10
// and 9; the row without a team holds 3 created in 2026-Q1 (masked, so is the product cell).
export function lignesFlux(): LigneBrute[] {
  const ligne = (team: string, debut: string, groupe: string, created: number, done: number): LigneBrute => ({
    team,
    quarter_start: debut,
    type_group: groupe,
    created,
    done,
  });
  return DEBUTS.flatMap((debut) => [
    ...EQUIPES.map((equipe) => ligne(equipe, debut, "story", equipe === "team-b" && debut === "2026-01-01" ? 3 : 30, 28)),
    ligne(PRODUIT, debut, "story", 90, 84),
    ligne(PRODUIT, debut, "defect", 20, 18),
    ligne(SANS_EQUIPE, debut, "defect", debut === "2026-01-01" ? 3 : 10, 9),
  ]);
}

export function lignesBlocage(): LigneBrute[] {
  return DEBUTS.flatMap((debut) => EQUIPES.map((equipe) => ({ team: equipe, quarter_start: debut, blocked_n: 40, blocked: 8, share_percent: 20 })));
}

function retenue(equipe: unknown, portee: Portee): boolean {
  if (typeof equipe !== "string" || equipe === SANS_EQUIPE) return false;
  if (portee.kind === "product") return equipe === PRODUIT;
  return equipe !== PRODUIT && identifiantEquipe(equipe) === portee.team;
}

function entreesFlux(reponse: ReponseVue, portee: Portee): EntreeFlux[] {
  return reponse.rows
    .filter((l) => retenue(l.team, portee))
    .map((l) => {
      const created = celluleDe(l, "created");
      const done = celluleDe(l, "done");
      if (created === null || done === null || (l.type_group !== "story" && l.type_group !== "defect")) throw new TypeError("ligne de flux illisible");
      return { quarter: etiquetteTrimestre(String(l.quarter_start)), group: l.type_group, created, done };
    });
}

function entreesBlocage(reponse: ReponseVue, portee: Portee): EntreeBloque[] {
  return reponse.rows
    .filter((l) => retenue(l.team, portee))
    .map((l) => {
      const blocked = celluleDe(l, "blocked");
      const blockedN = celluleDe(l, "blocked_n");
      const share = celluleDe(l, "share_percent");
      if (blocked === null || blockedN === null || share === null) throw new TypeError("ligne de blocage illisible");
      return { quarter: etiquetteTrimestre(String(l.quarter_start)), blocked, blockedN, share };
    });
}

// The reader of the panels of the second screen, fed by the contract's functions from synthetic rows of the views.
export function sourcePanneauxContrat(mode: ModeDonnees): SourcePanneaux {
  const flux = reponseMasquee("v_team_flow_inout", lignesFlux());
  const blocage = reponseMasquee("v_team_blocked_share", lignesBlocage());
  const lire: LecteurPanneau = async (code, filtres) => {
    const f = verifierFiltres({ team: filtres.team, from: filtres.from, to: filtres.to }, { today: DATE_DONNEES });
    if (!f.ok) throw new RefusPanneau(f.code);
    const produit: Portee = { kind: "product" };
    try {
      switch (code) {
        case "blocked-share":
          return servirPanneau(panneauBlockedShare(entreesBlocage(blocage, f.scope), f, DATE_DONNEES, SEUIL, mode.jeu), mode);
        case "stories-inout":
          return servirPanneau(panneauStoriesInout(entreesFlux(flux, f.scope), f, DATE_DONNEES, SEUIL, mode.jeu), mode);
        case "defects-inout":
          return servirPanneau(panneauDefectsInout(entreesFlux(flux, produit), f, DATE_DONNEES, SEUIL, mode.jeu), mode);
        case "correction-share":
          return servirPanneau(panneauCorrectionShare(entreesFlux(flux, produit), f, DATE_DONNEES, SEUIL, mode.jeu), mode);
      }
    } catch (echec) {
      if (echec instanceof PorteeProduitRefusee) throw new RefusPanneau(echec.code);
      throw echec;
    }
  };
  return { lire, simulee: false };
}
