// Task 40.1 (mothra-slices D35, R-169): the schemas of the page "preparation of a cycle" in mothra/contract/src/cycle-preparation/.
// The parity cases (valid and refused answers as data) are in cycle-preparation-parite.test.ts.
import assert from "node:assert/strict";
import { test } from "node:test";
import Value from "typebox/value";

import { cellule } from "../src/cellule.ts";
import {
  CODES_AVIS,
  CODE_COMPTES_REELS_MASQUES,
  MOTIF_CLE_CYCLE,
  CODES_ETAT_PAGE,
  CODES_ETAT_VIDE,
  CODES_REFUS_PAGE,
  CODES_SOURCE_READY,
  CODE_DOMAINE_TROP_PETIT,
  SchemaDemandeCyclePreparation,
  SchemaReponseCyclePreparation,
  SchemaRefusCyclePreparation,
} from "../src/cycle-preparation/schemas.ts";

const c = (n: number | null) => cellule(n, 5);

function reponse(): Record<string, unknown> {
  return {
    threshold: 5,
    dataDate: "2026-11-19",
    dataset: "synthetic",
    scope: "domain",
    cycles: [{ key: "c-01", start: "2026-11-01", end: "2026-12-31", state: "running" }],
    cycle: "c-01",
    emptyState: null,
    notices: [],
    readySource: "ready_source_label",
    summary: {
      mentions: ["indirect_indicator"],
      planned: c(20),
      ready: c(8),
      confirmedIn: c(10),
      declined: c(6),
      withoutConfirmation: c(4),
      replannedBeforeStart: c(null),
      epicReview: { mentions: ["partial_evidence_signals"], inEpicReview: c(6), candidates: c(null) },
    },
    columns: [
      { column: "col_a", mapped: true, count: c(12) },
      { column: "status_not_mapped", mapped: false, count: c(null) },
    ],
    columnsTotal: c(null),
  };
}

test("the state codes of D35 are the six of the design, plus the proposed one for a domain of fewer than three teams", () => {
  assert.deepEqual(
    [...CODES_ETAT_PAGE].sort(),
    ["mapping_not_validated", "no_cycle_configured", "no_epic_for_cycle", "no_label_history", "ready_source_column", "ready_source_label"].sort(),
  );
  assert.deepEqual([...CODES_SOURCE_READY], ["ready_source_label", "ready_source_column"]);
  assert.ok(CODES_ETAT_VIDE.includes(CODE_DOMAINE_TROP_PETIT));
  assert.equal(CODE_DOMAINE_TROP_PETIT, "domain_too_small");
  assert.ok(!CODES_ETAT_PAGE.includes(CODE_DOMAINE_TROP_PETIT as never), "the proposed code is not one of the six of D35");
});

test("the refusals are CYCLE_UNKNOWN and SCOPE_INVALID, both 422 codes only", () => {
  assert.deepEqual([...CODES_REFUS_PAGE].sort(), ["CYCLE_UNKNOWN", "SCOPE_INVALID"]);
  assert.ok(Value.Check(SchemaRefusCyclePreparation, { error: "CYCLE_UNKNOWN" }));
  assert.ok(Value.Check(SchemaRefusCyclePreparation, { error: "SCOPE_INVALID" }));
  assert.ok(!Value.Check(SchemaRefusCyclePreparation, { error: "RANGE_INVALID" }));
  assert.ok(!Value.Check(SchemaRefusCyclePreparation, { error: "CYCLE_UNKNOWN", message: "text" }), "codes only, no text");
});

test("a complete answer validates", () => {
  assert.ok(Value.Check(SchemaReponseCyclePreparation, reponse()));
});

test("the answer holds the domain scope only: any other scope is refused by the schema", () => {
  for (const portee of ["product", "team.t-07", "t-07", ""]) {
    assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...reponse(), scope: portee }), portee);
  }
});

test("no collection indexed by team: no property or item key named team, and no record with free keys", () => {
  const entree = JSON.stringify(SchemaReponseCyclePreparation);
  assert.ok(!/team/i.test(entree.replace(/"description":"[^"]*"/g, "")), "no team property in the schema");
  assert.ok(!entree.includes("patternProperties"), "no map keyed by a free key");
  assert.ok(!entree.includes("additionalProperties\":{"), "no record of free keys");
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...reponse(), teams: [] }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...reponse(), team: "t-07" }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...reponse(), byTeam: { "t-07": c(7) } }));
});

test("an undeclared field is refused at every level", () => {
  const a = reponse();
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, extra: 1 }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, cycles: [{ key: "c-01", start: "2026-11-01", end: "2026-12-31", state: "running", title: "x" }] }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, columns: [{ column: "col_a", mapped: true, count: c(12), epics: ["E-1"] }] }));
  const resume = a.summary as Record<string, unknown>;
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, epics: [] } }));
});

test("the cycle selector offers upcoming and running cycles only, never an ended one", () => {
  const a = reponse();
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, cycles: [{ key: "c-00", start: "2026-01-01", end: "2026-02-28", state: "ended" }] }));
  assert.ok(Value.Check(SchemaReponseCyclePreparation, { ...a, cycles: [{ key: "c-02", start: "2027-01-01", end: "2027-02-28", state: "upcoming" }] }));
});

