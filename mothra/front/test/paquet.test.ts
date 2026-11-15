import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const paquet = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("the front package is private and named after its folder", () => {
  assert.equal(paquet.name, "@mothra/front");
  assert.equal(paquet.private, true);
});
