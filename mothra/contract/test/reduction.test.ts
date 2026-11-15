// Task 19.5 (A2, A4, A7) and 19.6 (B1): reduceToStatistics on a full F-H5 body, a full F-H1 body and a full dashboard answer, with distinctive
// sentinel counts (7919 and 6007: primes nobody writes by hand). Invented team and figures, no real data.
import assert from "node:assert/strict";
import { test } from "node:test";

import { corpsDepuisVues } from "../src/corps-fiche.ts";
import type { EntreeCorps } from "../src/corps-fiche.ts";
import { identifiantEquipe, scopeFiche } from "../src/equipe.ts";
import { tableauLeadCycle } from "../src/lead-cycle.ts";
import { reduceToStatistics } from "../src/reduction.ts";
import type { LigneReponse, ReponseVue } from "../src/reponse.ts";
import { h1Verdict } from "../src/verdict.ts";
import { DEPART_ECHANTILLON, DEPART_H1, DEPART_H5, DEPART_RATTACHEMENT } from "./depart.ts";

const S1 = 7919; // sentinel: throughput, items
const S2 = 6007; // sentinel: ready queue
const S3 = 9973; // sentinel: items of the pooled year (prime; above S1 and S2 so that the old items never exceed the items, H-01)
const v = (x: number) => ({ state: "value" as const, value: x });
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
const JUGE = DEBUTS[2];
const EQUIPE = "team-a";
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe(EQUIPE) });

function ligne(debut: string | null, debit: number, effectif: number, lm = 40, cm = 10): LigneReponse {
  return {
    team: EQUIPE,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: v(debit),
    items_lt: v(effectif),
    items_ct: v(effectif),
    items_old: v(S2), // S2 < S1 < S3: the old items stay fewer than the items of the row (H-01)
    items_without_commitment: v(S2),
    lead_median_days: v(lm),
    lead_p85_days: v(lm * 2),
    cycle_median_days: v(cm),
    cycle_p85_days: v(cm * 2),
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: v(lm),
    lead_p85_days_excl_old: v(lm * 2),
    cycle_median_days_excl_old: v(cm),
    cycle_p85_days_excl_old: v(cm * 2),
  };
}

function reponse(view: string, rows: LigneReponse[]): ReponseVue {
  return { view, threshold: 5, columns: [], rows, sources: ["flow"] };
}

function vues(debit = S1): EntreeCorps["vues"] {
  const parts = (n: number) => reponse("x", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: v(S1), share_percent: v(n) })));
  return {
    leadCycle: reponse("v_team_lead_time_throughput", [...DEBUTS.map((d) => ligne(d, debit, S1)), ligne(null, debit * 3, S3)]),      // the pooled year is the sum of the three quarters: 3 x debit (before: 4 x debit)
    sansEquipe: parts(10),
    nonPlanifie: parts(12),
    fileEnAttente: reponse("v_team_ready_queue", [{ team: EQUIPE, quarter_start: JUGE, ready: v(S2) }]),
    bloque: reponse("v_team_blocked_share", [{ team: EQUIPE, quarter_start: JUGE, blocked_n: v(S1), blocked: v(S2), share_percent: v(30) }]),
  };
}

const HISTORIQUE = Object.entries({
  h5_band: DEPART_H5.band,
  h5_double_band: DEPART_H5.doubleBand,
  h5_run_rises: DEPART_H5.runRises,
  h5_run_min_cumulative_rise: DEPART_H5.runMinCumulativeRise,
  h5_floor: DEPART_H5.floor,
  h5_low_floor: DEPART_H5.lowFloor,
  h1_lower: DEPART_H1.lower,
  h1_upper: DEPART_H1.upper,
  attachment_threshold_points: DEPART_RATTACHEMENT.thresholdPoints,
  sample_median_min_items: DEPART_ECHANTILLON.medianMinItems,
  sample_p85_min_items: DEPART_ECHANTILLON.p85MinItems,
}).map(([code, value]) => ({ code, value, setOn: "2026-10-27" }));

function corps(chart: "lead_cycle_h5" | "lead_cycle_h1", debit = S1) {
  return corpsDepuisVues({
    chart,
    scope: SCOPE,
    dataDate: "2026-10-05",
    premiereLecture: "2026-10-30",
    historique: HISTORIQUE,
    vues: vues(debit),
    identifiantEquipe,
    empreinte: "f".repeat(64),
  });
}

