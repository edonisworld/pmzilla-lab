// Task 18.3: the pure check of a written text (design D20, invariant 11 amended): key, e-mail address, names of the two lists, length.
// Lists of invented names held here as test data, never the real files.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { ligneCorrespond, lireNoms, motifsDeNoms, TEXTE_LONGUEUR_MAX, verifierTexteEcrit } from "../src/texte.ts";

const LISTE_SENSIBLE = "# invented\n\n  Zorglub Martin  \nabc\nXYZW\n";
const LISTE_EQUIPES = "Quentin Duval\nQwerty Team\n";
const motifs = motifsDeNoms([...lireNoms(LISTE_SENSIBLE), ...lireNoms(LISTE_EQUIPES)]);

test("a list is read one name per line, comments and empty lines left out", () => {
  assert.deepEqual(lireNoms("﻿# c\n\n  A B  \nC\r\n"), ["A B", "C"]);
});

test("a ticket key is refused with its reason, never its value", () => {
  for (const texte of ["see ABC-123", "ISO-9001 applies", "A1_B-7", "(PROJ-1)"]) {
    const r = verifierTexteEcrit(texte, motifs);
    assert.deepEqual(r, { ok: false, reason: "ticket_key" }, texte);
  }
});

test("a key preceded by a letter and a zero-width space is refused: the raw text keeps the word boundary", () => {
  // Normalised alone, "x" + key would be stuck and pass; the raw text still shows the boundary (audit #629, S3, review point 1).
  assert.deepEqual(verifierTexteEcrit("see x​ABC-123", motifs), { ok: false, reason: "ticket_key" });
});

test("a reference with a space instead of a hyphen is accepted", () => {
  assert.deepEqual(verifierTexteEcrit("compliant with ISO 9001", motifs), { ok: true });
  assert.deepEqual(verifierTexteEcrit("the quarter 2026-3 and q-2", motifs), { ok: true });
});

test("an e-mail address is refused", () => {
  assert.deepEqual(verifierTexteEcrit("write to someone@example.org now", motifs), { ok: false, reason: "email" });
  assert.deepEqual(verifierTexteEcrit("the at sign @ alone, and a@b without a dot", motifs), { ok: true });
});

test("a name of either list is refused, a name stuck to a letter is accepted, a short name keeps its case", () => {
  assert.deepEqual(verifierTexteEcrit("asked Zorglub Martin", motifs), { ok: false, reason: "sensitive_name" });
  assert.deepEqual(verifierTexteEcrit("asked quentin duval", motifs), { ok: false, reason: "sensitive_name" });
  assert.deepEqual(verifierTexteEcrit("asked xZorglub Martin", motifs), { ok: true });
  assert.deepEqual(verifierTexteEcrit("the note abc", motifs), { ok: false, reason: "sensitive_name" });
  assert.deepEqual(verifierTexteEcrit("the note ABC", motifs), { ok: true });
});

test("500 characters are accepted, 501 refused with the count and the maximum, spaces at the ends not counted", () => {
  assert.equal(TEXTE_LONGUEUR_MAX, 500);
  assert.deepEqual(verifierTexteEcrit("a".repeat(500), motifs), { ok: true });
  assert.deepEqual(verifierTexteEcrit(`   ${"a".repeat(500)}   `, motifs), { ok: true });
  assert.deepEqual(verifierTexteEcrit("a".repeat(501), motifs), { ok: false, reason: "too_long", count: 501, max: 500 });
  assert.deepEqual(verifierTexteEcrit(`  ${"a".repeat(501)} `, motifs), { ok: false, reason: "too_long", count: 501, max: 500 });
});

test("the length counts Unicode code points, not UTF-16 units", () => {
  assert.deepEqual(verifierTexteEcrit("\u{1F600}".repeat(500), motifs), { ok: true });
  assert.equal(verifierTexteEcrit("\u{1F600}".repeat(501), motifs).ok, false);
});

test("a refusal holds neither the text nor the matched value", () => {
  const r = JSON.stringify(verifierTexteEcrit("asked Zorglub Martin", motifs));
  assert.equal(r.includes("Zorglub"), false);
});

test("the shared parity cases on invented names (also played against tools/sensitive_names.py)", () => {
  const cas = JSON.parse(readFileSync(new URL("../test-data/cas-texte.json", import.meta.url), "utf8")) as {
    names: string[];
    cases: Array<{ name: string; text: string; matches: boolean }>;
  };
  const m = motifsDeNoms(cas.names);
  for (const c of cas.cases) {
    assert.equal(ligneCorrespond(m, c.text), c.matches, c.name);
  }
});
