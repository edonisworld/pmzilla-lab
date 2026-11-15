// The helper refuses before any connection: every refused environment leaves the client factory untouched. Needs no database, but it
// imports the helper, so the runner of group 3 counts it with the database tests (the pure rule is tested in ../garde-base-jetable.test.ts).
import assert from "node:assert/strict";
import { test } from "node:test";

import type { Environnement } from "../../src/config/index.ts";
import { RefusBaseJetable, creerBaseJetable } from "./base-jetable.ts";

const MOT_DE_PASSE_SENTINELLE = "mot-de-passe-sentinelle";   // fictive value held in a constant: the secret scanner refuses a literal assigned to a lab variable
const base: Environnement = { DBTEST_PORT: "55432", PMZILLA_LAB_DB_PORT: "55432", PMZILLA_LAB_DB_PASSWORD: MOT_DE_PASSE_SENTINELLE };

test("a refused environment opens no connection at all", async () => {
  const cas: Environnement[] = [
    { ...base, DBTEST_PORT: "5432", PMZILLA_LAB_DB_PORT: "5432" },
    { ...base, PMZILLA_LAB_DB_PORT: "6000" },
    { ...base, DBTEST_PORT: "05432" },
    { ...base, MOTHRA_DB_HOST: "db.example.invalid" },
    { ...base, PMZILLA_LAB_DB_PASSWORD: "" },
  ];
  for (const env of cas) {
    let appels = 0;
    const creerClient = () => {
      appels += 1;
      throw new Error("no client should be created");
    };
    await assert.rejects(creerBaseJetable(env, creerClient), (erreur: unknown) => erreur instanceof RefusBaseJetable);
    assert.equal(appels, 0);
  }
});
