// The tests with a database share the view role of the throwaway server (password, LOGIN, CREATE ROLE of the migrations): their files must
// run one after the other, and the tests without a database first.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const paquet = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("the test script runs the files of test/db/ with --test-concurrency=1, after the tests without a database", () => {
  const commandes: string[] = String(paquet.scripts.test).split("&&").map((c) => c.trim());
  const avecBase = commandes.filter((c) => c.includes("test/db/"));
  assert.equal(avecBase.length, 1);
  assert.match(avecBase[0], /--test-concurrency=1/);
  assert.ok(!commandes.some((c) => c.includes("test/*.test.ts") && c.includes("test/db/")));
  assert.ok(commandes.findIndex((c) => c.includes("test/*.test.ts")) < commandes.indexOf(avecBase[0]));
});
