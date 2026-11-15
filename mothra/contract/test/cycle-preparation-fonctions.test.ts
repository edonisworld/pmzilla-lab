// Task 40.2 (mothra-slices D35, R-169): the pure functions of the page "preparation of a cycle". The cases as data (parity) are in
// cycle-preparation-parite.test.ts. No rule of the views ("Ready", "candidate to Epic Review") is recomputed here: a static test below
// checks that the module neither names nor computes them.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { cellule } from "../src/cellule.ts";
import type { Cellule } from "../src/cellule.ts";
import {
  cadrerSelonMapping,
  choisirCycle,
  choisirEtats,
  totalDesCellules,
  verifierPorteeDomaine,
} from "../src/cycle-preparation/fonctions.ts";
import type { CycleCle, EntreeEtats } from "../src/cycle-preparation/fonctions.ts";
import { masquerVue } from "../src/masquage.ts";

const c = (n: number | null): Cellule => cellule(n, 5);
const CYCLES: CycleCle[] = [
  { key: "c-00", start: "2026-01-01", end: "2026-02-28", state: "ended" },
  { key: "c-02", start: "2027-01-01", end: "2027-02-28", state: "upcoming" },
  { key: "c-01", start: "2026-11-01", end: "2026-12-31", state: "running" },
];

// ---- cycle selection ---------------------------------------------------------------------------------------------------------------
test("the selection offers the upcoming and running cycles only, in the neutral order (start, then key)", () => {
  const r = choisirCycle(CYCLES, undefined);
  assert.ok(r.ok);
  assert.deepEqual(r.cycles.map((x) => x.key), ["c-01", "c-02"]);
  assert.equal(r.cycle?.key, "c-01");
});

test("a requested cycle among the offered ones is selected", () => {
  const r = choisirCycle(CYCLES, "c-02");
  assert.ok(r.ok);
  assert.equal(r.cycle?.key, "c-02");
});

test("an ended or unknown cycle is refused with 422 CYCLE_UNKNOWN", () => {
  for (const cle of ["c-00", "c-99", "", "C-01"]) {
    assert.deepEqual(choisirCycle(CYCLES, cle), { ok: false, status: 422, code: "CYCLE_UNKNOWN" }, cle);
  }
});

test("no cycle to offer and no cycle requested: ok with no cycle (the empty-state code is chosen elsewhere); a cycle requested is unknown", () => {
  const seulFini: CycleCle[] = [CYCLES[0]];
  const r = choisirCycle(seulFini, undefined);
  assert.ok(r.ok);
  assert.equal(r.cycle, null);
  assert.deepEqual(r.cycles, []);
  assert.deepEqual(choisirCycle([], "c-01"), { ok: false, status: 422, code: "CYCLE_UNKNOWN" });
});

test("a duplicated key or an unknown state is a caller error", () => {
  assert.throws(() => choisirCycle([CYCLES[1], { ...CYCLES[2], key: "c-02" }], undefined), TypeError);
  assert.throws(() => choisirCycle([{ ...CYCLES[1], state: "paused" as never }], undefined), TypeError);
});

test("the selection leaves its input untouched", () => {
  const copie = JSON.stringify(CYCLES);
  choisirCycle(CYCLES, "c-01");
  assert.equal(JSON.stringify(CYCLES), copie);
});

// ---- domain scope ------------------------------------------------------------------------------------------------------------------
test("the domain scope: no team, whatever its form, else 422 SCOPE_INVALID", () => {
  assert.deepEqual(verifierPorteeDomaine({}), { ok: true, cycle: undefined });
  assert.deepEqual(verifierPorteeDomaine({ cycle: "c-01" }), { ok: true, cycle: "c-01" });
  const refus = { ok: false, status: 422, code: "SCOPE_INVALID" };
  for (const equipe of ["t-07", "product", "team.t-07", "", ["a", "b"], 7, null, {}]) {
    assert.deepEqual(verifierPorteeDomaine({ team: equipe }), refus, JSON.stringify(equipe));
    assert.deepEqual(verifierPorteeDomaine({ cycle: "c-01", team: equipe }), refus, JSON.stringify(equipe));
  }
  for (const mauvais of [null, "x", 3, ["a"]]) {
    assert.deepEqual(verifierPorteeDomaine(mauvais), refus);
  }
});

