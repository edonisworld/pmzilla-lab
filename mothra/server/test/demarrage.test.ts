// Tasks 6.1 and 6.6: the start sequence and its refusals. Order of the checks: contract (exit 3), configuration (exit 5), environment
// (exit 4). A refusal opens no connection and creates no access object.
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { preparer } from "../src/demarrage.ts";
import type { OptionsDemarrage } from "../src/demarrage.ts";
import { RefusDemarrage } from "../src/refus.ts";
import { AccesFictif, CHEMIN_CONTRAT, SECRET_SENTINELLE, envMinimal } from "./aide.ts";

function essai(env: Record<string, string | undefined>, options: Partial<OptionsDemarrage> = {}): { refus: RefusDemarrage | null; acces: number } {
  let acces = 0;
  try {
    preparer(env, {
      cheminContrat: CHEMIN_CONTRAT,
      creerAcces: () => {
        acces += 1;
        return new AccesFictif();
      },
      journal: false,
      avertir: () => {},
      ...options,
    });
  } catch (erreur) {
    assert.ok(erreur instanceof RefusDemarrage, "a start refusal was expected");
    return { refus: erreur, acces };
  }
  return { refus: null, acces };
}

function contratEcrit(texte: string): URL {
  const dossier = mkdtempSync(join(tmpdir(), "mothra-contrat-"));
  const fichier = join(dossier, "vues.json");
  writeFileSync(fichier, texte);
  return new URL(`file://${fichier}`);
}

const VUE = { name: "v_x", schema: "flow", roleKind: "flow", countColumns: ["n"], plainColumns: ["a"] };

test("a valid contract and environment start the server (access created once, nothing listening yet)", () => {
  const { refus, acces } = essai(envMinimal());
  assert.equal(refus, null);
  assert.equal(acces, 1);
});

test("the start creates the storage access once, under the storage role, and none on a refusal (task 16.1)", () => {
  const vus: string[] = [];
  const creerStockage: OptionsDemarrage["creerStockage"] = (config) => {
    vus.push(config.stockage.utilisateur);
    return { roleCourant: async () => "x", fermer: async () => {} };
  };
  assert.equal(essai(envMinimal(), { creerStockage }).refus, null);
  assert.deepEqual(vus, ["pmzilla_mothra"]);
  const sans = envMinimal();
  delete sans.PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA;
  const { refus } = essai(sans, { creerStockage });
  assert.equal(refus?.code, "SECRET_MISSING");
  assert.equal(refus?.variable, "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA");
  assert.deepEqual(vus, ["pmzilla_mothra"], "no storage access on a refusal");
});

test("a missing contract exits 3 with CONTRACT_MISSING, before the configuration and any access", () => {
  const { refus, acces } = essai({}, { cheminContrat: new URL("file:///inexistant/vues.json") });
  assert.equal(refus?.code, "CONTRACT_MISSING");
  assert.equal(refus?.sortie, 3);
  assert.equal(refus?.phrase, "mothra: refused (CONTRACT_MISSING)");
  assert.equal(acces, 0);
});

test("an invalid contract exits 3 with CONTRACT_INVALID", () => {
  const { refus, acces } = essai(envMinimal(), { cheminContrat: contratEcrit("{ pas du json") });
  assert.equal(refus?.code, "CONTRACT_INVALID");
  assert.equal(refus?.sortie, 3);
  assert.equal(acces, 0);
});

test("a contract threshold under the floor exits 3 with CONTRACT_FLOOR", () => {
  const { refus, acces } = essai(envMinimal(), { cheminContrat: contratEcrit(JSON.stringify({ minThreshold: 3, views: [VUE] })) });
  assert.equal(refus?.code, "CONTRACT_FLOOR");
  assert.equal(refus?.sortie, 3);
  assert.equal(acces, 0);
});

test("a contract that names a table is refused, never replaced by a built-in list", () => {
  const table = { ...VUE, name: "issues" };
  const { refus } = essai(envMinimal(), { cheminContrat: contratEcrit(JSON.stringify({ views: [table] })) });
  assert.equal(refus?.code, "CONTRACT_INVALID");
});

test("the contract is checked before the configuration", () => {
  const { refus } = essai({}, { cheminContrat: new URL("file:///inexistant/vues.json") });
  assert.equal(refus?.sortie, 3);
});

test("a configuration refusal exits 5 and creates no access", () => {
  const env = envMinimal();
  delete env.PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS;
  const { refus, acces } = essai(env);
  assert.equal(refus?.code, "SECRET_MISSING");
  assert.equal(refus?.sortie, 5);
  assert.equal(acces, 0);
});

test("an address other than 127.0.0.1 exits 4 with NOT_LOOPBACK, and opens no access", () => {
  for (const hote of ["0.0.0.0", "::", "localhost", "192.168.1.10", "::1"]) {
    const { refus, acces } = essai(envMinimal({ MOTHRA_HOST: hote }));
    assert.equal(refus?.code, "NOT_LOOPBACK", hote);
    assert.equal(refus?.sortie, 4);
    assert.equal(refus?.phrase, "mothra: refused (NOT_LOOPBACK)");
    assert.equal(acces, 0);
  }
});

test("the address 127.0.0.1 is accepted", () => {
  assert.equal(essai(envMinimal({ MOTHRA_HOST: "127.0.0.1" })).refus, null);
});

