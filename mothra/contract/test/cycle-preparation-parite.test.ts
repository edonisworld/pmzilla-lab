// Tasks 40.1 and 40.2 (mothra-slices D35, R-169): parity cases of the page "preparation of a cycle", played as data, in a file of their own.
// The masking of the three views of task 38.1 is NOT played here: the function of task 15.3 refuses a view it does not port (refusal by
// default), and the views, with their Python side in `masquer_vue`, come with task 38.1. Until then the cases start from cells, the output of
// that function (PRECONDITION of every total), and one case chains the real function of 15.3 on a ported view into the total.
// Removal condition: the parity cases of the three views join contrats/ (shared with tests/flow_views) when task 38.1 ports them.
import assert from "node:assert/strict";
import { test } from "node:test";
import Value from "typebox/value";

import { cellule } from "../src/cellule.ts";
import type { Cellule } from "../src/cellule.ts";
import { SchemaReponseCyclePreparation } from "../src/cycle-preparation/schemas.ts";
import { choisirCycle, choisirEtats, totalDesCellules, verifierPorteeDomaine } from "../src/cycle-preparation/fonctions.ts";
import type { CycleCle, EntreeEtats } from "../src/cycle-preparation/fonctions.ts";
import { masquerVue } from "../src/masquage.ts";
import type { LigneBrute } from "../src/masquage.ts";

const c = (n: number | null): Cellule => cellule(n, 5);

// ---- totals ------------------------------------------------------------------------------------------------------------------------
const CAS_TOTAL: Array<{ nom: string; entree: Array<number | null>; attendu: unknown }> = [
  { nom: "all visible", entree: [5, 6, 7], attendu: { state: "value", value: 18 } },
  { nom: "one masked in the middle", entree: [5, null, 7], attendu: { state: "masked", threshold: 5 } },
  { nom: "the first masked", entree: [null, 6, 7], attendu: { state: "masked", threshold: 5 } },
  { nom: "all masked", entree: [null, null, null], attendu: { state: "masked", threshold: 5 } },
  { nom: "a single visible cell", entree: [9], attendu: { state: "value", value: 9 } },
  { nom: "a single masked cell", entree: [null], attendu: { state: "masked", threshold: 5 } },
  { nom: "a count under the floor is a masked cell", entree: [4, 6], attendu: { state: "masked", threshold: 5 } },
];
for (const cas of CAS_TOTAL) {
  test(`total of the columns: ${cas.nom}`, () => {
    assert.deepEqual(totalDesCellules(cas.entree.map(c)), cas.attendu);
  });
}

test("chain: the rows masked by the function of task 15.3 (a ported view) give the total of this module", () => {
  const vue = {
    name: "v_team_status",
    schema: "flow",
    roleKind: "flow",
    countColumns: ["tickets"],
    plainColumns: ["team", "type", "status_category", "status"],
  };
  const ligne = (tickets: number): LigneBrute => ({ team: "A", type: "Story", status_category: "Done", status: "x", tickets });
  const visibles = masquerVue(vue, [ligne(5), ligne(8)], 5).map((l) => l.tickets as Cellule);
  assert.deepEqual(totalDesCellules(visibles), { state: "value", value: 13 });
  const unMasque = masquerVue(vue, [ligne(5), ligne(3), ligne(8)], 5).map((l) => l.tickets as Cellule);
  assert.deepEqual(totalDesCellules(unMasque), { state: "masked", threshold: 5 });
});

test("a view of the page that task 38.1 has not yet ported is refused by the function of 15.3, never served with the primary rule alone", () => {
  const vue = { name: "v_cycle_unported", schema: "flow", roleKind: "flow", countColumns: ["epics"], plainColumns: ["cycle"] };
  assert.throws(() => masquerVue(vue, [{ cycle: "c-01", epics: 7 }], 5), /non port/);
});