test("the scope is checked before the cycle: a team with a cycle is a scope refusal, never an accepted team scope", () => {
  assert.deepEqual(verifierPorteeDomaine({ team: "t-07", cycle: 7 }), { ok: false, status: 422, code: "SCOPE_INVALID" });
});

test("a cycle that is not a text is refused with CYCLE_UNKNOWN", () => {
  assert.deepEqual(verifierPorteeDomaine({ cycle: 7 }), { ok: false, status: 422, code: "CYCLE_UNKNOWN" });
});

// ---- total only without a masked cell ----------------------------------------------------------------------------------------------
test("a total is shown only when no cell it sums is masked", () => {
  assert.deepEqual(totalDesCellules([c(5), c(7), c(9)]), { state: "value", value: 21 });
  assert.deepEqual(totalDesCellules([c(5), c(null), c(9)]), { state: "masked", threshold: 5 });
  assert.deepEqual(totalDesCellules([c(null), c(null)]), { state: "masked", threshold: 5 });
});

test("a masked total carries the highest threshold met and nothing of the visible cells", () => {
  const t = totalDesCellules([c(40), { state: "masked", threshold: 8 }, { state: "masked", threshold: 6 }]);
  assert.deepEqual(t, { state: "masked", threshold: 8 });
  assert.ok(!("value" in t));
});

test("a total of no cell is a caller error, never zero", () => {
  assert.throws(() => totalDesCellules([]), TypeError);
});

// ---- empty-state code --------------------------------------------------------------------------------------------------------------
const ENTREE: EntreeEtats = {
  domainTeamCount: 3,
  offeredCycles: 2,
  summaryRowPresent: true,
  labelHistoryCollected: true,
  mappingValidated: true,
  realCountsHidden: false,
  readySource: "column",
};

test("a regular case: no empty state, no notice, the Ready source code of the referential", () => {
  assert.deepEqual(choisirEtats(ENTREE), { emptyState: null, notices: [], readySource: "ready_source_column" });
  assert.equal(choisirEtats({ ...ENTREE, readySource: "label" }).readySource, "ready_source_label");
});

test("a domain of fewer than three teams: the explained empty state wins over every other state", () => {
  for (const n of [0, 1, 2]) {
    const r = choisirEtats({ ...ENTREE, domainTeamCount: n, offeredCycles: 0, summaryRowPresent: false, labelHistoryCollected: false, mappingValidated: false });
    assert.equal(r.emptyState, "domain_too_small", String(n));
  }
  assert.equal(choisirEtats({ ...ENTREE, domainTeamCount: 3 }).emptyState, null);
  assert.equal(choisirEtats({ ...ENTREE, domainTeamCount: 4 }).emptyState, null);
});

test("no cycle to offer: no_cycle_configured, before no epic and no history", () => {
  assert.equal(choisirEtats({ ...ENTREE, offeredCycles: 0, summaryRowPresent: false, labelHistoryCollected: false }).emptyState, "no_cycle_configured");
});

test("no summary row for the cycle: no_epic_for_cycle with a history, no_label_history without", () => {
  assert.equal(choisirEtats({ ...ENTREE, summaryRowPresent: false }).emptyState, "no_epic_for_cycle");
  assert.equal(choisirEtats({ ...ENTREE, summaryRowPresent: false, labelHistoryCollected: false }).emptyState, "no_label_history");
});

test("no label history is an empty state in every case, even with a summary row (R-20261031-58)", () => {
  assert.deepEqual(choisirEtats({ ...ENTREE, labelHistoryCollected: false }), {
    emptyState: "no_label_history",
    notices: [],
    readySource: "ready_source_column",
  });
});

test("real data with counts not shown: its own empty state, after the small domain and before every other state", () => {
  assert.equal(choisirEtats({ ...ENTREE, realCountsHidden: true }).emptyState, "real_counts_not_shown");
  assert.equal(choisirEtats({ ...ENTREE, realCountsHidden: true, offeredCycles: 0, summaryRowPresent: false, labelHistoryCollected: false }).emptyState, "real_counts_not_shown");
  assert.equal(choisirEtats({ ...ENTREE, realCountsHidden: true, domainTeamCount: 2 }).emptyState, "domain_too_small");
  assert.deepEqual(choisirEtats({ ...ENTREE, realCountsHidden: true, mappingValidated: false }).notices, []);
});

