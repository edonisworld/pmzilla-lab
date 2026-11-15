// Task 18.4: the computed body of a sheet from masked view answers written by hand (the form that the masking of task 15.3 gives: every count,
// statistic and share is a cell). Invented teams and figures, no real data. Starting values of the synthetic runs from ./depart.ts.
import assert from "node:assert/strict";
import { test } from "node:test";

import { GraphiqueInconnu, PorteeNonServie, SeuilsNonFixes, corpsDepuisVues, lireSeuils, verifierCreation } from "../src/corps-fiche.ts";
import type { EntreeCorps, EntreeHistorique } from "../src/corps-fiche.ts";
import { identifiantEquipe, porteeDeScope, scopeFiche } from "../src/equipe.ts";
import { CODES_LIMITES, codeMesure, lireCodeMesure } from "../src/listes-fiche.ts";
import { tableauLeadCycle } from "../src/lead-cycle.ts";
import { servirTableau } from "../src/reduction.ts";
import type { LigneReponse, ReponseVue } from "../src/reponse.ts";
import { DEPART_ECHANTILLON, DEPART_H1, DEPART_H5, DEPART_RATTACHEMENT } from "./depart.ts";

const M = { state: "masked" as const, threshold: 5 };
type Entier = number | "m";
const c = (x: Entier) => (x === "m" ? M : { state: "value" as const, value: x });

const DATE = "2026-10-05"; // judged quarter 2026-07-01; reference quarters 2026-01-01, 2026-04-01 (the three closed quarters, R-20261114-49)
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;
const JUGE = DEBUTS[2];
const EQUIPE = "team-a";
// The real identifier and the real scope of the contract (review of 18.4, A1): no identity double.
const identifiant = identifiantEquipe;
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe(EQUIPE) });

function reponse(view: string, rows: LigneReponse[]): ReponseVue {
  return { view, threshold: 5, columns: [], rows, sources: ["flow"] };
}

interface OptsTrimestre {
  n?: Entier; // throughput
  ltN?: Entier; // items_lt
  ctN?: Entier; // items_ct
  lm?: Entier;
  lp?: Entier;
  cm?: Entier;
  cp?: Entier;
}

