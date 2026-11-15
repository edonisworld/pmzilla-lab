import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const paquet = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("the server package is private and named after its folder", () => {
  assert.equal(paquet.name, "@mothra/server");
  assert.equal(paquet.private, true);
});
