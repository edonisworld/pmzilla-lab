// Task 16.1 (design D17, ADR 0006): database cases of the storage connection, on the throwaway database only. Skipped, never failed, when
// DBTEST_PORT or the superuser password of the throwaway server is absent (same guard as base.test.ts). The author runs them (tools/dbtest.sh).
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import pg from "pg";

import { lireEnvironnement } from "../../src/config/index.ts";
import { creerAccesPostgres, parametresConnexion } from "../../src/db/base.ts";
import { creerAccesStockage, parametresStockage } from "../../src/db/stockage.ts";
import { contrat, sautBaseJetable } from "../aide.ts";
import { creerBaseJetable } from "./base-jetable.ts";
import type { BaseJetable } from "./base-jetable.ts";

const saut = sautBaseJetable();
let base: BaseJetable | null = null;

before(async () => {
  if (saut === false) {
    base = await creerBaseJetable(lireEnvironnement());
  }
});

after(async () => {
  await base?.supprimer();
});

function configuration() {
  assert.ok(base !== null, "the throwaway database was not created");
  return base.configuration();
}

test("the storage connection runs as the storage role and reads its tables", { skip: saut }, async () => {
  const acces = creerAccesStockage(configuration());
  try {
    assert.equal(await acces.roleCourant(), "pmzilla_mothra");
  } finally {
    await acces.fermer();
  }
  const client = new pg.Client(parametresStockage(configuration()));
  await client.connect();
  try {
    for (const table of ["users", "sheets", "published_versions", "threshold_history"]) {
      await client.query(`SELECT 1 FROM mothra.${table} LIMIT 1`);
    }
  } finally {
    await client.end();
  }
});

test("under the storage connection a flow table, a flow view or a quality view is refused for insufficient privilege", { skip: saut }, async () => {
  const client = new pg.Client(parametresStockage(configuration()));
  await client.connect();
  try {
    for (const objet of ["flow.issues", `flow.${contrat.views[0].name}`, "quality.quality_by_team", "cases.cases"]) {
      await assert.rejects(client.query(`SELECT 1 FROM ${objet} LIMIT 1`), (erreur: { code?: string }) => erreur.code === "42501", objet);
    }
    await assert.rejects(client.query("CREATE TABLE mothra.zz (a int)"), (erreur: { code?: string }) => erreur.code === "42501");
  } finally {
    await client.end();
  }
});

test("under the view connection a table of the schema mothra is refused for insufficient privilege", { skip: saut }, async () => {
  const client = new pg.Client(parametresConnexion(configuration()));
  await client.connect();
  try {
    for (const table of ["users", "sheets", "published_versions", "threshold_history"]) {
      await assert.rejects(client.query(`SELECT 1 FROM mothra.${table} LIMIT 1`), (erreur: { code?: string }) => erreur.code === "42501", table);
    }
  } finally {
    await client.end();
  }
});

test("both connections of one server work side by side, each on its own side", { skip: saut }, async () => {
  const config = configuration();
  const vues = creerAccesPostgres(config);
  const stockage = creerAccesStockage(config);
  try {
    const lignes = await vues.lireVue(contrat.views[0]);
    assert.ok(lignes.length > 0);
    assert.equal(await stockage.roleCourant(), "pmzilla_mothra");
  } finally {
    await vues.fermer();
    await stockage.fermer();
  }
});