test("the order of the empty states: domain, real counts, cycle, history, epic", () => {
  const tout = { ...ENTREE, domainTeamCount: 1, realCountsHidden: true, offeredCycles: 0, labelHistoryCollected: false, summaryRowPresent: false };
  assert.equal(choisirEtats(tout).emptyState, "domain_too_small");
  assert.equal(choisirEtats({ ...tout, domainTeamCount: 3 }).emptyState, "real_counts_not_shown");
  assert.equal(choisirEtats({ ...tout, domainTeamCount: 3, realCountsHidden: false }).emptyState, "no_cycle_configured");
  assert.equal(choisirEtats({ ...tout, domainTeamCount: 3, realCountsHidden: false, offeredCycles: 1 }).emptyState, "no_label_history");
  assert.equal(choisirEtats({ ...tout, domainTeamCount: 3, realCountsHidden: false, offeredCycles: 1, labelHistoryCollected: true }).emptyState, "no_epic_for_cycle");
});

test("a cycle key outside [a-z0-9-]{1,32} is a caller error; a requested key outside it is unknown", () => {
  for (const mauvaise of ["C-01", "c_01", "c 01", "", "a".repeat(33), "é"]) {
    assert.throws(() => choisirCycle([{ ...CYCLES[1], key: mauvaise }], undefined), TypeError, mauvaise);
    assert.deepEqual(choisirCycle(CYCLES, mauvaise), { ok: false, status: 422, code: "CYCLE_UNKNOWN" }, mauvaise);
  }
  assert.doesNotThrow(() => choisirCycle([{ ...CYCLES[1], key: "a".repeat(32) }], undefined));
});

test("an unvalidated mapping is a notice (columns not computed), not an empty state", () => {
  assert.deepEqual(choisirEtats({ ...ENTREE, mappingValidated: false }), {
    emptyState: null,
    notices: ["mapping_not_validated"],
    readySource: "ready_source_label",
  });
});

test("while the mapping is not validated the Ready source is the label, whatever the referential says; validated, the referential decides", () => {
  assert.equal(choisirEtats({ ...ENTREE, mappingValidated: false, readySource: "column" }).readySource, "ready_source_label");
  assert.equal(choisirEtats({ ...ENTREE, mappingValidated: false, readySource: "label" }).readySource, "ready_source_label");
  assert.equal(choisirEtats({ ...ENTREE, mappingValidated: true, readySource: "column" }).readySource, "ready_source_column");
});

test("the notice and the columns are tied: with mapping_not_validated the columns, their total and the candidates are absent", () => {
  const colonnes = [{ column: "col_a", mapped: true, count: c(12) }];
  const total = c(12);
  const candidats = c(7);
  assert.deepEqual(cadrerSelonMapping(["mapping_not_validated"], colonnes, total, candidats), { columns: [], columnsTotal: null, candidates: null });
  assert.deepEqual(cadrerSelonMapping([], colonnes, total, candidats), { columns: colonnes, columnsTotal: total, candidates: candidats });
});

test("the notices are empty when an empty state is explained", () => {
  const r = choisirEtats({ ...ENTREE, domainTeamCount: 2, mappingValidated: false, labelHistoryCollected: false });
  assert.equal(r.emptyState, "domain_too_small");
  assert.deepEqual(r.notices, []);
});

test("a cycle date that is not AAAA-MM-JJ is a caller error (dates are compared as text)", () => {
  for (const mauvaise of ["2026-1-01", "01/11/2026", "2026-11-01T00:00", ""]) {
    assert.throws(() => choisirCycle([{ ...CYCLES[1], start: mauvaise }], undefined), TypeError, mauvaise);
    assert.throws(() => choisirCycle([{ ...CYCLES[1], end: mauvaise }], undefined), TypeError, mauvaise);
  }
});

