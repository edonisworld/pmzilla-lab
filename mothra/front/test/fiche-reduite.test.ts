// Task 19.5 (A8): the sheet screen renders the reduced form from the catalogues: the throughput positions, the states of the explanations and of
// the signal, the coverage state, the label `reduced_form`, and `synthetic_dataset_notice` when the answer's code `dataset` is synthetic. The body is
// the real output of the contract on synthetic views with sentinel counts, then reduced by the contract: the screen computes nothing.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import { corpsDepuisVues, reduceToStatistics } from "@mothra/contract";
// (reduceToStatistics is also used below on a dashboard answer.)
import type { LigneReponse, ReponseLeadCycle, ReponseVue } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import type { ReponseFiche } from "../src/api/fiche.ts";
import { Fiche } from "../src/composants/Fiche.ts";
import { ContenuTableau } from "../src/pages/PageTableau.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { choixRadio, rendre, texte as texteDuMarquage } from "./rendu.ts";

const S = 7919; // sentinel count
const v = (x: number) => ({ state: "value" as const, value: x });
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe("team-a") });

function reponse(view: string, rows: LigneReponse[]): ReponseVue {
  return { view, threshold: 5, columns: [], rows, sources: ["flow"] };
}

function ligne(debut: string | null, debit: number): LigneReponse {
  return {
    team: "team-a",
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: v(debit),
    items_lt: v(S),
    items_ct: v(S),
    items_old: v(0), // R-20261106-66 : valait l'effectif (S), donc une taille de H1 nulle
    items_without_commitment: v(S),
    lead_median_days: v(40),
    lead_p85_days: v(80),
    cycle_median_days: v(10),
    cycle_p85_days: v(20),
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: v(40),
    lead_p85_days_excl_old: v(80),
    cycle_median_days_excl_old: v(10),
    cycle_p85_days_excl_old: v(20),
  };
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

function fiche(chart: "lead_cycle_h5" | "lead_cycle_h1", dataset: "synthetic" | "real", debitJuge = S): ReponseFiche {
  const parts = (n: number) => reponse("x", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: v(S), share_percent: v(n) })));
  const corps = corpsDepuisVues({
    chart,
    scope: SCOPE,
    dataDate: "2026-10-05",
    premiereLecture: null,
    historique: SEUILS.map(([code, value]) => ({ code, value, setOn: "2026-10-27" })),
    vues: {
      leadCycle: reponse("v_team_lead_time_throughput", [...DEBUTS.map((d, i) => ligne(d, i === 2 ? debitJuge : S)), ligne(null, S * 3)]),
      sansEquipe: parts(10),
      nonPlanifie: parts(12),
      fileEnAttente: reponse("v_team_ready_queue", [{ team: "team-a", quarter_start: DEBUTS[2], ready: v(6007) }]),
      bloque: reponse("v_team_blocked_share", [{ team: "team-a", quarter_start: DEBUTS[2], blocked_n: v(S), blocked: v(6007), share_percent: v(30) }]),
    },
    identifiantEquipe,
    empreinte: "f".repeat(64),
  });
  const avecJeu = { ...corps, dataset };
  return {
    ...(dataset === "real" ? reduceToStatistics(avecJeu) : avecJeu),
    id: "reduite-1",
    state: "draft",
    managementQuestion: "predictability",
    effect: { text: "Invented effect.", lang: "en" },
    cause: { text: "Invented cause.", lang: "en" },
  } as ReponseFiche;
}

function lu(f: ReponseFiche, langue: Langue): string {
  return texteDuMarquage(rendre(h(Fiche, { fiche: f, methodeOuverte: true }), langue)).replaceAll("&#x27;", "'");
}

const en = catalogues.en;
const fr = catalogues.fr;

test("the labels of D29 for the reduced form are in both catalogues, as the design writes them", () => {
  assert.equal(en["fiche.position.throughput_within_band"], "throughput within the band");
  assert.equal(en["fiche.position.throughput_under_floor"], "throughput under the floor");
  assert.equal(en["fiche.position.throughput_under_low_floor"], "throughput under the low floor");
  assert.equal(en["fiche.coverageState.coverage_sufficient"], "coverage sufficient");
  assert.equal(en["fiche.coverageState.coverage_insufficient"], "coverage insufficient");
  assert.equal(en["fiche.coverageState.coverage_masked"], "coverage masked");
  assert.equal(en["fiche.limit.reduced_form"], "reduced form: statistics and states only, no counts");
  assert.equal(en["fiche.signal.notRaised"], "No attachment signal");
  assert.equal(en["fiche.syntheticNotice"], "On the synthetic dataset, not on real data.");
  assert.equal(fr["fiche.position.throughput_under_floor"], "débit sous le plancher");
  assert.equal(fr["fiche.limit.reduced_form"], "forme réduite : statistiques et états seulement, sans effectifs");
  assert.equal(fr["fiche.syntheticNotice"], "Sur le jeu synthétique, pas sur des données réelles.");
});

