// Lot 3c of mothra-demo-habillage, task 7.2: the catalogue of task 5.5 holds the hypothesis 5 sheet pages, one per display state, and the stability
// table in each of its states of D17, on answers from `corpsDepuisVues` (test/fiches-h5.ts). Temporary folders are made by the tests; here the page
// is generated in memory.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { POSITIONS_DEBIT } from "@mothra/contract/listes-fiche";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { genererCatalogue } from "../scripts/catalogue.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { CAS_H5 } from "./fiches-h5.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const SOURCE = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
const PAGE = genererCatalogue(SOURCE, "");

// The part of the page between the heading of a section and the next one.
function section(titre: string): string {
  const debut = PAGE.indexOf(`<h2>${titre}</h2>`);
  assert.ok(debut >= 0, `section absente : ${titre}`);
  const fin = PAGE.indexOf('<section class="catalogue-section">', debut);
  return PAGE.slice(debut, fin < 0 ? undefined : fin);
}

function specimen(titre: string): string {
  const debut = PAGE.indexOf(`<figcaption>${titre}</figcaption>`);
  assert.ok(debut >= 0, `spécimen absent : ${titre}`);
  return PAGE.slice(debut, PAGE.indexOf("</figure>", debut));
}

test("the page holds the stability table in each state of D17: values, a masked and an insufficient measure, every position code, a missing position, the judged quarter marked or not", () => {
  const html = section("Stability table (hypothesis 5)");
  assert.ok(html.includes('data-tableau="stabilite"'));
  for (const titre of [
    "stability table, values, every position within the band, judged quarter marked",
    "stability table, values (French)",
    "stability table, judged throughput under the floor",
    "stability table, judged throughput under the low floor",
    "stability table, judged throughput masked",
    "stability table, judged P85 an insufficient sample",
    "stability table, judged P85 masked",
    "stability table, a missing position (fallback sentence)",
    "stability table, P85 not given (empty cells)",
    "stability table, no quarter marked",
  ]) {
    assert.ok(html.includes(`<figcaption>${titre}</figcaption>`), `spécimen absent : ${titre}`);
  }
  // Every position code of the contract's list, and the fallback of a missing one.
  for (const code of [...POSITIONS_DEBIT, "unknown"]) assert.ok(html.includes(`data-position="${code}"`), `position absente : ${code}`);
  for (const code of POSITIONS_DEBIT) assert.ok(html.includes(catalogues.en[`fiche.position.${code}`]), code);
  assert.ok(html.includes(catalogues.en["fiche.position.unknown"]));
  assert.ok(html.includes(catalogues.fr["conviction.h5.table.title"]) && html.includes(catalogues.en["conviction.h5.table.title"]));
  // The states of a measure: a value, the masked cell, the insufficient sample, the empty cell of a P85 not given.
  for (const marque of ['class="cellule cellule-valeur" data-state="value"', 'class="cellule cellule-masquee" data-state="masked"', 'class="cellule cellule-insuffisante" data-state="insufficient_sample"', 'class="cellule cellule-vide" data-state="empty"']) {
    assert.ok(html.includes(marque), marque);
  }
  // The judged quarter is marked in the specimens that give it and in none of the one that does not.
  assert.ok(specimen("stability table, values, every position within the band, judged quarter marked").includes('aria-current="true"'));
  assert.ok(!specimen("stability table, no quarter marked").includes("aria-current"));
  // The table draws no bar and no waiting.
  assert.doesNotMatch(html, /barre-parts|<svg|data-marqueur|class="composition/);
});

test("the page holds the hypothesis 5 sheet pages, one per display state and per case, on the complete and the reduced answer", () => {
  const html = section("Sheet pages computed by the contract (hypothesis 5)");
  for (const cas of CAS_H5) {
    for (const forme of ["synthetic dataset", "real data, reduced form"]) assert.ok(html.includes(`<figcaption>sheet page h5 ${cas}, ${forme}</figcaption>`), `page de fiche absente : ${cas}, ${forme}`);
  }
  for (const titre of [
    "sheet page h5 confirmed, published, real data, reduced form (French)",
    "sheet page h5 throughput_masked, synthetic dataset (French)",
    "sheet page h5 draft without effect nor cause",
    "sheet page h5 reviewed",
  ]) {
    assert.ok(html.includes(`<figcaption>${titre}</figcaption>`), `spécimen absent : ${titre}`);
  }
  // Each display state is drawn: the badge and the outline of the card.
  for (const etat of ["confirmed", "refuted", "not_settled", "insufficient_sample", "masked"]) {
    assert.ok(html.includes(`carte-preuve" data-etat="${etat}"`), `état absent : ${etat}`);
  }
  // The pages are the component's rendering of contract answers: the statement of hypothesis 5, the stability table, the band and the floors.
  assert.ok(html.includes(catalogues.en["conviction.statement.lead_cycle_h5"]) || html.includes(catalogues.en["conviction.statement.lead_cycle_h5"].replaceAll("'", "&#x27;")));
  assert.ok(html.includes('class="gabarit-fiche"') && html.includes('data-tableau="stabilite"') && html.includes('data-seuil-h5="band"') && html.includes('data-seuil-h5="floor"'));
  // The reason of a masked throughput is told under its badge; the published sheet is one pill with a lock.
  assert.ok(html.includes('data-raison="throughput_masked"') && html.includes(catalogues.en["fiche.reason.throughput_masked"]));
  assert.ok(html.includes('class="statut-fiche statut-publiee"') && html.includes('data-icone="lock"'));
  // No count, no name of the invented team, no waiting on any of these pages.
  assert.doesNotMatch(html, /Equipe Temoin Zeta|7919/);
  assert.doesNotMatch(html, /barre-parts|data-barre|data-marqueur|class="composition|cache-visuel|part-attente|part-travail|data-chiffre="(wait|work)"/);
});

test("the sheet pages of hypothesis 5 hold none of the labels D13 marks hypothesis 1 only", () => {
  const html = section("Sheet pages computed by the contract (hypothesis 5)");
  for (const cle of ["conviction.bar.title", "conviction.notComparable", "conviction.chart.title", "conviction.footer.waitDefinition", "conviction.footer.cycleScope"]) {
    for (const langue of ["en", "fr"] as const) assert.ok(!html.includes(catalogues[langue][cle]), `${cle} ${langue}`);
  }
});
