// Tasks 31.1 and 31.2 (mothra-slices D35): the scope check, the range check and the range total of the shared filters framework.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { cellule } from "../src/cellule.ts";
import type { Cellule } from "../src/cellule.ts";
import Value from "typebox/value";

import { SchemaCreationFiche } from "../src/fiche-schema.ts";
import { SchemaSerieEquipe } from "../src/lead-cycle.ts";
import {
  MOTIF_IDENTIFIANT_EQUIPE,
  SchemaFiltres,
  identifiantEquipe,
  scopeFiche,
  totalDePlage,
  verifierFiltres,
} from "../src/filtres.ts";

// Reading date: 2026-11-19, so the running quarter is 2026-Q4 and the last closed one is 2026-Q3.
const OPT = { today: "2026-11-19" };

test("no team means the whole product, a team identifier means that team", () => {
  assert.deepEqual(verifierFiltres({ from: "2026-Q2", to: "2026-Q3" }, OPT), {
    ok: true,
    scope: { kind: "product" },
    from: "2026-Q2",
    to: "2026-Q3",
    periods: ["2026-Q2", "2026-Q3"],
  });
  const r = verifierFiltres({ team: "t-07", from: "2026-Q3", to: "2026-Q3" }, OPT);
  assert.equal(r.ok && r.scope.kind === "team" && r.scope.team, "t-07");
});

test("a multi-team request, an array, a list or a malformed identifier is refused with SCOPE_INVALID", () => {
  const refuses = [
    { team: ["t-1", "t-2"] },
    { team: "t-1,t-2" },
    { team: "t-1 t-2" },
    { team: "" },
    { team: 7 },
    { team: { id: "t-1" } },
    { team: "x".repeat(65) },
  ];
  for (const t of refuses) {
    assert.deepEqual(verifierFiltres({ ...t, from: "2026-Q2", to: "2026-Q3" }, OPT), { ok: false, status: 422, code: "SCOPE_INVALID" });
  }
});

// The querystring schema is the one source for what is outside the schema (400 INVALID_REQUEST, author's decision R-20261030-54):
// an undeclared field (a sort parameter included), a missing from or to, a wrong type. The team is read as unknown so that a repeated
// team reaches `verifierFiltres`, which refuses it with 422 SCOPE_INVALID.
test("the querystring schema refuses an undeclared field, a missing from or to and a wrong type", () => {
  const base = { from: "2026-Q2", to: "2026-Q3" };
  assert.equal(Value.Check(SchemaFiltres, base), true);
  assert.equal(Value.Check(SchemaFiltres, { ...base, team: "t-1" }), true);
  assert.equal(Value.Check(SchemaFiltres, { ...base, team: ["t-1", "t-2"] }), true);
  for (const mauvais of [
    { ...base, sort: "asc" },
    { ...base, order: "team" },
    { ...base, teams: "a" },
    { to: "2026-Q3" },
    { from: "2026-Q2" },
    {},
    { from: 2026, to: "2026-Q3" },
    { from: ["2026-Q2"], to: "2026-Q3" },
  ]) {
    assert.equal(Value.Check(SchemaFiltres, mauvais), false);
  }
});

test("the scope is checked before the range", () => {
  assert.deepEqual(verifierFiltres({ team: ["a"], from: "bad", to: "bad" }, OPT), { ok: false, status: 422, code: "SCOPE_INVALID" });
});

test("a range that is not whole closed quarters is refused with RANGE_INVALID", () => {
  const refuses = [
    { from: "2026-Q4", to: "2026-Q4" }, // running quarter
    { from: "2026-Q3", to: "2027-Q1" }, // future
    { from: "2026-Q3", to: "2026-Q2" }, // inverted
    { from: "2026-07", to: "2026-09" }, // months
    { from: "2026-W30", to: "2026-W31" }, // weeks
    { from: "2026-Q5", to: "2026-Q5" },
    { from: "2026-07-01", to: "2026-09-30" }, // dates
  ];
  for (const r of refuses) {
    assert.deepEqual(verifierFiltres(r, OPT), { ok: false, status: 422, code: "RANGE_INVALID" });
  }
});

test("a range longer than three quarters is refused, three quarters are accepted", () => {
  assert.deepEqual(verifierFiltres({ from: "2025-Q3", to: "2026-Q3" }, OPT), { ok: false, status: 422, code: "RANGE_INVALID" });
  assert.deepEqual(verifierFiltres({ from: "2025-Q4", to: "2026-Q3" }, OPT), { ok: false, status: 422, code: "RANGE_INVALID" }); // four quarters (R-20261114-49)
  const r = verifierFiltres({ from: "2026-Q1", to: "2026-Q3" }, OPT);
  assert.equal(r.ok && r.periods.length, 3);
});

