// Task 17.2 (decision F10): the coverage floor script fails under the floor naming the package, passes on an up-to-date floor.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const SCRIPT = join(import.meta.dirname, "..", "outils", "couverture.mjs");
const PLANCHERS_REELS = join(import.meta.dirname, "..", "outils", "planchers-couverture.json");

// A fixture package: one branch of two is reached by its only test.
function lancer(
  paquet: string,
  plancher: Record<string, unknown>,
  options: { test?: string; extraEnv?: NodeJS.ProcessEnv } = {},
) {
  const dossier = mkdtempSync(join(tmpdir(), "mothra-couverture-"));
  try {
    mkdirSync(join(dossier, "src"));
    mkdirSync(join(dossier, "test"));
    writeFileSync(join(dossier, "src", "a.mjs"), "export function f(x) {\n  if (x) {\n    return 1;\n  }\n  return 2;\n}\n");
    writeFileSync(
      join(dossier, "test", "a.test.mjs"),
      options.test ??
        'import assert from "node:assert/strict";\nimport { test } from "node:test";\nimport { f } from "../src/a.mjs";\ntest("f", () => {\n  assert.equal(f(true), 1);\n});\n',
    );
    const fichier = join(dossier, "planchers.json");
    writeFileSync(fichier, JSON.stringify({ paquets: { fictif: { include: ["src/*.mjs"], tests: ["test/*.test.mjs"], ...plancher } } }));
    const env: NodeJS.ProcessEnv = { ...process.env, MOTHRA_COUVERTURE_PLANCHERS: fichier, ...options.extraEnv };
    delete env.NODE_TEST_CONTEXT;
    return spawnSync(process.execPath, [SCRIPT, paquet], { encoding: "utf8", cwd: dossier, env });
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
}

test("a fake floor above the measured coverage fails, naming the package", () => {
  const r = lancer("fictif", { lignes: 100, branches: 100 });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /plancher de couverture non atteint : fictif/);
});

test("a branch floor alone above the measured coverage fails too", () => {
  const r = lancer("fictif", { lignes: 0, branches: 100 });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /plancher de couverture non atteint : fictif/);
});

test("an up-to-date floor passes", () => {
  const r = lancer("fictif", { lignes: 50, branches: 25 });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.doesNotMatch(r.stdout, /plancher de couverture non atteint/);
});

test("a provisional floor passes and says so", () => {
  const r = lancer("fictif", { lignes: 100, branches: 100, provisoire: true });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /plancher provisoire non mesuré : fictif/);
});

test("an unknown package is a named failure", () => {
  const r = lancer("absent", { lignes: 0, branches: 0 });
  assert.equal(r.status, 2);
  assert.match(r.stdout, /paquet inconnu : absent/);
});

const TEST_EN_ECHEC =
  'import assert from "node:assert/strict";\nimport { test } from "node:test";\nimport { f } from "../src/a.mjs";\ntest("f", () => {\n  assert.equal(f(true), 99);\n});\n';

test("a failing test takes precedence over the floor and is named", () => {
  const r = lancer("fictif", { lignes: 0, branches: 0 }, { test: TEST_EN_ECHEC });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /tests en échec : fictif/);
});

test("a failing test that is also under the floor reports both", () => {
  const r = lancer("fictif", { lignes: 100, branches: 100 }, { test: TEST_EN_ECHEC });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /tests en échec : fictif/);
  assert.match(r.stdout, /plancher de couverture non atteint : fictif/);
});

test("a launch failure exits 2 and says so", () => {
  const r = lancer("fictif", { lignes: 0, branches: 0 }, { extraEnv: { MOTHRA_COUVERTURE_NODE: "/inexistant/node" } });
  assert.equal(r.status, 2);
  assert.match(r.stdout, /lancement impossible \(/);
});

test("no file measured is a named failure", () => {
  const r = lancer("fictif", { lignes: 0, branches: 0, include: ["rien/*.mjs"] });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /aucun test ou aucun fichier mesuré : fictif/);
});

test("no test run is a named failure", () => {
  const r = lancer("fictif", { lignes: 0, branches: 0 }, { test: "// no test here\n" });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /aucun test ou aucun fichier mesuré : fictif/);
});

test("every provisional package carries a planned measure and a removal condition", () => {
  const { paquets } = JSON.parse(readFileSync(PLANCHERS_REELS, "utf8"));
  for (const [nom, p] of Object.entries<Record<string, unknown>>(paquets)) {
    if (p.provisoire !== true) continue;
    for (const cle of ["mesure_prevue", "retrait"]) {
      assert.ok(typeof p[cle] === "string" && (p[cle] as string).trim() !== "", `${nom}.${cle}`);
    }
  }
});

test("the contract floors are never lowered (values measured on 2026-11-02)", () => {
  const { paquets } = JSON.parse(readFileSync(PLANCHERS_REELS, "utf8"));
  assert.equal(paquets.contract.provisoire, false);
  assert.ok(paquets.contract.lignes >= 98, "contract.lignes");
  assert.ok(paquets.contract.branches >= 94, "contract.branches");
});

test("the reviewed floors file covers the contract and server packages, with integer floors from 0 to 100", () => {
  const { paquets } = JSON.parse(readFileSync(PLANCHERS_REELS, "utf8"));
  assert.deepEqual(Object.keys(paquets).sort(), ["contract", "server"]);
  for (const [nom, p] of Object.entries<Record<string, unknown>>(paquets)) {
    for (const cle of ["lignes", "branches"]) {
      assert.ok(Number.isInteger(p[cle]) && (p[cle] as number) >= 0 && (p[cle] as number) <= 100, `${nom}.${cle}`);
    }
    assert.ok(Array.isArray(p.include) && p.include.length > 0, `${nom}.include`);
    assert.ok(Array.isArray(p.tests) && p.tests.length > 0, `${nom}.tests`);
  }
});

test("the server package keeps its test script and measures coverage through a separate test:coverage script", () => {
  const { scripts } = JSON.parse(readFileSync(join(import.meta.dirname, "..", "server", "package.json"), "utf8"));
  assert.equal(scripts["test:coverage"], "node ../outils/couverture.mjs server");
  assert.ok(!String(scripts.test).includes("couverture"));
  const { paquets } = JSON.parse(readFileSync(PLANCHERS_REELS, "utf8"));
  // One single run over both globs gives one merged report; the order comes from the patterns of the configuration, one file at a time.
  assert.deepEqual(paquets.server.tests, ["test/*.test.ts", "test/db/*.test.ts"]);
  assert.equal(paquets.server.concurrence, 1);
});

test("the test script of the contract package goes through the floor script", () => {
  const { scripts } = JSON.parse(readFileSync(join(import.meta.dirname, "..", "contract", "package.json"), "utf8"));
  assert.equal(scripts.test, "node ../outils/couverture.mjs contract");
});
