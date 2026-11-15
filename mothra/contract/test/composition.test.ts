// Lot 1 of mothra-demo-habillage (D3, D5, D15): the composition of the lead time and the display state. Every sheet answer comes from
// corpsDepuisVues applied to synthetic view rows (R-20261031-61), never from an object written by hand; the pure state function takes free inputs.
import assert from "node:assert/strict";
import { test } from "node:test";

import { corpsDepuisVues } from "../src/corps-fiche.ts";
import type { EntreeCorps, EntreeHistorique } from "../src/corps-fiche.ts";
import { compositionConviction, etatAffichage, verifierEtatAffichage } from "../src/composition.ts";
import { identifiantEquipe, scopeFiche } from "../src/equipe.ts";
import type { LigneReponse, ReponseVue } from "../src/reponse.ts";
import { DEPART_ECHANTILLON, DEPART_H1, DEPART_H5, DEPART_RATTACHEMENT } from "./depart.ts";

const M = { state: "masked" as const, threshold: 5 };
type Entier = number | "m";
const c = (x: Entier) => (x === "m" ? M : { state: "value" as const, value: x });

const DATE = "2026-10-05";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
const EQUIPE = "team-a";
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe(EQUIPE) });

interface Opts {
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

// trimestres: one option set per quarter of the window (null: no row); annee: the pooled-year row.
function fiche(chart: "lead_cycle_h1" | "lead_cycle_h5", trimestres: Array<Opts | null>, annee: Opts = {}, seuils: Record<string, number> = {}) {
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

const TROIS: Opts[] = [{}, {}, {}];      // three quarters since R-20261114-49 (renamed from QUATRE, rename only)

test("values: median lead time 36 and cycle time 10 give 26 days of waiting, 10 of work and shares summing to 100", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10 }));
  assert.equal(r.measured.quarter, "pooled_year");
  assert.equal(r.measured.state, "value");
  assert.deepEqual(r.measured.waitDays, { state: "value", value: 26 });
  assert.deepEqual(r.measured.workDays, { state: "value", value: 10 });
  assert.deepEqual(r.measured.leadDays, { state: "value", value: 36 });
  // R-20261101-43: the shares of the measured period moved to partsDAttente (parts-attente.test.ts, same expected value).
});

test("quarters: one entry per point of the chart, in order, with waiting, work and lead time", () => {
  const f = fiche("lead_cycle_h1", TROIS);
  const r = compositionConviction(f);
  assert.deepEqual(
    r.quarters.map((q) => q.quarter),
    f.chart?.quarters.map((q) => q.quarter),
  );
  assert.equal(r.quarters.length, 3);
  assert.deepEqual(r.quarters[0].waitDays, { state: "value", value: 5 });
  assert.deepEqual(r.quarters[0].workDays, { state: "value", value: 10 });
});

// R-20261101-43: the tests of the markers (adopted thresholds as shares, a threshold of 1 or under, a threshold of 0 or under) moved to
// parts-attente.test.ts, on `waitShares`.

test("masked lead time: waiting and lead time are the masked cell with its threshold, no number", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", TROIS, { lm: "m" }));
  assert.equal(r.measured.state, "masked");
  assert.deepEqual(r.measured.waitDays, { state: "masked", threshold: 5 });
  assert.deepEqual(r.measured.leadDays, { state: "masked", threshold: 5 });
});

test("masked cycle time: waiting and work are the masked cell with threshold 5, in a quarter too", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{}, { cm: "m" }, {}], { cm: "m" }));
  assert.deepEqual(r.measured.waitDays, { state: "masked", threshold: 5 });
  assert.deepEqual(r.measured.workDays, { state: "masked", threshold: 5 });
  assert.equal(r.quarters[1].state, "masked");
  assert.deepEqual(r.quarters[1].waitDays, { state: "masked", threshold: 5 });
  assert.deepEqual(r.quarters[1].workDays, { state: "masked", threshold: 5 });
  assert.equal(r.quarters[0].state, "value");
});

test("one median insufficient: no waiting is served for the quarter, the visible term stays; the measured period serves no figure", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{}, { ctN: 7 }, {}], { ctN: 7 }));
  assert.equal(r.measured.state, "insufficient_sample");
  assert.deepEqual(r.measured.waitDays, { state: "insufficient_sample" });
  assert.deepEqual(r.measured.workDays, { state: "insufficient_sample" });
  assert.deepEqual(r.measured.leadDays, { state: "insufficient_sample" });
  assert.equal(r.quarters[1].state, "insufficient_sample");
  assert.deepEqual(r.quarters[1].waitDays, { state: "insufficient_sample" });
  assert.deepEqual(r.quarters[1].leadDays, { state: "value", value: 15 });
});

