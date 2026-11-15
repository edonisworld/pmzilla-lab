// Task 4.1: the structured masked cell of design D3, its generator and the freshness of the generated JSON Schema files (design D5).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import Value from "typebox/value";

import { cellule, SchemaCellule } from "../src/cellule.ts";
import type { Cellule } from "../src/cellule.ts";
import { genererSchemas, verifierFraicheur } from "../src/generer.ts";

test("a value cell holds the state and an integer at or above the floor", () => {
  assert.equal(Value.Check(SchemaCellule, { state: "value", value: 12 }), true);
  assert.equal(Value.Check(SchemaCellule, { state: "value", value: 5 }), true);
  assert.equal(Value.Check(SchemaCellule, { state: "value", value: 4 }), false);
  assert.equal(Value.Check(SchemaCellule, { state: "value", value: 7.5 }), false);
  assert.equal(Value.Check(SchemaCellule, { state: "value" }), false);
});

test("a masked cell holds the state and a threshold of at least five, and no value property", () => {
  assert.equal(Value.Check(SchemaCellule, { state: "masked", threshold: 5 }), true);
  assert.equal(Value.Check(SchemaCellule, { state: "masked", threshold: 10 }), true);
  assert.equal(Value.Check(SchemaCellule, { state: "masked", threshold: 4 }), false);
  assert.equal(Value.Check(SchemaCellule, { state: "masked" }), false);
});

test("an extra field is refused, a value or an estimate on a masked cell included", () => {
  assert.equal(Value.Check(SchemaCellule, { state: "masked", threshold: 5, value: 3 }), false);
  assert.equal(Value.Check(SchemaCellule, { state: "masked", threshold: 5, value: null }), false);
  assert.equal(Value.Check(SchemaCellule, { state: "masked", threshold: 5, estimate: 3 }), false);
  assert.equal(Value.Check(SchemaCellule, { state: "value", value: 9, threshold: 5 }), false);
  assert.equal(Value.Check(SchemaCellule, { state: "value", value: 9, reason: "under_threshold" }), false);
});

test("an unknown state, a bare number or null is not a cell", () => {
  assert.equal(Value.Check(SchemaCellule, { state: "lt5", threshold: 5 }), false);
  assert.equal(Value.Check(SchemaCellule, 12), false);
  assert.equal(Value.Check(SchemaCellule, null), false);
});

// Compiles only if `state === "masked"` narrows the union: on the masked branch `value` does not exist, on the other `threshold` does not.
function lire(c: Cellule): { threshold: number } | { value: number } {
  if (c.state === "masked") {
    // @ts-expect-error a masked cell has no value property
    void c.value;
    return { threshold: c.threshold };
  }
  // @ts-expect-error a value cell has no threshold property
  void c.threshold;
  return { value: c.value };
}

test("the state discriminates the cell type: narrowing excludes value on a masked cell", () => {
  assert.deepEqual(lire({ state: "masked", threshold: 5 }), { threshold: 5 });
  assert.deepEqual(lire({ state: "value", value: 9 }), { value: 9 });
});

test("the published schema types state as a const on each branch, and not as an enum", () => {
  const branches = (JSON.parse(readFileSync(new URL("../../../contrats/schemas/cellule.schema.json", import.meta.url), "utf8")) as {
    anyOf: { properties: { state: Record<string, unknown> } }[];
  }).anyOf;
  assert.deepEqual(
    branches.map((b) => b.properties.state.const),
    ["value", "masked"],
  );
  for (const b of branches) {
    assert.equal("const" in b.properties.state, true);
    assert.equal("enum" in b.properties.state, false);
  }
});

test("a count at or above the threshold becomes a value cell", () => {
  assert.deepEqual(cellule(12, 5), { state: "value", value: 12 });
  assert.deepEqual(cellule(5, 5), { state: "value", value: 5 });
  assert.deepEqual(cellule(10, 10), { state: "value", value: 10 });
});

test("a count under the threshold becomes a masked cell without any value property", () => {
  const masquee = cellule(3, 5);
  assert.deepEqual(masquee, { state: "masked", threshold: 5 });
  assert.equal("value" in masquee, false);
  assert.deepEqual(cellule(0, 5), { state: "masked", threshold: 5 });
  assert.deepEqual(cellule(8, 10), { state: "masked", threshold: 10 });
});

test("NULL from a view becomes a masked cell with the effective threshold", () => {
  assert.deepEqual(cellule(null, 5), { state: "masked", threshold: 5 });
  assert.deepEqual(cellule(null, 10), { state: "masked", threshold: 10 });
});

test("a threshold under the floor is raised to five in the cell", () => {
  assert.deepEqual(cellule(null, 3), { state: "masked", threshold: 5 });
  assert.deepEqual(cellule(4, 0), { state: "masked", threshold: 5 });
});

test("a count that is not a non-negative integer is refused, never turned into a cell", () => {
  assert.throws(() => cellule(2.5, 5), TypeError);
  assert.throws(() => cellule(-1, 5), TypeError);
  assert.throws(() => cellule(Number.NaN, 5), TypeError);
  assert.throws(() => cellule(7, 5.5), TypeError);
});

test("every cell built from a count or NULL validates against the schema", () => {
  for (const compte of [null, 0, 1, 4, 5, 6, 40]) {
    for (const seuil of [5, 6, 10]) {
      assert.equal(Value.Check(SchemaCellule, cellule(compte, seuil)), true, `${compte} / ${seuil}`);
    }
  }
});

test("the generator writes one JSON Schema file per TypeBox schema, sorted keys, final newline", () => {
  const fichiers = genererSchemas();
  assert.deepEqual(Object.keys(fichiers).sort(), [
    "contrats/schemas/cellule.schema.json",
    "contrats/schemas/reponse-vue.schema.json",
    "contrats/schemas/vues.schema.json",
  ]);
  for (const texte of Object.values(fichiers)) {
    assert.equal(texte.endsWith("}\n"), true);
    assert.equal(texte.includes("~"), false, "no internal TypeBox marker in the published schema");
    JSON.parse(texte);
  }
  assert.deepEqual(genererSchemas(), fichiers, "deterministic");
});

test("the freshness check names the stale or missing file and nothing else", () => {
  const attendus = { "contrats/schemas/a.schema.json": "{}\n", "contrats/schemas/b.schema.json": "[]\n" };
  const tous = (chemin: string) => attendus[chemin as keyof typeof attendus];
  assert.deepEqual(verifierFraicheur(attendus, tous), []);
  const perime = (chemin: string) => (chemin.endsWith("b.schema.json") ? "[ ]\n" : tous(chemin));
  assert.deepEqual(verifierFraicheur(attendus, perime), ["schéma JSON périmé : contrats/schemas/b.schema.json (régénérer)"]);
  const absent = (chemin: string) => (chemin.endsWith("a.schema.json") ? undefined : tous(chemin));
  assert.deepEqual(verifierFraicheur(attendus, absent), ["schéma JSON périmé : contrats/schemas/a.schema.json (régénérer)"]);
});

test("the tracked JSON Schema files are the generator's output", () => {
  const racine = new URL("../../../", import.meta.url);
  const lire = (chemin: string): string | undefined => {
    try {
      return readFileSync(new URL(chemin, racine), "utf8");
    } catch {
      return undefined;
    }
  };
  assert.deepEqual(verifierFraicheur(genererSchemas(), lire), []);
});
