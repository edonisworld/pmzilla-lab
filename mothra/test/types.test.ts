// The type check (outils/types.mjs) fails with the "types : " prefix on a type error, and passes on clean code.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const SCRIPT = join(import.meta.dirname, "..", "outils", "types.mjs");

function verifier(source: string) {
  const dossier = mkdtempSync(join(tmpdir(), "mothra-types-"));
  try {
    writeFileSync(join(dossier, "tsconfig.json"), JSON.stringify({ compilerOptions: { strict: true, noEmit: true, types: [] }, include: ["a.ts"] }));
    writeFileSync(join(dossier, "a.ts"), source);
    return spawnSync(process.execPath, [SCRIPT, dossier], { encoding: "utf8" });
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
}

test("a type error fails the check, every line prefixed", () => {
  const r = verifier('export const x: number = "a";\n');
  assert.notEqual(r.status, 0);
  const lignes = r.stdout.trimEnd().split("\n");
  assert.ok(lignes.length >= 2);
  assert.ok(lignes.every((l) => l.startsWith("types : ")));
  assert.match(r.stdout, /TS2322/);
});

test("a missing typescript fails with a named message", () => {
  const dossier = mkdtempSync(join(tmpdir(), "mothra-types-"));
  try {
    const r = spawnSync(process.execPath, [SCRIPT], { encoding: "utf8", env: { ...process.env, MOTHRA_TYPES_RACINE: dossier } });
    assert.equal(r.status, 1);
    assert.equal(r.stdout.trimEnd(), "types : typescript absent, lancer npm ci");
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

test("clean code passes the check", () => {
  const r = verifier("export const x: number = 1;\n");
  assert.equal(r.status, 0);
  assert.match(r.stdout, /^types : /);
});