for (const langue of ["en", "fr"] as const) {
  test(`a reduced F-H5 body rendered in ${langue}: positions, coverage state, reduced form, signal state; no count, no fallback`, () => {
    const t = lu(fiche("lead_cycle_h5", "real"), langue);
    const c = catalogues[langue];
    assert.ok(t.includes(c["fiche.position.throughput_within_band"]));
    assert.ok(t.includes(c["fiche.coverageState.coverage_sufficient"]));
    assert.ok(t.includes(c["fiche.limit.reduced_form"]));
    assert.ok(t.includes(c["fiche.signal.notRaised"]));
    assert.ok(!t.includes(c["fiche.syntheticNotice"]), "no synthetic notice on real data");
    assert.doesNotMatch(t, /7919|6007/);
    assert.doesNotMatch(t, /not available|non disponible/);
  });

  test(`a reduced F-H5 body with a judged quarter under the floor shows that position in ${langue}`, () => {
    const t = lu(fiche("lead_cycle_h5", "real", 1000), langue);
    assert.ok(t.includes(catalogues[langue]["fiche.position.throughput_under_low_floor"]));
    assert.doesNotMatch(t, /7919|6007/);
  });

  test(`a synthetic body is complete and carries the notice next to the verdict and on the method face in ${langue}`, () => {
    const f = fiche("lead_cycle_h5", "synthetic");
    const marquage = rendre(h(Fiche, { fiche: f, methodeOuverte: true }), langue);
    const notice = catalogues[langue]["fiche.syntheticNotice"];
    assert.equal(marquage.split(notice).length - 1, 2, "the notice appears twice: next to the verdict and on the method face");
    assert.ok(!lu(f, langue).includes(catalogues[langue]["fiche.limit.reduced_form"]));
  });
}

// Q48 (a) of R-20261031-19: on real data the creation form does not offer the sheet of hypothesis 5, and offers the other; on the synthetic
// dataset it offers both. No raw error: the form simply holds one choice less.
function formulaire(dataset: "synthetic" | "real", langue: Langue = "en"): string {
  const point = { quarter: "2026-Q3", lead: { state: "value" as const, value: 15 }, cycle: { state: "value" as const, value: 10 }, items: { state: "value" as const, value: 30 } };
  const donnees: ReponseLeadCycle = {
    threshold: 5,
    dataDate: "2026-10-05",
    dataset,
    product: [],
    teams: [{ team: "Team A", teamId: identifiantEquipe("Team A"), points: [point] }],
  };
  return rendre(
    h(ContenuTableau, { reponse: donnees, portee: "Team A", surPortee: () => undefined, fiche: { genre: "formulaire" }, surFaire: () => undefined, surCreer: () => undefined, simulee: false }),
    langue,
  ).replaceAll("&#x27;", "'");
}

// R-20261101-40 (lot 3d, D18): hypothesis 5 is shown disabled with its reason on real data instead of hidden; the assertion stays as strict
// (no enabled hypothesis 5 choice on real data).
test("the creation form does not offer hypothesis 5 on real data, and offers both on the synthetic dataset", () => {
  for (const langue of ["en", "fr"] as const) {
    assert.deepEqual(choixRadio(formulaire("real", langue)).filter((c) => !c.desactive).map((c) => c.valeur), ["lead_cycle_h1"], langue);
    assert.ok(formulaire("real", langue).includes(catalogues[langue]["tableau.form.h5RealUnavailable"]), langue);
    assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(formulaire("real", langue))?.[0] ?? "").includes(catalogues[langue]["conviction.nav.lead_cycle_h1"]), langue);
    assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(formulaire("synthetic", langue))?.[0] ?? "").includes(catalogues[langue]["conviction.nav.lead_cycle_h5"]), langue);
  }
});

// Review of 19.5/19.6, B1: the dashboard receives, on real data, what the server really sends: the answer reduced by the contract, whose points
// carry no `items`. The screen renders it without exception, with no Items column, and offers hypothesis 1 only.
test("a really reduced dashboard answer renders without exception: no Items column, hypothesis 1 only", () => {
  const point = { quarter: "2026-Q3", lead: { state: "value" as const, value: 15 }, cycle: { state: "value" as const, value: 10 }, items: { state: "value" as const, value: S } };
  const complet: ReponseLeadCycle = {
    threshold: 5,
    dataDate: "2026-10-05",
    product: [],
    teams: [{ team: "Team A", teamId: identifiantEquipe("Team A"), points: [point] }],
  };
  const reduite = reduceToStatistics({ ...complet, dataset: "real" });
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const html = rendre(
      h(ContenuTableau, { reponse: reduite, portee: "Team A", surPortee: () => undefined, fiche: { genre: "formulaire" }, surFaire: () => undefined, surCreer: () => undefined, simulee: false }),
      langue,
    ).replaceAll("&#x27;", "'");
    assert.ok(!html.includes(c["tableau.column.items"]), `${langue}: no Items header`);
    assert.doesNotMatch(html, /7919/);
    assert.ok(html.includes(c["tableau.column.lead"]), langue);
    assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(html)?.[0] ?? "").includes(c["conviction.nav.lead_cycle_h1"]), langue);
    // R-20261101-40 (lot 3d): hypothesis 5 is disabled with its reason on real data, never enabled.
    assert.deepEqual(choixRadio(html).filter((x) => !x.desactive).map((x) => x.valeur), ["lead_cycle_h1"], langue);
    assert.ok(html.includes(c["tableau.form.h5RealUnavailable"]), langue);
  }
  // The complete answer keeps its Items column.
  const pleine = rendre(
    h(ContenuTableau, { reponse: { ...complet, dataset: "synthetic" }, portee: "Team A", surPortee: () => undefined, fiche: { genre: "aucune" }, surFaire: () => undefined, surCreer: () => undefined, simulee: false }),
    "en",
  );
  assert.ok(pleine.includes(en["tableau.column.items"]));
});

test("a reduced F-H1 body shows no position", () => {
  const t = lu(fiche("lead_cycle_h1", "real"), "en");
  assert.ok(!t.includes(en["fiche.positions.title"]));
  assert.ok(t.includes(en["fiche.limit.reduced_form"]));
});
