// Task 6.3: the connection is opened under the flow view-limited role only, with the secret of the configuration module; the SQL is built
// from the contract. The database tests use the throwaway-database helper (base-jetable.ts), which needs DBTEST_PORT and the superuser
// password of the throwaway server (PMZILLA_LAB_DB_PASSWORD) from tools/dbtest.sh: they are skipped otherwise, with a reason naming the
// missing variable, never failed. This file reads the environment only through the configuration module.
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import pg from "pg";

import { chargerConfiguration, lireEnvironnement } from "../../src/config/index.ts";
import { DELAI_REQUETE_MS, creerAccesPostgres, parametresConnexion, requeteDeVue } from "../../src/db/base.ts";
import { SECRET_SENTINELLE, contrat, envMinimal, sautBaseJetable } from "../aide.ts";
import { creerBaseJetable } from "./base-jetable.ts";
import type { BaseJetable } from "./base-jetable.ts";

const vue = contrat.views[0];
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

function configurationJetable() {
  assert.ok(base !== null, "the throwaway database was not created");
  return base.configuration();
}

test("the connection parameters carry a statement timeout", () => {
  const parametres = parametresConnexion(chargerConfiguration(envMinimal()));
  assert.equal(parametres.statement_timeout, DELAI_REQUETE_MS);
  assert.ok(DELAI_REQUETE_MS > 0 && DELAI_REQUETE_MS <= 30000);
});

test("the connection parameters carry the view-limited role and the secret from the configuration", () => {
  const config = chargerConfiguration(envMinimal({ DBTEST_PORT: "55432" }));
  const parametres = parametresConnexion(config);
  assert.equal(parametres.user, "pmzilla_mothra_views");
  assert.equal(parametres.port, 55432);
  assert.equal(parametres.host, "127.0.0.1");
  assert.equal(typeof parametres.password, "function");
  assert.equal((parametres.password as () => string)(), SECRET_SENTINELLE);
  assert.ok(!JSON.stringify(parametres).includes(SECRET_SENTINELLE));
});

test("no setting names another role: the role is not configurable", () => {
  const config = chargerConfiguration(envMinimal({ MOTHRA_DB_USER: "postgres", PGUSER: "postgres", PMZILLA_LAB_DB_URL: "postgres://postgres@x/y" }));
  assert.equal(config.base.utilisateur, "pmzilla_mothra_views");
});

test("the query of a view names the contract's columns and view only, quoted, schema-qualified", () => {
  assert.equal(
    requeteDeVue(vue),
    'SELECT "team", "type", "status_category", "status", "tickets" FROM "flow"."v_team_status" ORDER BY "team", "type", "status_category", "status"',
  );
});

test("an identifier outside the strict pattern is refused, never put in a query", () => {
  assert.throws(() => requeteDeVue({ ...vue, name: 'v"; DROP TABLE flow.issues; --' }));
  assert.throws(() => requeteDeVue({ ...vue, plainColumns: ["a b"] }));
});

test("a database that refuses the connection answers a failure without detail", async () => {
  const config = chargerConfiguration(envMinimal({ DBTEST_PORT: "1" }));
  const acces = creerAccesPostgres(config);
  await assert.rejects(acces.lireVue(vue), (erreur: Error) => erreur.name === "BaseIndisponible" && !erreur.message.includes(SECRET_SENTINELLE));
  await acces.fermer();
});

test("on the throwaway database, a query of the ticket table is refused for insufficient privilege", { skip: saut }, async () => {
  const config = configurationJetable();
  const client = new pg.Client(parametresConnexion(config));
  await client.connect();
  try {
    await assert.rejects(client.query("SELECT 1 FROM flow.issues LIMIT 1"), (erreur: { code?: string }) => erreur.code === "42501");
    const resultat = await client.query("SELECT current_user AS role");
    assert.equal((resultat.rows[0] as { role: string }).role, "pmzilla_mothra_views");
  } finally {
    await client.end();
  }
});

test("on the throwaway database, the view is read under the role", { skip: saut }, async () => {
  const acces = creerAccesPostgres(configurationJetable());
  try {
    const lignes = await acces.lireVue(vue);
    assert.ok(Array.isArray(lignes));
    assert.ok(lignes.length > 0, "the synthetic dataset populates the view");
  } finally {
    await acces.fermer();
  }
});