test("in a Claude Code session without DBTEST_PORT the start is refused, exit 4, no access", () => {
  const { refus, acces } = essai(envMinimal({ CLAUDECODE: "1" }));
  assert.equal(refus?.code, "SESSION_WITHOUT_THROWAWAY_DB");
  assert.equal(refus?.sortie, 4);
  assert.equal(refus?.phrase, "mothra: refused (SESSION_WITHOUT_THROWAWAY_DB)");
  assert.equal(acces, 0);
});

test("in a session with a throwaway port equal to the lab port the start is accepted", () => {
  assert.equal(essai(envMinimal({ CLAUDECODE: "1", DBTEST_PORT: "55432", PMZILLA_LAB_DB_PORT: "55432" })).refus, null);
});

test("in a session with a throwaway port and no lab port the start is accepted", () => {
  const env = envMinimal({ CLAUDECODE: "1", DBTEST_PORT: "55432" });
  delete env.PMZILLA_LAB_DB_PORT;
  assert.equal(essai(env).refus, null);
});

test("in a session with DBTEST_PORT=5432 (the standard port) the start is refused, exit 4, no access", () => {
  for (const labo of ["5432", undefined]) {
    const env = envMinimal({ CLAUDECODE: "1", DBTEST_PORT: "5432", PMZILLA_LAB_DB_PORT: labo });
    const { refus, acces } = essai(env);
    assert.equal(refus?.code, "SESSION_WITHOUT_THROWAWAY_DB", String(labo));
    assert.equal(refus?.sortie, 4);
    assert.equal(acces, 0);
  }
});

test("in a session with a throwaway port different from the lab port the start is refused, exit 4, no access", () => {
  const { refus, acces } = essai(envMinimal({ CLAUDECODE: "1", DBTEST_PORT: "55432", PMZILLA_LAB_DB_PORT: "6000" }));
  assert.equal(refus?.code, "SESSION_WITHOUT_THROWAWAY_DB");
  assert.equal(refus?.sortie, 4);
  assert.equal(refus?.phrase, "mothra: refused (SESSION_WITHOUT_THROWAWAY_DB)");
  assert.equal(acces, 0);
});

test("in a session, a throwaway port that is not strict decimal is refused (configuration refusal, no access)", () => {
  for (const mauvais of ["05432", "0", "+55432", "55432 "]) {
    const { refus, acces } = essai(envMinimal({ CLAUDECODE: "1", DBTEST_PORT: mauvais, PMZILLA_LAB_DB_PORT: mauvais }));
    assert.equal(refus?.code, "SETTING_INVALID", mauvais);
    assert.equal(acces, 0);
  }
});

test("outside a session, without DBTEST_PORT, the start is accepted", () => {
  assert.equal(essai(envMinimal()).refus, null);
});

test("no variable or option waives the session refusal", () => {
  for (const extra of [{ MOTHRA_ALLOW_SESSION: "1" }, { MOTHRA_FORCE: "1" }, { MOTHRA_ALLOW_REAL_DB: "1" }, { DBTEST_PORT: "" }]) {
    const { refus } = essai(envMinimal({ CLAUDECODE: "1", ...extra }));
    assert.equal(refus?.code, "SESSION_WITHOUT_THROWAWAY_DB", JSON.stringify(extra));
  }
});

test("without MOTHRA_DB_NAME the start is refused, exit 5, naming the variable and no default name, no access", () => {
  const env = envMinimal();
  delete env.MOTHRA_DB_NAME;
  const { refus, acces } = essai(env);
  assert.equal(refus?.code, "SETTING_MISSING");
  assert.equal(refus?.sortie, 5);
  assert.equal(refus?.variable, "MOTHRA_DB_NAME");
  assert.equal(refus?.phrase, "mothra: refused (SETTING_MISSING) MOTHRA_DB_NAME");
  assert.equal(acces, 0);
  assert.equal(essai({ ...env, MOTHRA_DB_NAME: "" }).refus?.code, "SETTING_MISSING");
});

test("the database host is the loopback only: 127.0.0.1, ::1 or localhost", () => {
  for (const hote of ["127.0.0.1", "::1", "localhost"]) {
    assert.equal(essai(envMinimal({ MOTHRA_DB_HOST: hote })).refus, null, hote);
  }
});

test("a database host that is not local exits 4 with NOT_LOOPBACK, never echoing the value, and opens no access", () => {
  for (const hote of ["db.example.invalid", "10.0.0.5", "0.0.0.0", "127.0.0.2", "LOCALHOST", "localhost.example.invalid", "::"]) {
    const { refus, acces } = essai(envMinimal({ MOTHRA_DB_HOST: hote }));
    assert.equal(refus?.code, "NOT_LOOPBACK", hote);
    assert.equal(refus?.sortie, 4);
    assert.equal(refus?.phrase, "mothra: refused (NOT_LOOPBACK)");
    assert.ok(!String(refus?.message).includes(hote));
    assert.equal(acces, 0);
  }
});

test("a refusal phrase holds the code and the variable's name, never the secret", () => {
  const env = envMinimal({ MOTHRA_PORT: "x" });
  const { refus } = essai(env);
  assert.ok(refus !== null);
  assert.ok(!refus.phrase.includes(SECRET_SENTINELLE));
});
