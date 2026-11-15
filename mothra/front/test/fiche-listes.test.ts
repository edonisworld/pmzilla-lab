// Task 19.3 (review of 19.3, non-blocking): the lists of the front equal those of the contract. `satisfies` and `Record<...>` check
// inclusion at compilation; these tests check at run time that no list of the front holds a code the contract lacks (except the
// declared simulated ones) and that every code of the contract has a label in both catalogues.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CODES_LIMITES,
  CODES_SEUILS,
  COLONNES_MESURE,
  EXPLICATIONS_DE_FICHE,
  GRAPHIQUES_DE_FICHE,
  LIENS_DE_FICHE,
  METHODES,
  MOTIFS_DE_FICHE,
  QUESTIONS_DE_DIRECTION,
  VERDICTS_DE_FICHE,
} from "@mothra/contract/listes-fiche";

import { EXPLICATIONS, LIENS, VERDICTS_AFFICHES } from "../src/api/fiche.ts";
import { CLES_QUESTION } from "../src/composants/ChampsFiche.ts";
import { CLES_EXPLICATION, CLES_MOTIF } from "../src/composants/Fiche.ts";
import { CLES_LIEN, CLES_LIMITE, CLES_MESURE, CLES_METHODE, CLES_SEUIL } from "../src/composants/FicheMethode.ts";
import { GRAPHIQUES_FICHE } from "../src/pages/PageTableau.ts";
import { catalogues } from "../src/i18n/langue.ts";

const trie = (l: readonly string[]): string[] => [...l].sort();
const cles = (t: Record<string, string>): string[] => trie(Object.keys(t));

// The codes a table holds beyond the contract's list: none (the simulated codes were removed with the fixture alignment, Q40).
function auxiliaires(table: Record<string, string>, contrat: readonly string[]): string[] {
  return cles(table).filter((c) => !contrat.includes(c));
}

test("the lists the front re-exports are the contract's own", () => {
  assert.deepEqual([...GRAPHIQUES_FICHE], [...GRAPHIQUES_DE_FICHE]);
  assert.deepEqual([...EXPLICATIONS], [...EXPLICATIONS_DE_FICHE]);
  assert.deepEqual([...LIENS], [...LIENS_DE_FICHE]);
  assert.deepEqual([...VERDICTS_AFFICHES], [...VERDICTS_DE_FICHE]);
});

test("the reasons and the links of the front equal the lists of the contract, neither more nor less", () => {
  assert.deepEqual(cles(CLES_MOTIF), trie(MOTIFS_DE_FICHE));
  assert.deepEqual(cles(CLES_LIEN), trie(LIENS_DE_FICHE));
  assert.deepEqual(cles(CLES_QUESTION), trie(QUESTIONS_DE_DIRECTION));
});

test("the explanations of the front are the contract's plus the attachment signal, and nothing else", () => {
  assert.deepEqual(cles(CLES_EXPLICATION), trie([...EXPLICATIONS_DE_FICHE, "tasks_attachment"]));
});

test("the measure, threshold, method and limit tables hold every code of the contract, and no other", () => {
  const seuils = Object.values(CODES_SEUILS).flat();
  for (const [table, contrat] of [
    [CLES_MESURE, COLONNES_MESURE],
    [CLES_SEUIL, seuils],
    [CLES_METHODE, METHODES],
    [CLES_LIMITE, CODES_LIMITES],
  ] as const) {
    for (const code of contrat) assert.ok(Object.hasOwn(table, code), `code du contrat sans libellé : ${code}`);
  }
  assert.deepEqual(auxiliaires(CLES_MESURE, COLONNES_MESURE), []);
  assert.deepEqual(auxiliaires(CLES_SEUIL, seuils), []);
  assert.deepEqual(auxiliaires(CLES_METHODE, METHODES), []);
  assert.deepEqual(auxiliaires(CLES_LIMITE, CODES_LIMITES), []);
});

test("every code of every list has its label in both catalogues", () => {
  const tables = [CLES_MOTIF, CLES_LIEN, CLES_QUESTION, CLES_EXPLICATION, CLES_MESURE, CLES_SEUIL, CLES_METHODE, CLES_LIMITE];
  for (const table of tables) {
    for (const cle of Object.values(table)) {
      assert.ok(cle in catalogues.en && cle in catalogues.fr, `libellé absent : ${cle}`);
    }
  }
});