test("a range outside the three closed quarters is refused even when it is three quarters or fewer", () => {
  for (const [from, to] of [["2020-Q1", "2020-Q4"], ["2024-Q1", "2024-Q4"], ["2025-Q3", "2025-Q3"], ["2025-Q1", "2025-Q4"], ["2025-Q4", "2025-Q4"]]) {
    assert.deepEqual(verifierFiltres({ from, to }, OPT), { ok: false, status: 422, code: "RANGE_INVALID" });
  }
  // The first quarter of the window is accepted (it is whole: the truncated-quarter flag is gone).
  assert.equal(verifierFiltres({ from: "2026-Q1", to: "2026-Q1" }, OPT).ok, true);
});

test("the quarter boundary: on the first day of a quarter the previous one is closed", () => {
  assert.equal(verifierFiltres({ from: "2026-Q3", to: "2026-Q3" }, { today: "2026-10-01" }).ok, true);
  assert.equal(verifierFiltres({ from: "2026-Q3", to: "2026-Q3" }, { today: "2026-09-30" }).ok, false);
  assert.equal(verifierFiltres({ from: "2025-Q4", to: "2025-Q4" }, { today: "2026-01-02" }).ok, true);
});

test("a refusal carries a code only, never a text", () => {
  const r = verifierFiltres({ team: ["a"], from: "x", to: "y" }, OPT);
  assert.deepEqual(Object.keys(r).sort(), ["code", "ok", "status"]);
});

// ---- 31.2: the range total

const v = (n: number): Cellule => cellule(n, 5);
const m = (seuil = 5): Cellule => cellule(null, seuil);

test("the range total is the sum of the counts when no period of the range is masked", () => {
  const donnees = [
    { period: "2026-Q1", count: v(10) },
    { period: "2026-Q2", count: v(7) },
    { period: "2026-Q3", count: v(5) },
  ];
  assert.deepEqual(totalDePlage(donnees, "2026-Q1", "2026-Q3"), { state: "value", value: 22 });
  assert.deepEqual(totalDePlage(donnees, "2026-Q2", "2026-Q3"), { state: "value", value: 12 });
});

test("one masked period makes the total a masked cell with no value, even when the others are large", () => {
  const donnees = [
    { period: "2026-Q1", count: v(500) },
    { period: "2026-Q2", count: m() },
    { period: "2026-Q3", count: v(500) },
  ];
  const t = totalDePlage(donnees, "2026-Q1", "2026-Q3");
  assert.deepEqual(t, { state: "masked", threshold: 5 });
  assert.equal("value" in t, false);
});

test("a masked period outside the range does not mask the total", () => {
  const donnees = [
    { period: "2026-Q1", count: m() },
    { period: "2026-Q2", count: v(8) },
    { period: "2026-Q3", count: v(9) },
  ];
  assert.deepEqual(totalDePlage(donnees, "2026-Q2", "2026-Q3"), { state: "value", value: 17 });
});

test("the masked total carries the highest threshold met, never under the floor", () => {
  const donnees = [
    { period: "2026-Q2", count: m(10) },
    { period: "2026-Q3", count: m(5) },
  ];
  assert.deepEqual(totalDePlage(donnees, "2026-Q2", "2026-Q3"), { state: "masked", threshold: 10 });
});

test("a missing or duplicated period, or a bad range, is a caller error", () => {
  assert.throws(() => totalDePlage([{ period: "2026-Q1", count: v(6) }], "2026-Q1", "2026-Q2"), TypeError);
  assert.throws(
    () => totalDePlage([{ period: "2026-Q1", count: v(6) }, { period: "2026-Q1", count: v(7) }], "2026-Q1", "2026-Q1"),
    TypeError,
  );
  assert.throws(() => totalDePlage([], "2026-Q3", "2026-Q1"), TypeError);
  assert.throws(() => totalDePlage([], "bad", "2026-Q1"), TypeError);
});

test("the range crosses a year boundary", () => {
  const donnees = [
    { period: "2025-Q4", count: v(6) },
    { period: "2026-Q1", count: v(6) },
  ];
  assert.deepEqual(totalDePlage(donnees, "2025-Q4", "2026-Q1"), { state: "value", value: 12 });
});

