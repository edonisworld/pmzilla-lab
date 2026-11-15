// Task 16.2 (author's decision of 2026-10-28, design D17): the uniqueness test of the start codes. Each start refusal phrase of D7 and D17
// maps to one exit code only; DATASET_MISMATCH maps to 4 with the other environment checks; SETTING_MISSING and SETTING_INVALID, the dataset
// setting included, map to 5. The expected table is written here from D7 and D17, independently of the code under test.
import assert from "node:assert/strict";
import { test } from "node:test";

import { CODES_DE_SORTIE, RefusDemarrage, SORTIE_CONFIGURATION, SORTIE_CONTRAT, SORTIE_ENVIRONNEMENT, codeDeSortie } from "../src/refus.ts";
import type { CodeRefus } from "../src/refus.ts";

const ATTENDU: Record<CodeRefus, number> = {
  CONTRACT_MISSING: 3,
  CONTRACT_INVALID: 3,
  CONTRACT_FLOOR: 3,
  NOT_LOOPBACK: 4,
  SESSION_WITHOUT_THROWAWAY_DB: 4,
  DATASET_MISMATCH: 4,
  SECRET_MISSING: 5,
  SETTING_MISSING: 5,
  SETTING_INVALID: 5,
};

test("the closed list of start refusals is the one of D7 and D17, nothing more, nothing less", () => {
  assert.deepEqual(Object.keys(CODES_DE_SORTIE).sort(), Object.keys(ATTENDU).sort());
});

test("each start refusal phrase maps to one exit code only, the expected one", () => {
  for (const [code, sortie] of Object.entries(ATTENDU)) {
    const refus = new RefusDemarrage(code as CodeRefus, code.startsWith("SETTING") || code.startsWith("SECRET") ? "MOTHRA_X" : undefined);
    assert.equal(refus.sortie, sortie, code);
    assert.equal(codeDeSortie(code as CodeRefus), sortie, code);
    assert.equal(CODES_DE_SORTIE[code as CodeRefus], sortie, code);
    // The phrase holds its own code and no other one.
    const autres = Object.keys(ATTENDU).filter((autre) => autre !== code && refus.phrase.includes(`(${autre})`));
    assert.deepEqual(autres, [], code);
    assert.ok(refus.phrase.startsWith(`mothra: refused (${code})`), code);
  }
});

test("DATASET_MISMATCH is an environment check (4), the setting codes are configuration (5), and the families are distinct", () => {
  assert.equal(codeDeSortie("DATASET_MISMATCH"), SORTIE_ENVIRONNEMENT);
  assert.equal(codeDeSortie("DATASET_MISMATCH"), codeDeSortie("NOT_LOOPBACK"));
  assert.equal(codeDeSortie("DATASET_MISMATCH"), codeDeSortie("SESSION_WITHOUT_THROWAWAY_DB"));
  for (const code of ["SETTING_MISSING", "SETTING_INVALID", "SECRET_MISSING"] as const) {
    assert.equal(codeDeSortie(code), SORTIE_CONFIGURATION);
  }
  assert.equal(new Set([SORTIE_CONTRAT, SORTIE_ENVIRONNEMENT, SORTIE_CONFIGURATION]).size, 3);
});

test("the refusal of the dataset names neither the database nor a value", () => {
  assert.equal(new RefusDemarrage("DATASET_MISMATCH").phrase, "mothra: refused (DATASET_MISMATCH)");
});