test("the summary carries indirect_indicator and the Epic Review counts partial_evidence_signals, as fixed tuples", () => {
  const a = reponse();
  const resume = a.summary as Record<string, unknown>;
  const revue = resume.epicReview as Record<string, unknown>;
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, mentions: [] } }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, mentions: ["partial_evidence_signals"] } }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, epicReview: { ...revue, mentions: ["indirect_indicator"] } } }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, epicReview: { ...revue, mentions: [] } } }));
});

test("every count is a structured cell: a bare number or a masked cell with a value is refused", () => {
  const a = reponse();
  const resume = a.summary as Record<string, unknown>;
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, planned: 20 } }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, planned: { state: "masked", threshold: 5, value: 3 } } }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, planned: { state: "value", value: 3 } } }), "under the floor");
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, columnsTotal: 12 }));
});

test("an explained empty state carries no summary, no column and no total", () => {
  const vide = {
    ...reponse(),
    emptyState: "no_epic_for_cycle",
    summary: null,
    columns: [],
    columnsTotal: null,
    readySource: null,
  };
  assert.ok(Value.Check(SchemaReponseCyclePreparation, vide));
  assert.ok(Value.Check(SchemaReponseCyclePreparation, { ...vide, emptyState: CODE_DOMAINE_TROP_PETIT }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...vide, emptyState: "mapping_not_validated" }), "the mapping state is a notice, not an empty state");
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...vide, emptyState: "something_else" }));
});

test("the only notice is the mapping one (no_label_history is an empty state), and the Ready source has one of its two codes", () => {
  const a = reponse();
  assert.ok(Value.Check(SchemaReponseCyclePreparation, { ...a, notices: ["mapping_not_validated"], readySource: "ready_source_column" }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, notices: ["no_label_history"] }));
  assert.deepEqual([...CODES_AVIS], ["mapping_not_validated"]);
  assert.ok(CODES_ETAT_VIDE.includes("real_counts_not_shown"));
  assert.equal(CODE_COMPTES_REELS_MASQUES, "real_counts_not_shown");
  const vide = { ...a, emptyState: "real_counts_not_shown", summary: null, columns: [], columnsTotal: null, readySource: null };
  assert.ok(Value.Check(SchemaReponseCyclePreparation, vide));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, notices: ["ready_source_label"] }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, readySource: "label" }));
});

test("the request: a cycle key and nothing else, any other field refused; the team is read as unknown so that it reaches the scope check", () => {
  assert.ok(Value.Check(SchemaDemandeCyclePreparation, {}));
  assert.ok(Value.Check(SchemaDemandeCyclePreparation, { cycle: "c-01" }));
  assert.ok(Value.Check(SchemaDemandeCyclePreparation, { team: ["a", "b"] }), "a repeated team answers 422 SCOPE_INVALID, not a schema error");
  assert.ok(!Value.Check(SchemaDemandeCyclePreparation, { cycle: "c-01", sort: "name" }));
  assert.ok(!Value.Check(SchemaDemandeCyclePreparation, { from: "2026-Q1" }));
  assert.ok(!Value.Check(SchemaDemandeCyclePreparation, { cycle: 7 }));
});

test("the Epic Review candidates may be null (mapping not validated), in no other field", () => {
  const a = reponse();
  const resume = a.summary as Record<string, unknown>;
  const revue = resume.epicReview as Record<string, unknown>;
  assert.ok(Value.Check(SchemaReponseCyclePreparation, { ...a, notices: ["mapping_not_validated"], summary: { ...resume, epicReview: { ...revue, candidates: null } }, columns: [], columnsTotal: null }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, summary: { ...resume, planned: null } }));
});

test("an empty state carries no notice", () => {
  const vide = { ...reponse(), emptyState: "no_epic_for_cycle", summary: null, columns: [], columnsTotal: null, readySource: null };
  assert.ok(Value.Check(SchemaReponseCyclePreparation, { ...vide, notices: [] }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...vide, notices: ["no_label_history"] }));
});

test("the cycle key is strict: [a-z0-9-]{1,32}, in the request, the selector and the answer", () => {
  assert.equal(MOTIF_CLE_CYCLE.source, "^[a-z0-9-]{1,32}$");
  const a = reponse();
  for (const bonne of ["c-01", "2026-q4", "a".repeat(32)]) {
    assert.ok(Value.Check(SchemaDemandeCyclePreparation, { cycle: bonne }), bonne);
  }
  for (const mauvaise of ["C-01", "c_01", "c 01", "", "a".repeat(33), "é"]) {
    assert.ok(!Value.Check(SchemaDemandeCyclePreparation, { cycle: mauvaise }), mauvaise);
    assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, cycle: mauvaise }), mauvaise);
    assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...a, cycles: [{ key: mauvaise, start: "2026-11-01", end: "2026-12-31", state: "running" }] }), mauvaise);
  }
});

test("the dataset code is required and limited to synthetic or real", () => {
  const { dataset: _omis, ...sansDataset } = reponse();
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, sansDataset));
  assert.ok(Value.Check(SchemaReponseCyclePreparation, { ...reponse(), dataset: "synthetic" }));
  assert.ok(Value.Check(SchemaReponseCyclePreparation, { ...reponse(), dataset: "real" }));
  assert.ok(!Value.Check(SchemaReponseCyclePreparation, { ...reponse(), dataset: "other" }));
});
