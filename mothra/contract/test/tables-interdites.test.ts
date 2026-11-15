// Audit #629, A-95 (R-20261109-20): the list of forbidden tables of the loader equals the tables of the flow and quality schemas created by the
// migrations, in both directions. Source: db/migrations; same expression as tests/flow_views/test_contrat_vues.py (RE_TABLE).
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { RefusContrat, TABLES_INTERDITES, validerContrat } from "../src/chargeur.ts";
import { SchemaVues } from "../src/vues.ts";

const MIGRATIONS = new URL("../../../db/migrations/", import.meta.url);

// R-20261109-21 Q1 (a): the schemas of the list are the ones the contract allows (GENRE_DE_ROLE, vues.ts:7), read from its schema, not copied.
// If the contract ever allows another schema, the tables of that schema enter the comparison below and the test fails until the list holds them.
const MOTIF_SCHEMAS = (SchemaVues as unknown as { properties: { views: { items: { properties: { schema: { pattern: string } } } } } }).properties.views.items.properties
  .schema.pattern;
const SCHEMAS = (/^\^\(([a-z|]+)\)\$$/.exec(MOTIF_SCHEMAS)?.[1] ?? "").split("|").filter((s) => s !== "");
const RE_TABLE = /CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\.(\w+)/gi;

function tablesDesMigrations(): Array<{ schema: string; nom: string }> {
  const trouvees: Array<{ schema: string; nom: string }> = [];
  for (const fichier of readdirSync(MIGRATIONS).filter((f) => f.endsWith(".sql")).sort()) {
    const sql = readFileSync(new URL(fichier, MIGRATIONS), "utf8").replace(/--[^\n]*/g, "");
    for (const m of sql.matchAll(RE_TABLE)) {
      const schema = m[1].toLowerCase();
      if (SCHEMAS.includes(schema)) trouvees.push({ schema, nom: m[2].toLowerCase() });
    }
  }
  return trouvees;
}

test("the schemas compared are the two of the contract, flow and quality (read from its schema, so a widening shows here)", () => {
  assert.deepEqual([...SCHEMAS].sort(), ["flow", "quality"], `motif du contrat : ${MOTIF_SCHEMAS} ; la liste du chargeur doit couvrir les tables de tout schéma permis`);
});

test("the migrations are read: at least 40 tables, from both schemas (an empty path must not give a green test)", () => {
  const tables = tablesDesMigrations();
  assert.ok(tables.length >= 40, `tables extraites : ${tables.length}`);
  assert.ok(tables.some((t) => t.schema === "flow"));
  assert.ok(tables.some((t) => t.schema === "quality"));
});

test("the forbidden tables of the loader are the tables of the migrations, in both directions", () => {
  const attendues = [...new Set(tablesDesMigrations().map((t) => t.nom))].sort();
  const listees = [...TABLES_INTERDITES].sort();
  const manquantes = attendues.filter((n) => !TABLES_INTERDITES.has(n));
  const enTrop = listees.filter((n) => !attendues.includes(n));
  assert.deepEqual({ manquantes, enTrop }, { manquantes: [], enTrop: [] }, "liste du chargeur et migrations d'accord");
});

test("a contract whose view bears the name of a table is refused", () => {
  // Witness: the same shape of contract with a name that is no table is accepted, so the refusals below come from the name of the table.
  assert.doesNotThrow(() =>
    validerContrat({ views: [{ name: "v_temoin", schema: "flow", roleKind: "flow", countColumns: ["tickets"], plainColumns: ["team"] }] }),
  );
  for (const { schema, nom } of tablesDesMigrations()) {
    const contrat = { views: [{ name: nom, schema, roleKind: schema, countColumns: ["tickets"], plainColumns: ["team"] }] };
    try {
      validerContrat(contrat);
      assert.fail(`accepté : ${schema}.${nom}`);
    } catch (erreur) {
      assert.ok(erreur instanceof RefusContrat, `${schema}.${nom}`);
      assert.equal(erreur.code, "CONTRACT_INVALID", `${schema}.${nom}`);
    }
  }
});
