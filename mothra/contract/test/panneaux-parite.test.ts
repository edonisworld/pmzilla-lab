// Task 37.1, contract part: parity cases of the panel functions in their own file, played as data. The masking of the rows of
// `v_team_flow_inout` (task 36.1) is NOT played here: it is played in flux-inout-masquage.test.ts (primary rule and rule D3 of the product
// row, TypeScript cases; the shared cases of contrats/ come with 36.1). The cases below start from already masked cells (the output of the
// masking function, PRECONDITION of `totalDePlage`).
import assert from "node:assert/strict";
import { test } from "node:test";

import { cellule } from "../src/cellule.ts";
import { verifierFiltres } from "../src/filtres.ts";
import { partDeDebitEnCorrection, panneauStoriesInout } from "../src/panneaux.ts";
import type { EntreeFlux } from "../src/panneaux.ts";

const OPT = { today: "2026-11-19" };
const c = (n: number | null) => cellule(n, 5);

const CAS_PART: Array<{ nom: string; defauts: number | null; histoires: number | null; attendu: unknown }> = [
  { nom: "both visible", defauts: 5, histoires: 15, attendu: { state: "value", value: 25 } },
  { nom: "defect term masked", defauts: null, histoires: 15, attendu: { state: "masked", threshold: 5 } },
  { nom: "story term masked", defauts: 5, histoires: null, attendu: { state: "masked", threshold: 5 } },
  { nom: "both masked", defauts: null, histoires: null, attendu: { state: "masked", threshold: 5 } },
  { nom: "equal terms", defauts: 12, histoires: 12, attendu: { state: "value", value: 50 } },
];

for (const cas of CAS_PART) {
  test(`share in correction: ${cas.nom}`, () => {
    assert.deepEqual(partDeDebitEnCorrection(c(cas.defauts), c(cas.histoires)), cas.attendu);
  });
}

const CAS_TOTAL: Array<{ nom: string; crees: Array<number | null>; attendu: unknown }> = [
  // R-20261114-49, by hand: three visible quarters 5 + 6 + 7 = 18 (before: four, 5 + 6 + 7 + 8 = 26)
  { nom: "three visible quarters", crees: [5, 6, 7], attendu: { state: "value", value: 18 } },
  { nom: "one masked quarter", crees: [5, null, 7], attendu: { state: "masked", threshold: 5 } },
  { nom: "all masked", crees: [null, null, null], attendu: { state: "masked", threshold: 5 } },
];

for (const cas of CAS_TOTAL) {
  test(`range total of created stories: ${cas.nom}`, () => {
    const f = verifierFiltres({ from: "2026-Q1", to: "2026-Q3" }, OPT);
    if (!f.ok) throw new Error("filtres");
    const lignes: EntreeFlux[] = ["2026-Q1", "2026-Q2", "2026-Q3"].map((q, i) => ({
      quarter: q,
      group: "story",
      created: c(cas.crees[i]),
      done: c(9),
    }));
    assert.deepEqual(panneauStoriesInout(lignes, f, OPT.today, 5).total.created, cas.attendu);
  });
}