// ---- empty-state code --------------------------------------------------------------------------------------------------------------
const BASE: EntreeEtats = {
  domainTeamCount: 3,
  offeredCycles: 2,
  summaryRowPresent: true,
  labelHistoryCollected: true,
  mappingValidated: true,
  realCountsHidden: false,
  readySource: "label",
};
const CAS_ETATS: Array<{ nom: string; entree: Partial<EntreeEtats>; vide: string | null; avis: string[]; source: string }> = [
  { nom: "regular, Ready label", entree: {}, vide: null, avis: [], source: "ready_source_label" },
  { nom: "regular, Ready column", entree: { readySource: "column" }, vide: null, avis: [], source: "ready_source_column" },
  { nom: "domain of two teams", entree: { domainTeamCount: 2 }, vide: "domain_too_small", avis: [], source: "ready_source_label" },
  { nom: "domain of two teams, nothing else configured", entree: { domainTeamCount: 2, offeredCycles: 0, summaryRowPresent: false, mappingValidated: false }, vide: "domain_too_small", avis: [], source: "ready_source_label" },
  { nom: "real data, counts not shown", entree: { realCountsHidden: true }, vide: "real_counts_not_shown", avis: [], source: "ready_source_label" },
  { nom: "real data, counts not shown, domain of two teams", entree: { realCountsHidden: true, domainTeamCount: 2 }, vide: "domain_too_small", avis: [], source: "ready_source_label" },
  { nom: "real data, counts not shown, nothing configured", entree: { realCountsHidden: true, offeredCycles: 0, summaryRowPresent: false, labelHistoryCollected: false }, vide: "real_counts_not_shown", avis: [], source: "ready_source_label" },
  { nom: "domain of three teams is enough", entree: { domainTeamCount: 3 }, vide: null, avis: [], source: "ready_source_label" },
  { nom: "no cycle offered", entree: { offeredCycles: 0, summaryRowPresent: false }, vide: "no_cycle_configured", avis: [], source: "ready_source_label" },
  { nom: "no epic, history collected", entree: { summaryRowPresent: false }, vide: "no_epic_for_cycle", avis: [], source: "ready_source_label" },
  { nom: "no epic, no history", entree: { summaryRowPresent: false, labelHistoryCollected: false }, vide: "no_label_history", avis: [], source: "ready_source_label" },
  { nom: "epics but no history", entree: { labelHistoryCollected: false }, vide: "no_label_history", avis: [], source: "ready_source_label" },
  { nom: "mapping not validated", entree: { mappingValidated: false }, vide: null, avis: ["mapping_not_validated"], source: "ready_source_label" },
  { nom: "mapping not validated, Ready column in the referential: the label wins", entree: { mappingValidated: false, readySource: "column" }, vide: null, avis: ["mapping_not_validated"], source: "ready_source_label" },
  { nom: "mapping not validated and no history", entree: { mappingValidated: false, labelHistoryCollected: false }, vide: "no_label_history", avis: [], source: "ready_source_label" },
];
for (const cas of CAS_ETATS) {
  test(`state code: ${cas.nom}`, () => {
    assert.deepEqual(choisirEtats({ ...BASE, ...cas.entree }), { emptyState: cas.vide, notices: cas.avis, readySource: cas.source });
  });
}

// ---- cycle selection ---------------------------------------------------------------------------------------------------------------
const CYCLES: CycleCle[] = [
  { key: "k-3", start: "2027-01-01", end: "2027-02-28", state: "upcoming" },
  { key: "k-1", start: "2026-09-01", end: "2026-10-31", state: "ended" },
  { key: "k-2", start: "2026-11-01", end: "2026-12-31", state: "running" },
  { key: "k-4", start: "2027-01-01", end: "2027-02-28", state: "upcoming" },
];
const CAS_CYCLE: Array<{ nom: string; demande: string | undefined; cle: string | null; offerts: string[]; code?: string }> = [
  { nom: "no request: the first in neutral order", demande: undefined, cle: "k-2", offerts: ["k-2", "k-3", "k-4"] },
  { nom: "a running cycle", demande: "k-2", cle: "k-2", offerts: ["k-2", "k-3", "k-4"] },
  { nom: "an upcoming cycle, tie on the start broken by the key", demande: "k-4", cle: "k-4", offerts: ["k-2", "k-3", "k-4"] },
  { nom: "an ended cycle", demande: "k-1", cle: null, offerts: [], code: "CYCLE_UNKNOWN" },
  { nom: "an unknown cycle", demande: "zzz", cle: null, offerts: [], code: "CYCLE_UNKNOWN" },
];
for (const cas of CAS_CYCLE) {
  test(`cycle selection: ${cas.nom}`, () => {
    const r = choisirCycle(CYCLES, cas.demande);
    if (cas.code !== undefined) {
      assert.deepEqual(r, { ok: false, status: 422, code: cas.code });
      return;
    }
    assert.ok(r.ok);
    assert.equal(r.cycle?.key ?? null, cas.cle);
    assert.deepEqual(r.cycles.map((x) => x.key), cas.offerts);
  });
}