const textesAvecSentinelle = (x: unknown): string[] =>
  [S1, S2, S3].map(String).filter((s) => new RegExp(`(?<![0-9.])${s}(?![0-9])`).test(JSON.stringify(x)));

// Every key of an object tree, at any depth.
function cles(x: unknown, sortie = new Set<string>()): Set<string> {
  if (Array.isArray(x)) x.forEach((e) => cles(e, sortie));
  else if (x !== null && typeof x === "object") {
    for (const [k, e] of Object.entries(x)) {
      sortie.add(k);
      cles(e, sortie);
    }
  }
  return sortie;
}

test("the complete bodies hold the sentinels (the test sees what it removes)", () => {
  assert.deepEqual(textesAvecSentinelle(corps("lead_cycle_h5")).sort(), [String(S1), String(S2), String(S3)].sort());
  assert.deepEqual(textesAvecSentinelle(corps("lead_cycle_h1")).sort(), [String(S1), String(S2), String(S3)].sort());
});

test("F-H5 reduced: no count at any depth, no items, no measure, no coverage count, no share of a count", () => {
  const reduit = reduceToStatistics(corps("lead_cycle_h5"));
  assert.deepEqual(textesAvecSentinelle(reduit), []);
  const toutes = cles(reduit);
  // (`method.excluded.throughput` lists positions of quarters, not a figure: the key `throughput` is not forbidden.)
  for (const interdite of ["items", "measure", "coverage", "unplannedProductShare", "tasksWithoutTeamShare", "reference"]) {
    assert.ok(!toutes.has(interdite), interdite);
  }
  assert.equal(reduit.method.coverageState, "coverage_sufficient");
  assert.ok(reduit.method.limits.includes("reduced_form"));
});

test("F-H5 reduced keeps the medians and P85, the verdict, its reasons, the positions, the states of the explanations and of the signal", () => {
  const plein = corps("lead_cycle_h5");
  const reduit = reduceToStatistics(plein);
  assert.equal(reduit.verdict, plein.verdict);
  assert.deepEqual(reduit.verdictReasons, plein.verdictReasons);
  assert.deepEqual(reduit.explanations.map((e) => [e.name, e.state, e.reason]), plein.explanations.map((e) => [e.name, e.state, e.reason]));
  assert.equal(reduit.attachmentSignal, plein.attachmentSignal);
  assert.deepEqual(reduit.attachmentSignalReasons, plein.attachmentSignalReasons);
  assert.deepEqual(reduit.chart?.quarters.map((p) => [p.quarter, p.lead, p.cycle]), plein.chart?.quarters.map((p) => [p.quarter, p.lead, p.cycle]));
  assert.deepEqual(reduit.p85, plein.p85);
  assert.equal(reduit.throughputPositions?.length, 3);
  assert.ok(reduit.throughputPositions?.every((p) => p.position === "throughput_within_band"));
  assert.deepEqual(reduit.method.thresholds, plein.method.thresholds);
  assert.equal(reduit.method.fingerprint, plein.method.fingerprint);
  assert.deepEqual(reduit.method.period, plein.method.period);
});

test("the reduced verdict equals the complete verdict on the same data, for both sheet kinds", () => {
  for (const chart of ["lead_cycle_h5", "lead_cycle_h1"] as const) {
    for (const debit of [S1, 3]) {
      const plein = corps(chart, debit);
      assert.equal(reduceToStatistics(plein).verdict, plein.verdict, `${chart} ${String(debit)}`);
    }
  }
});

test("F-H5: a judged quarter far under the reference throughput is under the low floor and the verdict is refuted, in both forms", () => {
  const v2 = vues();
  v2.leadCycle = reponse("v_team_lead_time_throughput", DEBUTS.map((d) => ligne(d, d === JUGE ? 1000 : S1, S1)));
  const plein = corpsDepuisVues({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: "2026-10-05", premiereLecture: null, historique: HISTORIQUE, vues: v2, identifiantEquipe, empreinte: "f".repeat(64) });
  const reduit = reduceToStatistics(plein);
  assert.equal(plein.verdict, "refuted");
  assert.equal(reduit.verdict, "refuted");
  assert.deepEqual(reduit.throughputPositions?.map((p) => p.position), [
    "throughput_within_band",
    "throughput_within_band",
    "throughput_under_low_floor",
  ]);
  assert.deepEqual(textesAvecSentinelle(reduit), []);
});

