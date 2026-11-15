// Parity of the sheet screen with the computed body of task 18.4: the body is built by `corpsDepuisVues` of the contract on synthetic
// views (invented team, invented figures), then rendered in each language. No code the service emits may fall to a "not available"
// fallback label (review of 19.3, B1): the front reads the codes of the contract, not codes of its own.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import { corpsDepuisVues } from "@mothra/contract";
import type { EntreeCorps, LigneReponse, ReponseVue } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import type { ReponseFiche } from "../src/api/fiche.ts";
import { Fiche } from "../src/composants/Fiche.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { rendre, texte as texteDuMarquage } from "./rendu.ts";

const M = { state: "masked" as const, threshold: 5 };
type Entier = number | "m";
const c = (x: Entier) => (x === "m" ? M : { state: "value" as const, value: x });

const DATE = "2026-10-05";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
const JUGE = DEBUTS[2];
const EQUIPE = "team-a";
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe(EQUIPE) });

function reponse(view: string, rows: LigneReponse[]): ReponseVue {
  return { view, threshold: 5, columns: [], rows, sources: ["flow"] };
}

interface Trimestre {
  n?: Entier;
  ltN?: Entier;
  ctN?: Entier;
  lm?: Entier;
  lp?: Entier;
  cm?: Entier;
  cp?: Entier;
}

function ligne(debut: string | null, o: Trimestre): LigneReponse {
  return {
    team: EQUIPE,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: c(o.n ?? 30),
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

function parts(valeurs: Array<Entier | null>, vue: string, colonneNombre: string): ReponseVue {
  return reponse(
    vue,
    valeurs.flatMap((v, i) => (v === null ? [] : [{ quarter_start: DEBUTS[i], [colonneNombre]: c(30), share_percent: c(v) }])),
  );
}

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

// Masked cells and insufficient samples everywhere the service notes them, so that every measure code of the body is exercised.
function entree(chart: "lead_cycle_h5" | "lead_cycle_h1"): EntreeCorps {
  const trimestres: Trimestre[] = [{ n: "m" }, { cm: "m", cp: 3 }, {}];
  const rows = trimestres.map((o, i) => ligne(DEBUTS[i], o));
  rows.push(ligne(null, { lp: "m", ltN: 5, ctN: 5 }));
  return {
    chart,
    scope: SCOPE,
    dataDate: DATE,
    premiereLecture: "2026-10-30",
    historique: SEUILS.map(([code, value]) => ({ code, value, setOn: "2026-10-27" })),
    vues: {
      leadCycle: reponse("v_team_lead_time_throughput", rows),
      sansEquipe: parts(["m", 10, 10], "v_task_without_team_share", "tasks_done"),
      nonPlanifie: parts([12, 12, "m"], "v_unplanned_share", "unplanned_n"),
      fileEnAttente: reponse("v_team_ready_queue", [{ team: EQUIPE, quarter_start: JUGE, ready: c("m") }]),
      bloque: reponse("v_team_blocked_share", [{ team: EQUIPE, quarter_start: JUGE, blocked_n: c(30), blocked: c("m"), share_percent: c("m") }]),
    },
    identifiantEquipe,
    empreinte: "f".repeat(64),
  };
}

function fiche(chart: "lead_cycle_h5" | "lead_cycle_h1"): ReponseFiche {
  return {
    ...corpsDepuisVues(entree(chart)),
    id: "parite-1",
    state: "draft",
    managementQuestion: "predictability",
    effect: { text: "Invented effect.", lang: "en" },
    cause: { text: "Invented cause.", lang: "en" },
  } as ReponseFiche;
}

function lu(chart: "lead_cycle_h5" | "lead_cycle_h1", langue: Langue): string {
  return texteDuMarquage(rendre(h(Fiche, { fiche: fiche(chart), methodeOuverte: true }), langue)).replaceAll("&#x27;", "'");
}

test("the body is a real one: masked cells, insufficient samples, limits and thresholds of the service are all present", () => {
  const h5 = fiche("lead_cycle_h5").method;
  assert.ok(h5.maskedCells.length >= 4, "des cellules masquées attendues");
  assert.ok(h5.limits.length >= 4);
  assert.ok(h5.thresholds.some((s) => s.code === "attachment_threshold_points"));
  const h1 = fiche("lead_cycle_h1").method;
  assert.ok(h1.insufficientSamples.length >= 1, "un échantillon insuffisant attendu");
  assert.ok(h1.maskedCells.length >= 1);
});

for (const chart of ["lead_cycle_h5", "lead_cycle_h1"] as const) {
  for (const langue of ["en", "fr"] as const) {
    test(`a real body of ${chart} rendered in ${langue} shows no "not available" fallback`, () => {
      assert.doesNotMatch(lu(chart, langue), /not available|non disponible/);
    });
  }
}

test("a measure code of the body is shown as its measure and its quarter, never as the raw code", () => {
  const anglais = lu("lead_cycle_h5", "en");
  assert.doesNotMatch(anglais, /@\d{4}-|_days|ready@/);
  assert.match(anglais, /Ready queue, quarter of/);
  assert.match(lu("lead_cycle_h1", "en"), /pooled year/);
});