test("the only notice is the mapping one: no_label_history is never a notice", () => {
  assert.deepEqual(choisirEtats({ ...ENTREE, mappingValidated: false, labelHistoryCollected: false }).notices, []);
  assert.deepEqual(choisirEtats({ ...ENTREE, mappingValidated: false }).notices, ["mapping_not_validated"]);
});

test("a blocking empty state carries no notice at all", () => {
  const r = choisirEtats({ ...ENTREE, summaryRowPresent: false, mappingValidated: false });
  assert.equal(r.emptyState, "no_epic_for_cycle");
  assert.deepEqual(r.notices, []);
});

test("a count that is not a non-negative integer is a caller error", () => {
  for (const mauvais of [-1, 1.5, Number.NaN]) {
    assert.throws(() => choisirEtats({ ...ENTREE, domainTeamCount: mauvais }), TypeError);
    assert.throws(() => choisirEtats({ ...ENTREE, offeredCycles: mauvais }), TypeError);
  }
  for (const mauvais of [1, 0, "true", null]) {
    assert.throws(() => choisirEtats({ ...ENTREE, summaryRowPresent: mauvais as never }), TypeError);
    assert.throws(() => choisirEtats({ ...ENTREE, realCountsHidden: mauvais as never }), TypeError);
  }
});

// ---- masking: the function of task 15.3, reused ------------------------------------------------------------------------------------
test("the masking is the function of task 15.3, which refuses by default a view it does not port: nothing here masks", () => {
  const vue = { name: "v_cycle_unported", schema: "flow", roleKind: "flow", countColumns: ["epics"], plainColumns: ["cycle"] } as const;
  assert.throws(() => masquerVue({ ...vue, countColumns: [...vue.countColumns], plainColumns: [...vue.plainColumns] }, [{ cycle: "c-01", epics: 7 }], 5), /non port/);
});

test("the module does not copy the masking and recomputes no rule of the views (static)", () => {
  const dossier = new URL("../src/cycle-preparation/", import.meta.url);
  for (const fichier of ["schemas.ts", "fonctions.ts"]) {
    const source = readFileSync(new URL(fichier, dossier), "utf8").replace(/^\s*\/\/.*$/gm, "");
    assert.ok(!/PLANCHER\s*[-+<>]|<\s*(effectif|seuil)|compteDeLigne|VUES_PORTEES/.test(source), `${fichier}: no masking rule copied`);
    assert.ok(!/candidate|candidat|readyLabel|inEpicReview\s*[-+*]/i.test(source.replace(/"candidates"|candidates:/g, "")), `${fichier}: no view rule`);
  }
});

// Q115 (R-20261031-62): the subpath `./cycle-preparation` points to the pure module, which reaches neither typebox nor schemas.ts at run time.
test("the pure module imports neither typebox nor schemas.ts, directly or through what it imports at run time (static)", () => {
  const racine = new URL("../src/", import.meta.url);
  const a = (source: string): string[] =>
    [
      ...[...source.matchAll(/^(?:import|export)\s+(?!type\b)[^;]*?from\s+["']([^"']+)["']/gm)].map((m) => m[1]),
      ...[...source.matchAll(/^import\s+["']([^"']+)["']/gm)].map((m) => m[1]),
    ];
  const vus = new Set<string>();
  const atteints: string[] = [];
  const suivre = (chemin: string): void => {
    if (vus.has(chemin)) return;
    vus.add(chemin);
    for (const s of a(readFileSync(new URL(chemin, racine), "utf8"))) {
      if (s.startsWith(".")) suivre(new URL(s, new URL(chemin, racine)).href.slice(racine.href.length));
      else atteints.push(`${chemin} importe ${s}`);
    }
  };
  suivre("cycle-preparation/pur.ts");
  assert.deepEqual(atteints, []);
  assert.ok(![...vus].some((f) => f.endsWith("schemas.ts") || f.endsWith("cellule.ts")), [...vus].join(", "));
  assert.ok(vus.has("cycle-preparation/fonctions.ts") && vus.has("cycle-preparation/codes.ts"));
  const exports = (JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { exports: Record<string, string> }).exports;
  assert.equal(exports["./cycle-preparation"], "./src/cycle-preparation/pur.ts");
});