// ---- scope -------------------------------------------------------------------------------------------------------------------------
const CAS_PORTEE: Array<{ nom: string; entree: unknown; attendu: unknown }> = [
  { nom: "empty query", entree: {}, attendu: { ok: true, cycle: undefined } },
  { nom: "a cycle only", entree: { cycle: "k-2" }, attendu: { ok: true, cycle: "k-2" } },
  { nom: "a team identifier", entree: { team: "t-07" }, attendu: { ok: false, status: 422, code: "SCOPE_INVALID" } },
  { nom: "the product word", entree: { team: "product" }, attendu: { ok: false, status: 422, code: "SCOPE_INVALID" } },
  { nom: "a list of teams", entree: { team: ["t-01", "t-02"] }, attendu: { ok: false, status: 422, code: "SCOPE_INVALID" } },
  { nom: "an empty team", entree: { team: "" }, attendu: { ok: false, status: 422, code: "SCOPE_INVALID" } },
  { nom: "a team with a valid cycle", entree: { team: "t-07", cycle: "k-2" }, attendu: { ok: false, status: 422, code: "SCOPE_INVALID" } },
];
for (const cas of CAS_PORTEE) {
  test(`scope: ${cas.nom}`, () => {
    assert.deepEqual(verifierPorteeDomaine(cas.entree), cas.attendu);
  });
}

// ---- answers as data (schema) --------------------------------------------------------------------------------------------------------
const ENTETE = { threshold: 5, dataDate: "2026-11-19", scope: "domain", dataset: "synthetic" };
const VIDE = { ...ENTETE, cycles: [], cycle: null, emptyState: "no_cycle_configured", notices: [], readySource: null, summary: null, columns: [], columnsTotal: null };
const CAS_REPONSE: Array<{ nom: string; reponse: unknown; valide: boolean }> = [
  { nom: "empty state: no cycle configured", reponse: VIDE, valide: true },
  { nom: "empty state: domain too small", reponse: { ...VIDE, emptyState: "domain_too_small" }, valide: true },
  { nom: "empty state with a leftover summary", reponse: { ...VIDE, summary: { mentions: ["indirect_indicator"] } }, valide: false },
  { nom: "empty state: real counts not shown", reponse: { ...VIDE, emptyState: "real_counts_not_shown" }, valide: true },
  { nom: "a cycle key outside the pattern", reponse: { ...VIDE, cycle: "C_01" }, valide: false },
  { nom: "empty state with a notice", reponse: { ...VIDE, notices: ["mapping_not_validated"] }, valide: false },
  { nom: "no dataset code", reponse: { ...VIDE, dataset: undefined }, valide: false },
  { nom: "a scope other than the domain", reponse: { ...VIDE, scope: "team.t-07" }, valide: false },
  { nom: "a per-team collection", reponse: { ...VIDE, teams: [{ id: "t-07", planned: c(9) }] }, valide: false },
  { nom: "an epic key or title", reponse: { ...VIDE, epics: [{ key: "E-1", title: "x" }] }, valide: false },
  { nom: "the threshold under the floor", reponse: { ...VIDE, threshold: 4 }, valide: false },
];
for (const cas of CAS_REPONSE) {
  test(`answer schema: ${cas.nom}`, () => {
    assert.equal(Value.Check(SchemaReponseCyclePreparation, cas.reponse), cas.valide);
  });
}