test("no reference (two quarters only): no position, the verdict is insufficient sample alone (R-20261031-01, Q11)", () => {
  const v2 = vues();
  v2.leadCycle = reponse("v_team_lead_time_throughput", DEBUTS.slice(1).map((d) => ligne(d, S1, S1)));
  const plein = corpsDepuisVues({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: "2026-10-05", premiereLecture: null, historique: HISTORIQUE, vues: v2, identifiantEquipe, empreinte: "f".repeat(64) });
  assert.equal(plein.verdict, "insufficient_sample");
  assert.deepEqual(plein.throughputPositions, []);
  assert.deepEqual(reduceToStatistics(plein).throughputPositions, []);
});

test("F-H1 reduced: ratios with their states, no position, no throughput, no count", () => {
  const plein = corps("lead_cycle_h1");
  const reduit = reduceToStatistics(plein);
  assert.deepEqual(textesAvecSentinelle(reduit), []);
  assert.equal(reduit.throughputPositions, undefined);
  assert.deepEqual(reduit.ratios?.pooledYear, { quarter: "pooled_year", median: { state: "value", value: 4 }, p85: { state: "value", value: 4 } });
  assert.equal(reduit.ratios?.quarters.length, 3);
  assert.equal(reduit.method.coverageState, "coverage_sufficient");
  assert.equal(reduit.verdict, plein.verdict);
});

test("the coverage state is computed against the P85 size: exactly at it sufficient, one under insufficient, masked masked", () => {
  const taille = DEPART_ECHANTILLON.p85MinItems;
  const avec = (effectif: number | "m") => {
    const v2 = vues();
    v2.leadCycle = reponse(
      "v_team_lead_time_throughput",
      DEBUTS.map((d) => {
        const l = ligne(d, S1, S1);
        if (d === JUGE) l.items_ct = effectif === "m" ? { state: "masked", threshold: 5 } : v(effectif);
        return l;
      }),
    );
    return reduceToStatistics(corpsDepuisVues({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: "2026-10-05", premiereLecture: null, historique: HISTORIQUE, vues: v2, identifiantEquipe, empreinte: "f".repeat(64) }));
  };
  assert.equal(avec(taille).method.coverageState, "coverage_sufficient");
  assert.equal(avec(taille - 1).method.coverageState, "coverage_insufficient");
  assert.equal(avec("m").method.coverageState, "coverage_masked");
});

test("h1Verdict reads only the ratios of the pooled year: the throughput of each quarter changes nothing", () => {
  const verdictDe = (debit: number) => corps("lead_cycle_h1", debit).verdict;
  assert.equal(verdictDe(S1), verdictDe(3));
  // The function takes the two ratios of the pooled year and the thresholds: no throughput among its inputs.
  const entree = { medianRatio: 4, p85Ratio: 4, lower: DEPART_H1.lower, upper: DEPART_H1.upper, medianSampleSufficient: true, p85SampleSufficient: true };
  assert.deepEqual(Object.keys(entree).sort(), ["lower", "medianRatio", "medianSampleSufficient", "p85Ratio", "p85SampleSufficient", "upper"]);
  assert.equal(h1Verdict(entree).verdict, "confirmed");
});

test("a dashboard answer reduced: medians and states, no items in the series, none of the sentinels", () => {
  const plein = tableauLeadCycle(vues().leadCycle, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe);
  assert.ok(textesAvecSentinelle(plein).length > 0);
  const reduit = reduceToStatistics(plein);
  assert.deepEqual(textesAvecSentinelle(reduit), []);
  assert.ok(!cles(reduit).has("items"));
  assert.equal(reduit.teams[0].points.length, plein.teams[0].points.length);
  assert.deepEqual(reduit.teams[0].points[0].lead, plein.teams[0].points[0].lead);
});

test("reducing twice gives the same answer", () => {
  const une = reduceToStatistics(corps("lead_cycle_h5"));
  assert.deepEqual(reduceToStatistics(une), une);
});
