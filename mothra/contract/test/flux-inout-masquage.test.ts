// Task 37.1 (routes): the masking of the rows of `v_team_flow_inout` (task 36.1) by `masquerVue`, the one TypeScript function of task 15.3,
// reused and never copied. The view is declared here by a literal (the contract file contrats/vues.json receives it with the view, in the
// branch of 36.1): these are the TypeScript cases of the primary rule and of rule D3 of the product row. The shared cases of contrats/ and
// their Python player come with 36.1.
import assert from "node:assert/strict";
import { test } from "node:test";

import { masquerVue } from "../src/masquage.ts";
import type { LigneBrute } from "../src/masquage.ts";
import { PLANCHER } from "../src/plancher.ts";
import { etiquetteTrimestre } from "../src/trimestres.ts";
import type { Vue } from "../src/vues.ts";

const VUE: Vue = {
  name: "v_team_flow_inout",
  schema: "flow",
  roleKind: "flow",
  countColumns: ["created", "done"],
  plainColumns: ["team", "quarter_start", "type_group"],
};

const ligne = (created: number | null, done: number | null, team = "(produit)"): LigneBrute => ({
  team,
  quarter_start: "2026-07-01",
  type_group: "story",
  created,
  done,
});

test("the view is carried by the masking function (not refused), its plain columns are kept as they are", () => {
  // H-05: a team row of the same group (counts at or above every threshold used here) so that the product row is not masked by rule D3.
  const [sortie] = masquerVue(VUE, [ligne(40, 30), ligne(40, 40, "team-a")], 5);
  assert.equal(sortie.team, "(produit)");
  assert.equal(sortie.quarter_start, "2026-07-01");
  assert.equal(sortie.type_group, "story");
  assert.deepEqual(sortie.created, { state: "value", value: 40 });
  assert.deepEqual(sortie.done, { state: "value", value: 30 });
});

const CAS: Array<{ nom: string; created: number | null; done: number | null; seuil: number; attendu: [unknown, unknown] }> = [
  { nom: "at the floor", created: 5, done: 5, seuil: 5, attendu: [{ state: "value", value: 5 }, { state: "value", value: 5 }] },
  { nom: "under the floor", created: 4, done: 0, seuil: 5, attendu: [{ state: "masked", threshold: 5 }, { state: "masked", threshold: 5 }] },
  { nom: "NULL from the view", created: null, done: 12, seuil: 5, attendu: [{ state: "masked", threshold: 5 }, { state: "value", value: 12 }] },
  { nom: "raised threshold", created: 9, done: 10, seuil: 10, attendu: [{ state: "masked", threshold: 10 }, { state: "value", value: 10 }] },
  { nom: "threshold under the floor is raised", created: 4, done: 6, seuil: 2, attendu: [{ state: "masked", threshold: PLANCHER }, { state: "value", value: 6 }] },
];

for (const cas of CAS) {
  test(`primary rule on v_team_flow_inout: ${cas.nom}`, () => {
    // H-05: a team row of the same group at 40 (above every threshold of the cases), so that rule D3 leaves the product row to the primary rule.
    const [sortie] = masquerVue(VUE, [ligne(cas.created, cas.done), ligne(40, 40, "team-a")], cas.seuil);
    assert.deepEqual([sortie.created, sortie.done], cas.attendu);
  });
}

test("a masked cell keeps nothing of the count", () => {
  const [sortie] = masquerVue(VUE, [ligne(7, 8)], 10);
  assert.deepEqual(Object.keys(sortie.created as object).sort(), ["state", "threshold"]);
  assert.ok(!JSON.stringify(sortie).includes('"value":7'));
  assert.ok(!JSON.stringify(sortie).includes('"value":8'));
});

// Rule D3 of the product row (R-144, model `_masque_part` of tools/flow_views.py): for each (quarter_start, type_group) and each count column,
// the cell of the row `(produit)` is shown only when every non-product row of the same column, `(sans équipe)` included, is shown.
const SANS_EQUIPE = "(sans équipe)";
const groupe = (team: string, created: number | null, done: number | null, quarter = "2026-07-01", type = "story"): LigneBrute => ({
  team,
  quarter_start: quarter,
  type_group: type,
  created,
  done,
});

test("D3: at threshold 10 a team cell at 7 masks the product cell of its column", () => {
  const [produit] = masquerVue(VUE, [groupe("(produit)", 40, 40), groupe("team-a", 20, 20), groupe("team-b", 7, 20)], 10);
  assert.deepEqual(produit.created, { state: "masked", threshold: 10 });
  assert.deepEqual(produit.done, { state: "value", value: 40 });
});

test("D3: at threshold 5 the same rows change nothing", () => {
  const sortie = masquerVue(VUE, [groupe("(produit)", 40, 40), groupe("team-a", 20, 20), groupe("team-b", 7, 20)], 5);
  assert.deepEqual(sortie[0].created, { state: "value", value: 40 });
  assert.deepEqual(sortie[2].created, { state: "value", value: 7 });
});

test("D3: a NULL team cell masks the product cell; the other column is judged on its own", () => {
  const [produit] = masquerVue(VUE, [groupe("(produit)", 40, 40), groupe("team-a", null, 20)], 5);
  assert.deepEqual(produit.created, { state: "masked", threshold: 5 });
  assert.deepEqual(produit.done, { state: "value", value: 40 });
});

test("D3: the row without a team counts with the teams", () => {
  const [produit] = masquerVue(VUE, [groupe("(produit)", 40, 40), groupe("team-a", 20, 20), groupe(SANS_EQUIPE, 2, 20)], 5);
  assert.deepEqual(produit.created, { state: "masked", threshold: 5 });
  assert.deepEqual(produit.done, { state: "value", value: 40 });
});

test("D3: the groups are independent by quarter and by type group", () => {
  const lignes = [
    groupe("(produit)", 40, 40),
    groupe("team-a", 3, 20),
    groupe("(produit)", 40, 40, "2026-07-01", "defect"),
    groupe("team-a", 20, 20, "2026-07-01", "defect"),
    groupe("(produit)", 40, 40, "2026-04-01"),
    groupe("team-a", 20, 20, "2026-04-01"),
  ];
  const sortie = masquerVue(VUE, lignes, 5);
  assert.deepEqual(sortie[0].created, { state: "masked", threshold: 5 });
  assert.deepEqual(sortie[2].created, { state: "value", value: 40 });
  assert.deepEqual(sortie[4].created, { state: "value", value: 40 });
});

test("the quarter label of a quarter_start is the one of the panels", () => {
  assert.equal(etiquetteTrimestre("2025-10-01"), "2025-Q4");
  assert.equal(etiquetteTrimestre("2026-07-01"), "2026-Q3");
});
