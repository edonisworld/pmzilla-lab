// Task 22.1 (R-20261106-39, R-20261106-43, Q2 (a)): the only shown zero of the contract is items_old of v_team_lead_time_throughput.
// 0 is accepted on that column; 0, 3 and 4 are refused on every other column; 1, 3 and 4 are refused on items_old. `cellule` builds the zero cell only
// when the caller says the column is that one.
import assert from "node:assert/strict";
import { test } from "node:test";

import Value from "typebox/value";

import { cellule } from "../src/cellule.ts";
import { schemaReponseDeVue } from "../src/reponse.ts";
import type { Vue } from "../src/vues.ts";

const VUE: Vue = {
  name: "v_team_lead_time_throughput",
  schema: "flow",
  roleKind: "flow",
  countColumns: ["throughput", "items_lt", "items_ct", "items_old", "items_without_commitment"],
  plainColumns: ["team", "period", "quarter_start"],
  maskableColumns: ["lead_median_days", "lead_p85_days", "cycle_median_days", "cycle_p85_days"],
};

function reponse(colonne: string, valeur: number) {
  const ligne: Record<string, unknown> = { team: "A", kind: "team", period: "quarter", quarter_start: null };
  for (const c of VUE.countColumns) ligne[c] = { state: "value", value: 5 };
  for (const c of VUE.maskableColumns ?? []) ligne[c] = { state: "masked", threshold: 5 };
  ligne[colonne] = { state: "value", value: valeur };
  return { view: VUE.name, threshold: 5, columns: [], rows: [ligne], sources: [] };
}

test("a zero is accepted on items_old of the lead time view", () => {
  assert.equal(Value.Check(schemaReponseDeVue(VUE), reponse("items_old", 0)), true);
});

test("0, 3 and 4 are refused on every other count column", () => {
  for (const colonne of VUE.countColumns.filter((c) => c !== "items_old")) {
    for (const v of [0, 3, 4]) {
      assert.equal(Value.Check(schemaReponseDeVue(VUE), reponse(colonne, v)), false, `${colonne} ${v}`);
    }
  }
});

test("1, 3 and 4 are refused on items_old, 5 is accepted", () => {
  for (const v of [1, 3, 4]) {
    assert.equal(Value.Check(schemaReponseDeVue(VUE), reponse("items_old", v)), false, String(v));
  }
  assert.equal(Value.Check(schemaReponseDeVue(VUE), reponse("items_old", 5)), true);
});

test("a view other than the lead time view refuses a zero even on a column named items_old", () => {
  const autre: Vue = { ...VUE, name: "v_team_status" };
  assert.equal(Value.Check(schemaReponseDeVue(autre), { ...reponse("items_old", 0), view: "v_team_status" }), false);
});

test("cellule shows a zero only when the caller allows it, and still masks 1 to 4", () => {
  assert.deepEqual(cellule(0, 5), { state: "masked", threshold: 5 });
  assert.deepEqual(cellule(0, 5, true), { state: "value", value: 0 });
  assert.deepEqual(cellule(0, 10, true), { state: "value", value: 0 });
  for (const v of [1, 3, 4]) {
    assert.deepEqual(cellule(v, 5, true), { state: "masked", threshold: 5 }, String(v));
  }
  assert.deepEqual(cellule(null, 5, true), { state: "masked", threshold: 5 });
});
