// Task 4.4: the synthetic parity cases of design D4, played by the npm player; it fails on the first differing case and names it.
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { chargerContrat } from "../src/chargeur.ts";
import { type CasParite, chargerCasParite, jouerCasParite } from "../src/parite.ts";

const RACINE = new URL("../../../contrats/", import.meta.url);
const CONTRAT = chargerContrat(new URL("vues.json", RACINE));

function copie(): CasParite {
  return structuredClone(chargerCasParite(new URL("cas-parite.json", RACINE)));
}

function nomDeLEchec(cas: CasParite): string | undefined {
  try {
    jouerCasParite(cas, CONTRAT);
    return undefined;
  } catch (erreur) {
    return (erreur as Error).message;
  }
}

test("the parity file holds the three kinds of cases of design D4, each with a unique name", () => {
  const cas = chargerCasParite(new URL("cas-parite.json", RACINE));
  assert.ok(cas.cells.length > 0 && cas.views.length > 0 && cas.thresholds.length > 0);
  const noms = [...cas.cells, ...cas.views, ...cas.thresholds].map((c) => c.name);
  assert.equal(new Set(noms).size, noms.length);
});

test("the view cases cover a table name, a schema-qualified name, another case, an injection text and an empty name", () => {
  const vues = chargerCasParite(new URL("cas-parite.json", RACINE)).views.map((c) => c.view);
  for (const attendu of ["issues", "flow.v_team_status", "V_TEAM_STATUS", "v_team_status; DROP TABLE flow.issues", ""]) {
    assert.ok(vues.includes(attendu), attendu);
  }
});

test("every case of the shared file gives its expected result", () => {
  assert.equal(nomDeLEchec(copie()), undefined);
});

test("the player fails on the first differing cell case and names it", () => {
  const cas = copie();
  cas.cells[2].expected = { state: "value", value: 4 };
  cas.cells[3].expected = { state: "value", value: 3 };
  assert.equal(nomDeLEchec(cas), `cas de parité différent : ${cas.cells[2].name}`);
});

test("the player fails on a view case and on a threshold case, naming them", () => {
  const vue = copie();
  vue.views[1].accepted = true;
  assert.equal(nomDeLEchec(vue), `cas de parité différent : ${vue.views[1].name}`);
  const seuil = copie();
  seuil.thresholds[8].expected = { threshold: 3 };
  assert.equal(nomDeLEchec(seuil), `cas de parité différent : ${seuil.thresholds[8].name}`);
});

test("a server that masks a column the contract does not list as a count column differs, naming the case", () => {
  const cas = copie();
  const cible = cas.cells.find((c) => c.column === "team");
  assert.ok(cible);
  cible.expected = { state: "masked", threshold: 5 };
  assert.equal(nomDeLEchec(cas), `cas de parité différent : ${cible.name}`);
});

test("an error raised while a case is played is caught and the case is named", () => {
  const cellule = copie();
  const compte = cellule.cells.find((c) => c.column === "tickets");
  assert.ok(compte);
  compte.value = 2.5; // not a count: the cell builder throws a TypeError
  assert.equal(nomDeLEchec(cellule), `cas de parité différent : ${compte.name}`);
  const seuil = copie();
  const autre = seuil.cells.find((c) => c.column === "tickets");
  assert.ok(autre);
  autre.threshold = "abc" as unknown as number; // not an integer: the cell builder throws a TypeError
  assert.equal(nomDeLEchec(seuil), `cas de parité différent : ${autre.name}`);
});

test("a parity file without the expected arrays is refused at loading, naming the key", () => {
  const dossier = mkdtempSync(join(tmpdir(), "parite-"));
  try {
    const ecrire = (nom: string, contenu: unknown): string => {
      const chemin = join(dossier, nom);
      writeFileSync(chemin, JSON.stringify(contenu));
      return chemin;
    };
    assert.throws(() => chargerCasParite(ecrire("tableau.json", [])), /objet attendu/);
    assert.throws(() => chargerCasParite(ecrire("nul.json", null)), /objet attendu/);
    assert.throws(() => chargerCasParite(ecrire("sans-cells.json", { views: [], thresholds: [] })), /tableau attendu pour cells/);
    assert.throws(() => chargerCasParite(ecrire("views.json", { cells: [], views: {}, thresholds: [] })), /tableau attendu pour views/);
    assert.throws(() => chargerCasParite(ecrire("seuils.json", { cells: [], views: [], thresholds: "x" })), /tableau attendu pour thresholds/);
    assert.deepEqual(chargerCasParite(ecrire("ok.json", { cells: [], views: [], thresholds: [] })), { cells: [], views: [], thresholds: [] });
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

test("a case on a column the contract does not know fails, naming it", () => {
  const cas = copie();
  cas.cells[0].column = "inconnue";
  assert.equal(nomDeLEchec(cas), `cas de parité différent : ${cas.cells[0].name}`);
});