test("a P85 too short (15 items) with both medians visible: the service gives not settled (p85_insufficient_sample), figures are served", () => {
  const f = fiche("lead_cycle_h1", TROIS, { ltN: 15, ctN: 15, lm: 36, cm: 10 });
  assert.equal(f.verdict, "not_settled");
  assert.deepEqual(f.h1Reasons, ["p85_insufficient_sample"]);
  const r = compositionConviction(f);
  assert.equal(r.state, "not_settled");
  assert.deepEqual(r.measured.waitDays, { state: "value", value: 26 });
});

test("Q121: insufficient sample with one median visible (lead 36 days): the state is insufficient_sample and no figure is served", () => {
  const f = fiche("lead_cycle_h1", TROIS, { ctN: 7, lm: 36, cm: 10 });
  assert.equal(f.verdict, "insufficient_sample");
  assert.deepEqual(f.chart?.pooledYear?.lead, { state: "value", value: 36 });
  const r = compositionConviction(f);
  assert.equal(r.state, "insufficient_sample");
  assert.equal(r.measured.state, "insufficient_sample");
  for (const j of [r.measured.waitDays, r.measured.workDays, r.measured.leadDays]) {
    assert.deepEqual(j, { state: "insufficient_sample" });
  }
});

test("Q121: a masked state serves only the masked cell, never a visible term", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", TROIS, { lm: "m" }));
  assert.equal(r.state, "masked");
  assert.deepEqual(r.measured.workDays, { state: "masked", threshold: 5 });
});

test("lead time under cycle time: not_comparable, no waiting value, never a corrected number", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{}, { lm: 8, cm: 10 }, {}], { lm: 8, cm: 10 }));
  assert.equal(r.measured.state, "not_comparable");
  assert.deepEqual(r.measured.waitDays, { state: "not_comparable" });
  assert.equal(r.quarters[1].state, "not_comparable");
  assert.deepEqual(r.quarters[1].waitDays, { state: "not_comparable" });
});

test("lead time equal to cycle time: zero waiting", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", TROIS, { lm: 10, cm: 10 }));
  assert.deepEqual(r.measured.waitDays, { state: "value", value: 0 });
  // R-20261101-43: the measured period's shares (0 and 100) moved to partsDAttente (ratio 1, parts-attente.test.ts).
});

test("lead time zero in a quarter: zero days, no share (a division by zero is never served)", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{}, { lm: 0, cm: 0 }, {}]));
  assert.equal(r.quarters[1].state, "value");
  assert.deepEqual(r.quarters[1].waitDays, { state: "value", value: 0 });
  assert.equal(r.quarters[1].waitShare, undefined);
  assert.equal(r.quarters[1].workShare, undefined);
});

test("display state: the service's verdict on a measured period, for a refuted and a not settled hypothesis 1", () => {
  const refutee = fiche("lead_cycle_h1", TROIS, { lm: 12, cm: 10 });
  assert.equal(refutee.verdict, "refuted");
  assert.equal(compositionConviction(refutee).state, "refuted");
  const milieu = fiche("lead_cycle_h1", TROIS, { lm: 25, cm: 10 });
  assert.equal(milieu.verdict, "not_settled");
  assert.equal(compositionConviction(milieu).state, "not_settled");
  const haute = fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10, lp: 100, cp: 20 });
  // The competing explanations cap a confirmation at not settled (D33), so "confirmed" is not reachable from corpsDepuisVues today:
  // it is covered by the pure function below.
  assert.equal(haute.verdict, "not_settled");
  assert.equal(compositionConviction(haute).state, "not_settled");
});

test("display state: insufficient sample with a masked pooled-year median is masked, without a masked term it stays insufficient", () => {
  const masquee = fiche("lead_cycle_h1", TROIS, { lm: "m" });
  assert.equal(masquee.verdict, "insufficient_sample");
  assert.equal(compositionConviction(masquee).state, "masked");
  const courte = fiche("lead_cycle_h1", TROIS, { ltN: 7, ctN: 7 });
  assert.equal(courte.verdict, "insufficient_sample");
  const r = compositionConviction(courte);
  assert.equal(r.state, "insufficient_sample");
  assert.deepEqual(r.measured.waitDays, { state: "insufficient_sample" });
  assert.deepEqual(r.measured.workDays, { state: "insufficient_sample" });
});

