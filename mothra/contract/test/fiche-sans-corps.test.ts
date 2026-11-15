// Audit #629, A-66 (R-20261112-30): the answer of a stale draft is the sheet without its body, with the code DATA_DATE_STALE and no other new
// field. The schema is exported by the package index (the server and the tests read it there).
import assert from "node:assert/strict";
import { test } from "node:test";

import Value from "typebox/value";

import { SchemaFicheSansCorps } from "../src/index.ts";

test("a stale sheet: what the author wrote and the code, nothing else (no verdict, no figure, no undeclared field)", () => {
  const valide = { id: "7", state: "draft", managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "fr" }, bodyState: "DATA_DATE_STALE" };
  assert.equal(Value.Check(SchemaFicheSansCorps, valide), true);
  assert.equal(Value.Check(SchemaFicheSansCorps, { id: "7", state: "reviewed", bodyState: "DATA_DATE_STALE" }), true);
  assert.equal(Value.Check(SchemaFicheSansCorps, { ...valide, verdict: "confirmed" }), false, "a body field is refused");
  assert.equal(Value.Check(SchemaFicheSansCorps, { ...valide, bodyState: "OTHER" }), false, "bodyState is the literal");
  assert.equal(Value.Check(SchemaFicheSansCorps, { id: "7", state: "draft" }), false, "bodyState is required");
  assert.equal(Value.Check(SchemaFicheSansCorps, { ...valide, state: "published" }), false, "a published sheet is never stale");
});
