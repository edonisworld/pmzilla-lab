// Task 18.3: the distinctive-name filter and the reader of the team-names extract, on the shared parity cases (invented labels), also
// played against tools/sensitive_names.py by tests/sensitive_names/test_parite_texte.py.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { estDistinctif, nomsDistinctifsDeLExtrait } from "../src/noms.ts";
import { lireNoms } from "../src/texte.ts";

const cas = JSON.parse(readFileSync(new URL("../test-data/cas-noms.json", import.meta.url), "utf8")) as {
  distinctive: Array<{ label: string; expected: boolean }>;
  extract: { text: string; generic: string; expected: string[] };
  parse: Array<{ name: string; text: string; expected: string[] }>;
  extracts: Array<{ name: string; text: string; generic: string; expected: string[] }>;
};

test("a list is cut and trimmed as Python's parse_names does, on the shared cases (CRLF, lone CR, byte-order marks, no-break spaces)", () => {
  assert.ok(cas.parse.length > 0);
  for (const c of cas.parse) {
    assert.deepEqual(lireNoms(c.text), c.expected, c.name);
  }
});

test("the extract reader gives the Python result on the shared cases (CRLF, lone CR, byte-order mark, case folding of the generic list)", () => {
  assert.ok(cas.extracts.length > 0);
  for (const c of cas.extracts) {
    assert.deepEqual(nomsDistinctifsDeLExtrait(c.text, c.generic), c.expected, c.name);
  }
});

test("the distinctive filter gives the same answers as the Python rule on the shared cases", () => {
  for (const c of cas.distinctive) {
    assert.equal(estDistinctif(c.label), c.expected, c.label);
  }
});

test("the extract gives its distinctive names, once each, minus the generic list, from the two sections only", () => {
  assert.deepEqual(nomsDistinctifsDeLExtrait(cas.extract.text, cas.extract.generic), cas.extract.expected);
});

test("an extract without name gives an empty list", () => {
  assert.deepEqual(nomsDistinctifsDeLExtrait("referential_teams:\n", ""), []);
});