test("display state: the five values, from the pure function", () => {
  for (const v of ["confirmed", "refuted", "not_settled", "insufficient_sample"]) {
    assert.equal(etatAffichage(v, false), v);
    assert.equal(etatAffichage(v, true), v === "insufficient_sample" ? "masked" : v);
  }
  assert.equal(verifierEtatAffichage("masked"), "masked");
});

test("display state: a state outside the five gives the message", () => {
  assert.throws(() => verifierEtatAffichage("almost"), { message: "état d'affichage inconnu : almost" });
  assert.throws(() => etatAffichage("bogus", false), { message: "état d'affichage inconnu : bogus" });
});

test("hypothesis 5: the measured period is the judged quarter (no waitShares: parts-attente.test.ts)", () => {
  const f = fiche("lead_cycle_h5", TROIS);
  const r = compositionConviction(f);
  assert.equal(r.measured.quarter, "2026-Q3");
  assert.equal(f.verdict, "not_settled");
  assert.equal(r.state, "not_settled");
  assert.deepEqual(r.measured.waitDays, { state: "value", value: 5 });
});

test("hypothesis 5: insufficient sample with a masked cycle time in the judged quarter is masked", () => {
  const f = fiche("lead_cycle_h5", [null, {}, { cm: "m" }]);
  assert.equal(f.verdict, "insufficient_sample");
  const r = compositionConviction(f);
  assert.equal(r.state, "masked");
});

// Lot 1b (R-20261101-05, Q140, design D3): `axisShare`, the lead time of a quarter over the largest lead time among the quarters whose lead
// time is a value, so that the rows of the composition chart have comparable lengths with no computation in the front.
test("axisShare: values, 100 x lead time / largest lead time of the visible quarters", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{ lm: 20, cm: 10 }, { lm: 40, cm: 10 }, { lm: 30, cm: 10 }]));
  // By hand (R-20261114-49, three quarters, the fourth, 10 over 40 = 25, is gone): the largest is 40, so 20 / 40 = 50, 40 / 40 = 100, 30 / 40 = 75.
  assert.deepEqual(
    r.quarters.map((q) => q.axisShare),
    [50, 100, 75],
  );
});

test("axisShare: the largest quarter is at 100, whatever its position", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{ lm: 40, cm: 10 }, { lm: 20, cm: 10 }, {}]));
  assert.equal(r.quarters[0].axisShare, 100);
  assert.equal(r.quarters[1].axisShare, 50);
});

test("axisShare: a masked quarter has none and does not enter the largest", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{ lm: 20, cm: 10 }, { lm: 40, cm: 10 }, { lm: "m" }]));
  assert.equal(r.quarters[2].state, "masked");
  assert.equal(r.quarters[2].axisShare, undefined);
  assert.equal(r.quarters[0].axisShare, 50);
  assert.equal(r.quarters[1].axisShare, 100);
});

test("axisShare: a quarter whose lead time is an insufficient sample has none, and does not enter the largest", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{ lm: 20, cm: 10 }, { ltN: 7, lm: 90, cm: 10 }, { lm: 40, cm: 10 }]));
  assert.deepEqual(r.quarters[1].leadDays, { state: "insufficient_sample" });
  assert.equal(r.quarters[1].axisShare, undefined);
  assert.equal(r.quarters[0].axisShare, 50);
  assert.equal(r.quarters[2].axisShare, 100);
});

test("axisShare: a quarter whose cycle time is an insufficient sample keeps its lead time on the axis, with no waiting", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{ lm: 20, cm: 10 }, { ctN: 7, lm: 40, cm: 10 }, {}]));
  assert.equal(r.quarters[1].state, "insufficient_sample");
  assert.equal(r.quarters[1].axisShare, 100);
  assert.equal(r.quarters[0].axisShare, 50);
});

test("axisShare: lead times all at zero give none (a division by zero is never served)", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", [{ lm: 0, cm: 0 }, { lm: 0, cm: 0 }, { lm: 0, cm: 0 }]));
  assert.deepEqual(
    r.quarters.map((q) => q.axisShare),
    [undefined, undefined, undefined],
  );
});

test("axisShare: the measured period has none and no shares, the verdict reads days only", () => {
  const r = compositionConviction(fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10 }));
  assert.deepEqual(Object.keys(r.measured).sort(), ["leadDays", "quarter", "state", "waitDays", "workDays"]);
  assert.deepEqual(Object.keys(r).sort(), ["measured", "quarters", "state"]);
});