function ligneLead(debut: string | null, o: OptsTrimestre, equipe = EQUIPE): LigneReponse {
  return {
    team: equipe,
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

const STABLE: OptsTrimestre[] = [{}, {}, {}];

function leadCycle(trimestres: Array<OptsTrimestre | null>, annee: OptsTrimestre | null = {}): ReponseVue {
  const rows: LigneReponse[] = [];
  trimestres.forEach((o, i) => {
    if (o !== null) rows.push(ligneLead(DEBUTS[i], o));
  });
  if (annee !== null) rows.push(ligneLead(null, annee));
  return reponse("v_team_lead_time_throughput", rows);
}

function parts(valeurs: Array<Entier | null>, vue: string, colonneNombre = "tasks_done"): ReponseVue {
  return reponse(
    vue,
    valeurs.flatMap((v, i) => (v === null ? [] : [{ quarter_start: DEBUTS[i], [colonneNombre]: c(30), share_percent: c(v) }])),
  );
}

function vuesDe(over: Partial<EntreeCorps["vues"]> = {}, trimestres: Array<OptsTrimestre | null> = STABLE): EntreeCorps["vues"] {
  return {
    leadCycle: leadCycle(trimestres),
    sansEquipe: parts([10, 10, 10], "v_task_without_team_share"),
    nonPlanifie: parts([12, 12, 12], "v_unplanned_share", "unplanned_n"),
    fileEnAttente: reponse("v_team_ready_queue", [{ team: EQUIPE, quarter_start: JUGE, ready: c(12) }]),
    bloque: reponse("v_team_blocked_share", [{ team: EQUIPE, quarter_start: JUGE, blocked_n: c(30), blocked: c(9), share_percent: c(30) }]),
    ...over,
  };
}

export function historiqueDeDepart(setOn = "2026-10-27"): EntreeHistorique[] {
  const entrees: Array<[string, number]> = [
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
  return entrees.map(([code, value]) => ({ code, value, setOn }));
}

function entree(over: Partial<EntreeCorps> = {}): EntreeCorps {
  return {
    chart: "lead_cycle_h5",
    scope: SCOPE,
    dataDate: DATE,
    premiereLecture: "2026-10-30",
    historique: historiqueDeDepart(),
    vues: vuesDe(),
    identifiantEquipe: identifiant,
    empreinte: "f".repeat(64),
    ...over,
  };
}

const RAISONS_STABLES = [
  { explanation: "unplanned_work", state: "not_measurable", reason: "defects_without_team" },
  { explanation: "capacity", state: "not_ruled_out", reason: "no_adopted_threshold" },
  { explanation: "dependencies", state: "not_ruled_out", reason: "no_adopted_threshold" },
];

test("F-H5: three stable quarters would confirm, the competing explanations cap the verdict at not settled with their reasons", () => {
  const corps = corpsDepuisVues(entree());
  assert.equal(corps.verdict, "not_settled");
  assert.deepEqual(corps.verdictReasons, RAISONS_STABLES);
  assert.equal(corps.method.hypothesis, "h5");
  assert.deepEqual(corps.h5Reasons, []);
  assert.deepEqual(corps.method.period.quarters, [
    { year: 2026, quarter: 1 },
    { year: 2026, quarter: 2 },
    { year: 2026, quarter: 3 },
  ]);
  assert.equal(corps.method.fingerprint, "f".repeat(64));
  assert.deepEqual(corps.method.coverage, { state: "value", value: 30 });
});

test("F-H5: a rising run of the median refutes, and the cap keeps a refutation", () => {
  const corps = corpsDepuisVues(entree({ vues: vuesDe({}, [{ cm: 10 }, { cm: 11 }, { cm: 12 }]) }));
  assert.equal(corps.verdict, "refuted");
});

test("F-H5 (task 2.3c, D14): with three complete closed quarters \"refuted\" stays reachable by the double band alone, with the finding h5_double_band", () => {
  // By hand: the medians 5, 5 and 30 have the mean 40 / 3 = 13.33 and the P85s 10, 10 and 60 the mean 80 / 3 = 26.67. The gaps are |5 - 13.33| / 13.33 = 0.625 and
  // |30 - 13.33| / 13.33 = 1.25 for the medians, the same for the P85s (|10 - 26.67| / 26.67 = 0.625, |60 - 26.67| / 26.67 = 1.25): the three quarters are beyond the
  // double band of 0.4, and two are enough. No rising run (5, 5 then 30: one rise at most, the second quarter is not above the first), no throughput under the
  // low floor (30 in every quarter, ratio 1): the one finding is the double band.
  const corps = corpsDepuisVues(entree({ vues: vuesDe({}, [{ cm: 5, cp: 10 }, { cm: 5, cp: 10 }, { cm: 30, cp: 60 }]) }));
  assert.equal(corps.verdict, "refuted");
  assert.deepEqual(corps.verdictFindings, ["h5_double_band"]);
  assert.deepEqual(corps.h5Reasons, []);
  // The same quarters with a quarter missing: no reference, no refutation (no two-quarter rule).
  const sans = corpsDepuisVues(entree({ vues: vuesDe({}, [null, { cm: 5, cp: 10 }, { cm: 30, cp: 60 }]) }));
  assert.equal(sans.verdict, "insufficient_sample");
});

test("F-H5: three complete quarters give a reference, two give none and the verdict is insufficient sample", () => {
  const trois = corpsDepuisVues(entree({ vues: vuesDe({}, [{}, {}, {}]) }));
  assert.equal(trois.verdict, "not_settled");
  const deux = corpsDepuisVues(entree({ vues: vuesDe({}, [null, {}, {}]) }));
  assert.equal(deux.verdict, "insufficient_sample");
});

test("F-H5: a masked throughput at the judged quarter leaves it out of the mean, the cell kept as the view gave it; with three closed quarters only two are complete: no reference, insufficient sample (R-20261114-83)", () => {
  const corps = corpsDepuisVues(entree({ vues: vuesDe({}, [{}, {}, { n: "m" }]) }));
  assert.equal(corps.verdict, "insufficient_sample");      // before: four quarters, three complete ones, "not_settled" with the reason throughput_masked
  assert.deepEqual(corps.h5Reasons, []);
  assert.deepEqual(corps.method.excluded.throughput, [2]);
  assert.deepEqual(corps.method.maskedCells, [{ measure: `throughput@${JUGE}`, cell: { state: "masked", threshold: 5 } }]);
});

test("F-H5: a masked P85, a masked throughput or a short sample in a reference quarter gives no reference (insufficient sample)", () => {
  for (const mauvais of [{ cp: "m" as const }, { n: "m" as const }, { ctN: 15 }]) {
    const corps = corpsDepuisVues(entree({ vues: vuesDe({}, [mauvais, {}, {}]) }));
    assert.equal(corps.verdict, "insufficient_sample", JSON.stringify(mauvais));
  }
});

test("F-H5: a median on 5 to 9 items is an insufficient sample, listed apart from the masked cells", () => {
  const corps = corpsDepuisVues(entree({ vues: vuesDe({}, [{}, {}, { ctN: 7 }]) }));
  assert.deepEqual(corps.method.insufficientSamples, [`cycle_median_days@${JUGE}`, `cycle_p85_days@${JUGE}`]);
  assert.deepEqual(corps.method.excluded.median, [2]);
  assert.deepEqual(corps.method.maskedCells, []);
});

test("signal: a gap of the judged share above 10 points raises it, shown with the verdict reason; equal to 10 raises nothing", () => {
  // R-20261114-51, D13: the reference is the mean of the TWO closed quarters before the judged one: 10 and 14, mean 12, as 10, 12 and 14 gave before, so the gaps
  // are the former ones: 25 - 12 = 13 (raised) and 22 - 12 = 10 (the threshold, nothing raised).
  const haut = corpsDepuisVues(entree({ vues: vuesDe({ sansEquipe: parts([10, 14, 25], "v_task_without_team_share") }) }));
  assert.equal(haut.attachmentSignal, "raised");
  assert.equal(haut.attachmentSignalShown, true);
  assert.ok(haut.verdictReasons.some((r) => r.reason === "tasks_attachment_signal"));
  assert.deepEqual(haut.tasksWithoutTeamShare, { state: "value", value: 25 });
  const egal = corpsDepuisVues(entree({ vues: vuesDe({ sansEquipe: parts([10, 14, 22], "v_task_without_team_share") }) }));
  assert.equal(egal.attachmentSignal, "not_raised");
  assert.equal(egal.attachmentSignalShown, false);
});

test("signal (D13): the reference is the mean of the two closed quarters before the judged one; a masked reference quarter is left out, two masked give none", () => {
  const signal = (valeurs: Entier[]) => corpsDepuisVues(entree({ vues: vuesDe({ sansEquipe: parts(valeurs, "v_task_without_team_share") }) }));
  // 20 and 30: mean 25 ; judged 36 : gap 11 above 10, raised ; judged 35 : gap 10, nothing
  assert.equal(signal([20, 30, 36]).attachmentSignal, "raised");
  assert.equal(signal([20, 30, 35]).attachmentSignal, "not_raised");
  // one masked reference quarter: the signal rests on the other, 20 ; judged 31 : gap 11, raised ; judged 30 : gap 10, nothing
  assert.equal(signal(["m", 20, 31]).attachmentSignal, "raised");
  assert.equal(signal(["m", 20, 30]).attachmentSignal, "not_raised");
  // both reference quarters masked: no signal, the reason is the masked share
  const aucune = signal(["m", "m", 50]);
  assert.equal(aucune.attachmentSignal, "not_raised");
  assert.deepEqual(aucune.attachmentSignalReasons, ["tasks_without_team_share_masked"]);
});

test("signal: a masked judged share raises nothing, carries its reason, stays the masked cell", () => {
  const corps = corpsDepuisVues(entree({ vues: vuesDe({ sansEquipe: parts([10, 14, "m"], "v_task_without_team_share") }) }));
  assert.equal(corps.attachmentSignal, "not_raised");
  assert.deepEqual(corps.attachmentSignalReasons, ["tasks_without_team_share_masked"]);
  assert.deepEqual(corps.tasksWithoutTeamShare, { state: "masked", threshold: 5 });
});

test("a team sheet: unplanned work is not measurable (defects without team), the product share is context only", () => {
  const corps = corpsDepuisVues(entree());
  const nonPlanifie = corps.explanations.find((e) => e.name === "unplanned_work");
  assert.deepEqual(nonPlanifie, { name: "unplanned_work", state: "not_measurable", reason: "defects_without_team" });
  assert.deepEqual(corps.unplannedProductShare, { state: "value", value: 12 });
  assert.ok(corps.method.limits.includes("no_per_team_unplanned_measure"));
});

test("capacity and dependencies: measured is not ruled out without an adopted threshold, masked is not measurable", () => {
  const corps = corpsDepuisVues(
    entree({
      vues: vuesDe({
        fileEnAttente: reponse("v_team_ready_queue", [{ team: EQUIPE, quarter_start: JUGE, ready: c("m") }]),
        bloque: reponse("v_team_blocked_share", []),
      }),
    }),
  );
  const capacite = corps.explanations.find((e) => e.name === "capacity");
  const dependances = corps.explanations.find((e) => e.name === "dependencies");
  assert.deepEqual(capacite, { name: "capacity", state: "not_measurable", reason: "masked", measure: { state: "masked", threshold: 5 } });
  assert.deepEqual(dependances, { name: "dependencies", state: "not_measurable", reason: "no_data" });
  const mesuree = corpsDepuisVues(entree()).explanations.find((e) => e.name === "capacity");
  assert.deepEqual(mesuree, { name: "capacity", state: "not_ruled_out", reason: "no_adopted_threshold", measure: { state: "value", value: 12 } });
});

test("F-H1: reads the pooled year only; the throughput of the quarters changes nothing", () => {
  const annee = { lm: 40, cm: 10, lp: 80, cp: 20 };
  const a = corpsDepuisVues(entree({ chart: "lead_cycle_h1", vues: vuesDe({ leadCycle: leadCycle(STABLE, annee) }) }));
  const b = corpsDepuisVues(
    entree({ chart: "lead_cycle_h1", vues: vuesDe({ leadCycle: leadCycle([{ n: 5 }, { n: "m" }, { n: 1000 }], annee) }) }),
  );
  assert.equal(a.method.hypothesis, "h1_first_half");
  assert.deepEqual(a.h1Reasons, []);
  assert.equal(a.verdict, b.verdict);
  assert.equal(a.attachmentSignalShown, false);
  assert.deepEqual(a.method.coverage, { state: "value", value: 30 });
  const refute = corpsDepuisVues(entree({ chart: "lead_cycle_h1", vues: vuesDe({ leadCycle: leadCycle(STABLE, { lm: 12, cm: 10 }) }) }));
  assert.equal(refute.verdict, "refuted");
});

test("F-H1: both headcounts must reach the size (Q7); a P85 on 10 to 19 items caps with its reason", () => {
  const annee = { lm: 40, cm: 10, lp: 80, cp: 20 };
  const medianeCourte = corpsDepuisVues(entree({ chart: "lead_cycle_h1", vues: vuesDe({ leadCycle: leadCycle(STABLE, { ...annee, ctN: 8 }) }) }));
  assert.equal(medianeCourte.verdict, "insufficient_sample");
  assert.deepEqual(medianeCourte.h1Reasons, ["median_insufficient_sample"]);
  const p85Court = corpsDepuisVues(entree({ chart: "lead_cycle_h1", vues: vuesDe({ leadCycle: leadCycle(STABLE, { ...annee, ctN: 15 }) }) }));
  assert.deepEqual(p85Court.h1Reasons, ["p85_insufficient_sample"]);
  const masquee = corpsDepuisVues(entree({ chart: "lead_cycle_h1", vues: vuesDe({ leadCycle: leadCycle(STABLE, { ...annee, cm: "m", ctN: "m" }) }) }));
  assert.deepEqual(masquee.h1Reasons, ["median_masked"]);
  assert.deepEqual(masquee.method.coverage, { state: "masked", threshold: 5 });
});

test("thresholds: the latest value is in force; a value recorded on or after the first reading is flagged with the former one", () => {
  const historique = [
    ...historiqueDeDepart("2026-10-27"),
    { code: "h5_band", value: 0.3, setOn: "2026-10-30" },
  ];
  const corps = corpsDepuisVues(entree({ historique, premiereLecture: "2026-10-30" }));
  const bande = corps.method.thresholds.find((s) => s.code === "h5_band");
  assert.deepEqual(bande, {
    code: "h5_band",
    value: 0.3,
    fixedOn: "2026-10-30",
    fixedBy: "author_alone",
    modifiedAfterReading: { formerValue: 0.2, formerDate: "2026-10-27" },
  });
  const sans = corpsDepuisVues(entree({ historique, premiereLecture: "2026-10-31" }));
  assert.equal(sans.method.thresholds.find((s) => s.code === "h5_band")?.modifiedAfterReading, undefined);
  assert.equal(corps.method.thresholdsFixedOn, "2026-10-30");
});

test("thresholds: a missing code gives no verdict (SeuilsNonFixes naming the codes), and the creation check refuses an unknown chart", () => {
  const sans = historiqueDeDepart().filter((h) => h.code !== "h5_floor" && h.code !== "sample_p85_min_items");
  assert.throws(
    () => corpsDepuisVues(entree({ historique: sans })),
    (e: unknown) => e instanceof SeuilsNonFixes && e.codes.join() === "h5_floor,sample_p85_min_items",
  );
  assert.throws(() => lireSeuils([], ["h5_band"], null), SeuilsNonFixes);
  assert.throws(() => verifierCreation("lead-cycle", historiqueDeDepart(), SCOPE), GraphiqueInconnu);
  assert.throws(() => verifierCreation("lead_cycle_h1", [], SCOPE), SeuilsNonFixes);
  assert.doesNotThrow(() => verifierCreation("lead_cycle_h5", historiqueDeDepart(), SCOPE));
  assert.throws(() => corpsDepuisVues(entree({ chart: "autre" })), GraphiqueInconnu);
});

test("masked cells: every masked cell of the body is the structured cell of the view, never null, zero or an estimate", () => {
  const corps = corpsDepuisVues(
    entree({
      vues: vuesDe({ sansEquipe: parts(["m", 14, "m"], "v_task_without_team_share") }, [{ cp: "m", ctN: "m", cm: "m" }, {}, { n: "m" }]),
    }),
  );
  for (const m of corps.method.maskedCells) {
    assert.deepEqual(m.cell, { state: "masked", threshold: 5 });
  }
  assert.ok(corps.method.maskedCells.length >= 4);
  const texte = JSON.stringify(corps);
  assert.ok(!texte.includes('"value":null'));
  assert.ok(!texte.includes('"value":0,'));
});

test("parity: each point of the chart equals the point of the dashboard function on the same answer", () => {
  const vues = vuesDe({}, [{ cm: "m", ctN: "m" }, { ctN: 7 }, {}]);
  const corps = corpsDepuisVues(entree({ vues }));
  const tableau = tableauLeadCycle(vues.leadCycle, { medianMinItems: 10, p85MinItems: 20 }, DATE, identifiant);
  const serie = tableau.teams.find((s) => s.team === EQUIPE);
  assert.ok(serie !== undefined);
  assert.equal(corps.chart?.quarters.length, 3);
  for (const point of corps.chart?.quarters ?? []) {
    assert.deepEqual(point, serie.points.find((p) => p.quarter === point.quarter));
  }
  assert.deepEqual(corps.chart?.pooledYear, serie.points.find((p) => p.quarter === "pooled_year"));
});

test("dashboard: a median is a value, a masked cell or an insufficient sample; each series carries its team identifier", () => {
  const vue = leadCycle([{ cm: "m", ctN: "m" }, { ctN: 7 }, {}, null]);
  const tableau = tableauLeadCycle(vue, { medianMinItems: 10, p85MinItems: 20 }, DATE, (n) => `id-${n}`);
  assert.equal(tableau.teams[0].teamId, "id-team-a");
  const [q1, q2, q3, , annee] = [...tableau.teams[0].points, undefined, undefined];
  assert.deepEqual(q1?.cycle, { state: "masked", threshold: 5 });
  assert.deepEqual(q2?.cycle, { state: "insufficient_sample" });
  assert.deepEqual(q3?.cycle, { state: "value", value: 10 });
  assert.equal(annee, undefined);
  assert.equal(tableau.teams[0].points.at(-1)?.quarter, "pooled_year");
  assert.deepEqual(tableau.product, []);
});

test("a plain number where a cell is expected is refused (the masking was bypassed)", () => {
  const vues = vuesDe();
  vues.leadCycle.rows[0].cycle_median_days = 10;
  assert.throws(() => corpsDepuisVues(entree({ vues })), TypeError);
});

test("the starting values are not in the contract: the body needs the history", () => {
  assert.throws(() => corpsDepuisVues(entree({ historique: [] })), SeuilsNonFixes);
});

test("A1: a real team sheet (scope team.<real identifier>) finds its series, and the scope is the inverse of scopeFiche", () => {
  assert.match(SCOPE, /^team\.[0-9a-f]{16}$/);
  assert.deepEqual(porteeDeScope(SCOPE), { kind: "team", team: identifiantEquipe(EQUIPE) });
  assert.deepEqual(porteeDeScope("product"), { kind: "product" });
  const corps = corpsDepuisVues(entree());
  assert.notEqual(corps.verdict, "insufficient_sample");
  assert.equal(corps.chart?.quarters.length, 3);
  assert.deepEqual(corps.method.scope, { level: "team", id: SCOPE });
  assert.deepEqual(corps.method.coverage, { state: "value", value: 30 });
});

test("A1: a team name, an unknown text and the product level are refused as scopes", () => {
  for (const scope of [EQUIPE, "team-a", "team.", "team.UPPER", `team.${"x".repeat(60)}`, "product", "product_level"]) {
    assert.throws(() => corpsDepuisVues(entree({ scope })), PorteeNonServie, scope);
    assert.throws(() => verifierCreation("lead_cycle_h5", historiqueDeDepart(), scope), PorteeNonServie, scope);
  }
  assert.equal(porteeDeScope(EQUIPE), null);
  assert.equal(porteeDeScope("team.UPPER"), null);
});

test("C1: a judged quarter with no row gives no verdict; a hole in the window gives no reference, not a rise counted across it", () => {
  const sansJuge = corpsDepuisVues(entree({ vues: vuesDe({}, [{}, {}, null]) }));
  assert.equal(sansJuge.verdict, "insufficient_sample");
  const trou = corpsDepuisVues(entree({ vues: vuesDe({}, [{ cm: 10 }, null, { cm: 12 }]) }));
  assert.equal(trou.verdict, "insufficient_sample", "no refutation by a rise counted over a hole");
});

test("C2: the sheet of hypothesis 5 states that its throughput is compared with the team's own past only", () => {
  assert.ok(corpsDepuisVues(entree()).method.limits.includes("throughput_own_past_only"));
  assert.ok(!corpsDepuisVues(entree({ chart: "lead_cycle_h1" })).method.limits.includes("throughput_own_past_only"));
});

test("D6: a new sheet carries the window limit of three closed quarters and never the former one (kept as a known code of frozen sheets only)", () => {
  for (const chart of ["lead_cycle_h5", "lead_cycle_h1"] as const) {
    const limites = corpsDepuisVues(entree({ chart })).method.limits;
    assert.ok(limites.includes("views_last_three_closed_quarters"), chart);
    assert.ok(!limites.includes("views_last_four_quarters"), chart);
  }
  assert.ok((CODES_LIMITES as readonly string[]).includes("views_last_four_quarters"), "the former code stays in the closed list, for frozen sheets");
});

test("measure codes: one builder, one reader", () => {
  assert.equal(codeMesure("throughput", "2026-07-01"), "throughput@2026-07-01");
  assert.deepEqual(lireCodeMesure("cycle_p85_days@pooled_year"), { column: "cycle_p85_days", when: "pooled_year" });
  assert.equal(lireCodeMesure("throughput@yesterday"), null);
  const corps = corpsDepuisVues(entree({ vues: vuesDe({}, [{}, {}, { n: "m" }]) }));
  for (const m of corps.method.maskedCells) assert.notEqual(lireCodeMesure(m.measure), null);
});

// ---- Reproductions de l'audit #629 (chasse Kraken), attendues rouges au commit a98a3ffb ------------------------------------------------

test("L3-04 : un couple de seuils bas >= haut ne se termine pas par un RangeError brut (500 sur toutes les fiches H1)", () => {
  // audit-kraken/lots/L3.md, constat 4
  const historique = historiqueDeDepart().map((h) => (h.code === "h1_lower" ? { ...h, value: 5 } : h.code === "h1_upper" ? { ...h, value: 2 } : h));
  const annee = { lm: 40, cm: 10, lp: 80, cp: 20 };
  let levee: unknown = null;
  try {
    corpsDepuisVues(entree({ chart: "lead_cycle_h1", historique, vues: vuesDe({ leadCycle: leadCycle(STABLE, annee) }) }));
  } catch (erreur) {
    levee = erreur;
  }
  assert.ok(!(levee instanceof RangeError), "le seuil bas >= haut doit être refusé à l'écriture, pas lever un RangeError à la lecture");
});

test("H-01 : les rapports poolés de H1 lisent les statistiques sans les anciens, comme le verdict", () => {
  // audit-kraken/lots/L5.md, H-01
  const vues = vuesDe({ leadCycle: leadCycle(STABLE, { lm: 40, cm: 10, lp: 80, cp: 20 }) });
  const annee = vues.leadCycle.rows.find((r) => r.period === "pooled_year");
  assert.ok(annee !== undefined);
  // Sans les anciens, les médianes et les P85 sont deux fois plus bas : rapport 2, et non 4.
  annee.lead_median_days_excl_old = c(20);
  annee.cycle_median_days_excl_old = c(10);
  annee.lead_p85_days_excl_old = c(40);
  annee.cycle_p85_days_excl_old = c(20);
  const corps = corpsDepuisVues(entree({ chart: "lead_cycle_h1", vues }));
  assert.deepEqual(corps.ratios?.pooledYear?.median, { state: "value", value: 2 });
  assert.deepEqual(corps.ratios?.pooledYear?.p85, { state: "value", value: 2 });
});

test("H-01 : une cellule déclarée masquée par la fiche n'est pas montrée par son graphique", () => {
  // audit-kraken/lots/L5.md, H-01
  const vues = vuesDe({ leadCycle: leadCycle(STABLE, { lm: 40, cm: 10, lp: 80, cp: 20 }) });
  const annee = vues.leadCycle.rows.find((r) => r.period === "pooled_year");
  assert.ok(annee !== undefined);
  annee.lead_median_days_excl_old = M; // masquée sans les anciens, alors que lead_median_days avec les anciens est montrée
  const corps = corpsDepuisVues(entree({ chart: "lead_cycle_h1", vues }));
  const declareeMasquee = corps.method.maskedCells.some((m) => m.measure === "lead_median_days@pooled_year");
  assert.ok(declareeMasquee, "précondition : la fiche déclare la cellule masquée");
  assert.notEqual(corps.chart?.pooledYear?.lead.state, "value", "le graphique ne montre pas une cellule que la fiche déclare masquée");
});

test("L3-08 : l'ordre des équipes de la réponse ne suit pas l'ordre alphabétique des noms", () => {
  // audit-kraken/lots/L3.md, constat 8 : les noms sont masqués par défaut, l'ordre ne doit pas les révéler
  const vue = reponse("v_team_lead_time_throughput", [ligneLead(DEBUTS[0], {}, "alpha-team"), ligneLead(DEBUTS[0], {}, "beta-team")]);
  const idDe = (nom: string): string => (nom === "alpha-team" ? "id-z" : "id-a");
  const tableau = tableauLeadCycle(vue, { medianMinItems: 10, p85MinItems: 20 }, DATE, idDe);
  // Q238 (R-20261107-30): the order is decided where the answer goes out, `servirTableau`, not in the computation.
  const servie = servirTableau(tableau, { jeu: "synthetic", comptesAutorises: true, afficherNoms: false });
  const ids = servie.teams.map((s) => s.teamId);
  assert.deepEqual(ids, [...ids].sort(), "ordre des identifiants, pas des noms");
  assert.deepEqual(ids, ["id-a", "id-z"]);
  // Names on: the order of the names.
  const avecNoms = servirTableau(tableau, { jeu: "synthetic", comptesAutorises: true, afficherNoms: true });
  assert.deepEqual(avecNoms.teams.map((s) => s.teamId), ["id-z", "id-a"]);
});
