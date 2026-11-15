// Task 16.1 (design D17, ADR 0006): the server opens two connections, the flow view-limited role for the views only and the storage role
// for the schema `mothra` only, each with its own secret. No database is needed here; the cases that need the throwaway database are in
// test/db/stockage.test.ts (skipped without DBTEST_PORT).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { chargerConfiguration } from "../src/config/index.ts";
import { creerAccesStockage, parametresStockage } from "../src/db/stockage.ts";
import { parametresConnexion } from "../src/db/base.ts";
import { SECRET_SENTINELLE, SECRET_STOCKAGE_SENTINELLE, envMinimal } from "./aide.ts";

const source = (relatif: string): string => readFileSync(new URL(`../src/${relatif}`, import.meta.url), "utf8");

test("the storage connection parameters carry the storage role, the secret as a function, and no view role", () => {
  const config = chargerConfiguration(envMinimal({ DBTEST_PORT: "55432" }));
  const parametres = parametresStockage(config);
  assert.equal(parametres.user, "pmzilla_mothra");
  assert.equal(parametres.port, 55432);
  assert.equal(parametres.host, "127.0.0.1");
  assert.equal(typeof parametres.password, "function");
  assert.equal((parametres.password as () => string)(), SECRET_STOCKAGE_SENTINELLE);
  assert.ok(!JSON.stringify(parametres).includes(SECRET_STOCKAGE_SENTINELLE));
  assert.ok(!JSON.stringify(parametres).includes(SECRET_SENTINELLE));
});

test("the storage connection is limited to the schema mothra by its search path and carries a statement timeout", () => {
  const parametres = parametresStockage(chargerConfiguration(envMinimal()));
  assert.equal(parametres.options, "-c search_path=mothra");
  assert.ok(typeof parametres.statement_timeout === "number" && parametres.statement_timeout > 0 && parametres.statement_timeout <= 30000);
});

test("the two connections never share a role nor a secret", () => {
  const config = chargerConfiguration(envMinimal());
  const vues = parametresConnexion(config);
  const stockage = parametresStockage(config);
  assert.notEqual(vues.user, stockage.user);
  assert.notEqual((vues.password as () => string)(), (stockage.password as () => string)());
  assert.equal(vues.options, undefined, "the view connection has no search path of mothra");
});

test("the view access never names the schema mothra nor the storage role, and the storage access names no flow or quality object", () => {
  const vues = source("db/base.ts");
  assert.ok(!/mothra\./i.test(vues.replace(/@mothra\/contract/g, "")) && !vues.includes("pmzilla_mothra"));
  const stockage = source("db/stockage.ts");
  assert.ok(!/\b(flow|quality|cases|knowledge)\./.test(stockage) && !stockage.includes("pmzilla_flow"));
  assert.ok(!stockage.includes("process.env"), "only the configuration module reads the environment");
});

test("an unreachable database gives a failure without detail and without the secret", async () => {
  const acces = creerAccesStockage(chargerConfiguration(envMinimal({ DBTEST_PORT: "1" })));
  await assert.rejects(acces.roleCourant(), (erreur: Error) => erreur.name === "BaseIndisponible" && !erreur.message.includes(SECRET_STOCKAGE_SENTINELLE));
  await acces.fermer();
});
