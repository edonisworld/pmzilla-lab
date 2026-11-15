// Entry of the server, tested as a process (design D7 exit codes): the real src/main.ts is launched with a fully controlled environment
// (nothing inherited) and only refusals are exercised, so nothing listens and nothing connects. The environment never gives the real
// database port: the port of these runs is a made-up one, and no refusal reaches the database anyway.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { LISTE_EQUIPES_FICTIVE, LISTE_SENSIBLE_FICTIVE, SECRET_SENTINELLE, SECRET_STOCKAGE_SENTINELLE } from "./aide.ts";

const MAIN = fileURLToPath(new URL("../src/main.ts", import.meta.url));
const PORT_FACTICE = "54999";

function lancer(env: Record<string, string>, args: string[] = []): { code: number | null; stdout: string; stderr: string } {
  const resultat = spawnSync(process.execPath, [MAIN, ...args], { env, encoding: "utf8", input: "", timeout: 30000 });
  return { code: resultat.status, stdout: resultat.stdout, stderr: resultat.stderr };
}

function envBase(extra: Record<string, string> = {}): Record<string, string> {
  return {
    MOTHRA_DB_NAME: "mothra_test",
    MOTHRA_DATASET: "synthetic",
    PMZILLA_LAB_DB_PORT: PORT_FACTICE,
    PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS: SECRET_SENTINELLE,
    PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA: SECRET_STOCKAGE_SENTINELLE,
    // The two lists of names (task 18.3): fake lists of invented names held as test data.
    MOTHRA_SENSITIVE_NAMES_FILE: LISTE_SENSIBLE_FICTIVE,
    MOTHRA_TEAM_NAMES_FILE: LISTE_EQUIPES_FICTIVE,
    ...extra,
  };
}

function sansSentinelle(sortie: { stdout: string; stderr: string }): void {
  assert.ok(!sortie.stdout.includes(SECRET_SENTINELLE));
  assert.ok(!sortie.stderr.includes(SECRET_SENTINELLE));
}

test("an extra argument exits 2 with the usage phrase on stderr, before anything else", () => {
  const sortie = lancer(envBase(), ["--port", "1"]);
  assert.equal(sortie.code, 2);
  assert.equal(sortie.stderr, "mothra: usage\n");
  assert.equal(sortie.stdout, "");
  sansSentinelle(sortie);
});

test("a missing secret exits 5, naming the variable and nothing else", () => {
  const env = envBase();
  delete env.PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS;
  const sortie = lancer(env);
  assert.equal(sortie.code, 5);
  assert.equal(sortie.stderr, "mothra: refused (SECRET_MISSING) PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS\n");
  assert.equal(sortie.stdout, "");
});

test("a missing storage secret exits 5, naming its own variable and nothing else (task 16.1)", () => {
  const env = envBase();
  delete env.PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA;
  const sortie = lancer(env);
  assert.equal(sortie.code, 5);
  assert.equal(sortie.stderr, "mothra: refused (SECRET_MISSING) PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA\n");
  assert.equal(sortie.stdout, "");
  sansSentinelle(sortie);
  assert.ok(!sortie.stderr.includes(SECRET_STOCKAGE_SENTINELLE));
});

test("a missing dataset setting exits 5, naming MOTHRA_DATASET; demo exits 5 too, never echoing the value (task 16.2)", () => {
  const env = envBase();
  delete env.MOTHRA_DATASET;
  const absent = lancer(env);
  assert.equal(absent.code, 5);
  assert.equal(absent.stderr, "mothra: refused (SETTING_MISSING) MOTHRA_DATASET\n");
  const demo = lancer(envBase({ MOTHRA_DATASET: "demo" }));
  assert.equal(demo.code, 5);
  assert.equal(demo.stderr, "mothra: refused (SETTING_INVALID) MOTHRA_DATASET\n");
});

test("a missing database name exits 5, naming MOTHRA_DB_NAME: there is no default name", () => {
  const env = envBase();
  delete env.MOTHRA_DB_NAME;
  const sortie = lancer(env);
  assert.equal(sortie.code, 5);
  assert.equal(sortie.stderr, "mothra: refused (SETTING_MISSING) MOTHRA_DB_NAME\n");
  sansSentinelle(sortie);
});

test("a database host that is not local exits 4 with NOT_LOOPBACK, without echoing the value or the secret", () => {
  const hote = "db.example.invalid";
  const sortie = lancer(envBase({ MOTHRA_DB_HOST: hote }));
  assert.equal(sortie.code, 4);
  assert.equal(sortie.stderr, "mothra: refused (NOT_LOOPBACK)\n");
  assert.ok(!sortie.stderr.includes(hote));
  sansSentinelle(sortie);
});

test("a listening address that is not 127.0.0.1 exits 4 with NOT_LOOPBACK", () => {
  const sortie = lancer(envBase({ MOTHRA_HOST: "0.0.0.0" }));
  assert.equal(sortie.code, 4);
  assert.equal(sortie.stderr, "mothra: refused (NOT_LOOPBACK)\n");
  sansSentinelle(sortie);
});

test("in a Claude Code session without a throwaway port the start exits 4", () => {
  const sortie = lancer(envBase({ CLAUDECODE: "1" }));
  assert.equal(sortie.code, 4);
  assert.equal(sortie.stderr, "mothra: refused (SESSION_WITHOUT_THROWAWAY_DB)\n");
  sansSentinelle(sortie);
});
