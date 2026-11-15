// Task 2.2: the workspace holds its three packages, engines follow the version file, installs are strict and exact.
// The Node version is read from .node-version, never written here.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const lire = (relatif: string): string => readFileSync(new URL(`../${relatif}`, import.meta.url), "utf8");
const racine = JSON.parse(lire("package.json"));

test("the workspace root is private and lists the three packages", () => {
  assert.equal(racine.private, true);
  assert.deepEqual(racine.workspaces, ["contract", "server", "front"]);
});

test("engines.node equals the version file and engines.npm is an exact version", () => {
  assert.equal(racine.engines.node, lire(".node-version").trim());
  assert.match(racine.engines.npm, /^\d+\.\d+\.\d+$/);
});

test("npm refuses another Node and saves exact versions", () => {
  const lignes = lire(".npmrc").split("\n").map((l) => l.trim());
  assert.ok(lignes.includes("engine-strict=true"));
  assert.ok(lignes.includes("save-exact=true"));
});

test("the root test script runs the root tests and every package's tests, without installing", () => {
  assert.match(racine.scripts.test, /node --test/);
  assert.match(racine.scripts.test, /--workspaces/);
  assert.equal(racine.packageManager, undefined);
});