// Static test (task 31.2): no total over a range outside the contract's service function. A server route, a formatting or a front
// component never reduces cells by addition; they call `totalDePlage`.
function fichiers(dossier: string, sortie: string[] = []): string[] {
  for (const e of readdirSync(dossier, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name === "dist") continue;
    const chemin = join(dossier, e.name);
    if (e.isDirectory()) fichiers(chemin, sortie);
    else if (/\.(ts|tsx)$/.test(e.name)) sortie.push(chemin);
  }
  return sortie;
}

test("no route, formatting or component adds up cell values (static)", () => {
  const racine = join(import.meta.dirname, "..", "..");
  const concernes = [join(racine, "server", "src"), join(racine, "front", "src")].flatMap((d) => {
    try {
      return fichiers(d);
    } catch {
      return [];
    }
  });
  // Any addition on a `.value` (`+=`, `+`, a reduce on an intermediate variable included); contract/ is outside the scanned folders.
  const motif = /\+=?\s*[\w.]*\.value\b|\.value\s*\+/;
  const fautifs = concernes.filter((f) => motif.test(readFileSync(f, "utf8")));
  assert.deepEqual(fautifs, []);
});

// ---- the opaque team identifier (R-20261030-61)

const NOMS_SYNTHETIQUES = ["Team A", "Team B", "Team C", "Team D", "team a", "Équipe Z", "x".repeat(300), ""];

test("the team identifier is deterministic, at least 12 hexadecimal characters, and fits the pattern", () => {
  for (const nom of NOMS_SYNTHETIQUES) {
    const id = identifiantEquipe(nom);
    assert.equal(identifiantEquipe(nom), id);
    assert.match(id, /^[0-9a-f]+$/);
    assert.ok(id.length >= 12, "at least 12 characters");
    assert.equal(MOTIF_IDENTIFIANT_EQUIPE.test(id), true);
  }
});

test("two different synthetic names give two different identifiers, and the team scope never holds the name", () => {
  const ids = NOMS_SYNTHETIQUES.map(identifiantEquipe);
  assert.equal(new Set(ids).size, ids.length);
  for (const nom of ["Team A", "Team B", "Équipe Z"]) {
    const scope = scopeFiche({ kind: "team", team: identifiantEquipe(nom) });
    assert.ok(!scope.toLowerCase().includes(nom.toLowerCase()), "the scope holds the name");
  }
});

test("the identifier pattern refuses capitals, dots, spaces, lists and more than 59 characters", () => {
  for (const mauvais of ["", "T-1", "a.b", "a b", "a,b", "x".repeat(60)]) {
    assert.equal(MOTIF_IDENTIFIANT_EQUIPE.test(mauvais), false);
  }
  assert.equal(MOTIF_IDENTIFIANT_EQUIPE.test("x".repeat(59)), true);
});

test("the sheet scope is `product` or `team.<identifier>`, accepted by the sheet schema up to 64 characters", () => {
  assert.equal(scopeFiche({ kind: "product" }), "product");
  const id = identifiantEquipe("Team A");
  assert.equal(scopeFiche({ kind: "team", team: id }), `team.${id}`);
  const limite = scopeFiche({ kind: "team", team: "x".repeat(59) });
  assert.equal(limite.length, 64);
  for (const scope of [limite, scopeFiche({ kind: "team", team: id }), "product"]) {
    assert.equal(Value.Check(SchemaCreationFiche, { chart: "lead_cycle_h5", scope, dataDate: "2026-10-27" }), true);
  }
});

test("a team series of the lead-cycle answer carries a teamId of the pattern", () => {
  const serie = { team: "Team A", teamId: identifiantEquipe("Team A"), points: [] };
  assert.equal(Value.Check(SchemaSerieEquipe, serie), true);
  assert.equal(Value.Check(SchemaSerieEquipe, { team: "Team A", points: [] }), false);
  assert.equal(Value.Check(SchemaSerieEquipe, { ...serie, teamId: "Team A" }), false);
});

test("the filters use the same pattern for the team parameter: one definition", () => {
  const id = identifiantEquipe("Team A");
  assert.equal(verifierFiltres({ team: id, from: "2026-Q2", to: "2026-Q3" }, OPT).ok, true);
  assert.deepEqual(verifierFiltres({ team: "Team A", from: "2026-Q2", to: "2026-Q3" }, OPT), { ok: false, status: 422, code: "SCOPE_INVALID" });
  assert.deepEqual(verifierFiltres({ team: "x".repeat(60), from: "2026-Q2", to: "2026-Q3" }, OPT), { ok: false, status: 422, code: "SCOPE_INVALID" });
});
