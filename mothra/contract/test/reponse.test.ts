// The answer of the view route, shared by the server and the front: columns are codes, rows hold cells and plain values.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import Value from "typebox/value";

import { SchemaReponseVue, estReponseVue, schemaReponseDeVue } from "../src/reponse.ts";
import type { ReponseVue } from "../src/reponse.ts";
import type { Vue } from "../src/vues.ts";
import * as publique from "../src/index.ts";

const VUE: Vue = { name: "v_x", schema: "flow", roleKind: "flow", countColumns: ["n"], plainColumns: ["a"] };

const EXEMPLE: ReponseVue = {
  view: "v_x",
  threshold: 5,
  columns: ["a", "n"],
  rows: [{ a: "x", n: { state: "value", value: 12 } }, { a: null, n: { state: "masked", threshold: 5 } }],
  sources: ["flow"],
};

test("estReponseVue accepts a valid answer and refuses an invalid one", () => {
  assert.equal(estReponseVue(EXEMPLE), true);
  assert.equal(estReponseVue({ ...EXEMPLE, extra: 1 }), false);
  assert.equal(estReponseVue({ ...EXEMPLE, rows: [{ a: { x: 1 } }] }), false);
  assert.equal(estReponseVue(null), false);
  assert.equal(estReponseVue("x"), false);
});

test("the package exports the answer schema, its type and the per-view builder", () => {
  assert.equal(publique.SchemaReponseVue, SchemaReponseVue);
  assert.equal(publique.schemaReponseDeVue, schemaReponseDeVue);
});

test("columns are a list of codes: an object column is refused", () => {
  assert.equal(Value.Check(SchemaReponseVue, EXEMPLE), true);
  assert.equal(Value.Check(SchemaReponseVue, { ...EXEMPLE, columns: [{ name: "a", kind: "plain" }] }), false);
});

test("the generic answer holds cells and plain values, nothing nested, nothing extra at the top", () => {
  assert.equal(Value.Check(SchemaReponseVue, { ...EXEMPLE, rows: [{ a: { x: 1 } }] }), false);
  assert.equal(Value.Check(SchemaReponseVue, { ...EXEMPLE, rows: [{ n: { state: "masked", threshold: 5, value: 3 } }] }), false);
  assert.equal(Value.Check(SchemaReponseVue, { ...EXEMPLE, extra: 1 }), false);
  assert.equal(Value.Check(SchemaReponseVue, { ...EXEMPLE, threshold: 4 }), false);
});

test("the per-view schema holds the columns of the view and nothing else, a count column only as a cell", () => {
  const schema = schemaReponseDeVue(VUE);
  assert.equal(Value.Check(schema, EXEMPLE), true);
  assert.equal(Value.Check(schema, { ...EXEMPLE, view: "v_y" }), false);
  assert.equal(Value.Check(schema, { ...EXEMPLE, rows: [{ a: "x", n: 12 }] }), false);
  assert.equal(Value.Check(schema, { ...EXEMPLE, rows: [{ a: "x", n: { state: "value", value: 12 }, b: "y" }] }), false);
  assert.equal(Value.Check(schema, { ...EXEMPLE, rows: [{ a: "x" }] }), false);
});

test("the published file of the answer schema lists the same required fields as the schema", () => {
  const publie = JSON.parse(readFileSync(new URL("../../../contrats/schemas/reponse-vue.schema.json", import.meta.url), "utf8")) as {
    required: string[];
    properties: Record<string, { items?: { type?: string } }>;
  };
  assert.deepEqual(publie.required, ["view", "threshold", "columns", "rows", "sources"]);
  assert.equal(publie.properties.columns.items?.type, "string");
});
