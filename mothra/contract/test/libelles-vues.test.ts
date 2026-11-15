// The two fixed labels of the contract (equipe.ts) are the ones the SQL views write: source db/migrations, gap detected here.
// Without this test a typo in the SQL or in the constant would give `kind: "team"` to a pseudo-row, silently.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { LIBELLE_PRODUIT, LIBELLE_SANS_EQUIPE } from "../src/equipe.ts";

const MIGRATIONS = new URL("../../../db/migrations/", import.meta.url);

function sqlDesMigrations(): string {
  return readdirSync(MIGRATIONS)
    .filter((f) => f.endsWith(".sql"))
    .sort()
    .map((f) => readFileSync(new URL(f, MIGRATIONS), "utf8").replace(/--[^\n]*/g, ""))
    .join("\n");
}

test("the migrations are read (an empty path must not give a green test)", () => {
  assert.ok(sqlDesMigrations().length > 1000);
});

test("the label of the row without a team is the one the views write", () => {
  assert.ok(sqlDesMigrations().includes(`'${LIBELLE_SANS_EQUIPE}'`), LIBELLE_SANS_EQUIPE);
});

test("the label of the product row is the one the views write", () => {
  assert.ok(sqlDesMigrations().includes(`'${LIBELLE_PRODUIT}'::text`), LIBELLE_PRODUIT);
});
