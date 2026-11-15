// R-20261031-61, Q111: the pooled-year point of a series (`pooled_year`) is shown through a catalogue key ("Pooled year", "Année groupée"),
// as `fiche.measure.atPooledYear` is, never as the raw code. The points come from the contract's functions (reponses-contrat.ts).
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import { TableauLeadCycle } from "../src/composants/TableauLeadCycle.ts";
import { libelleTrimestre } from "../src/composants/trimestre.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { MODE_REEL, reponseComplete, reponseServie, SEUIL } from "./reponses-contrat.ts";
import { rendre } from "./rendu.ts";

const en = catalogues.en;
const fr = catalogues.fr;

test("the table shows the pooled-year point by its catalogue key, in each language, never as the raw code", () => {
  const points = reponseComplete().teams[0].points;
  assert.equal(points.at(-1)?.quarter, "pooled_year");
  const anglais = rendre(h(TableauLeadCycle, { points, seuil: SEUIL }), "en");
  assert.match(anglais, /<td class="cellule">Last three quarters<\/td>/);      // R-20261114-49, design D7: the dashboard names the grouped row « Last three quarters »
  assert.match(anglais, /<td class="cellule">Q3 2026<\/td>/);
  assert.doesNotMatch(anglais, /pooled_year/);
  const francais = rendre(h(TableauLeadCycle, { points, seuil: SEUIL }), "fr");
  assert.match(francais, /<td class="cellule">3 derniers trimestres<\/td>/);
  assert.match(francais, /<td class="cellule">T3 2026<\/td>/);
  assert.doesNotMatch(francais, /pooled_year/);
});

test("the reduced answer of real data shows the pooled-year point the same way", () => {
  const points = reponseServie(MODE_REEL).teams[0].points;
  assert.match(rendre(h(TableauLeadCycle, { points, seuil: SEUIL }), "en"), /<td class="cellule">Last three quarters<\/td>/);
  assert.match(rendre(h(TableauLeadCycle, { points, seuil: SEUIL }), "fr"), /<td class="cellule">3 derniers trimestres<\/td>/);
});

test("the masked pooled year of a team is labelled the same way, its cells stay masked", () => {
  const points = reponseComplete().teams[1].points;
  assert.equal(points.at(-1)?.lead.state, "masked");
  const html = rendre(h(TableauLeadCycle, { points, seuil: SEUIL }), "en");
  assert.match(html, /<td class="cellule">Last three quarters<\/td><td class="[^"]*cellule-masquee/);
});

test("the label comes from the catalogue key tableau.quarter.lastThreeQuarters; the former key stays for the frozen sheets, with its former text", () => {
  assert.equal(en["tableau.quarter.lastThreeQuarters"], "Last three quarters");
  assert.equal(fr["tableau.quarter.lastThreeQuarters"], "3 derniers trimestres");
  assert.equal(en["tableau.quarter.pooledYear"], "Pooled year");
  assert.equal(fr["tableau.quarter.pooledYear"], "Année groupée");
  const formater = (langue: "en" | "fr") => (id: string): string => catalogues[langue][id];
  assert.equal(libelleTrimestre("pooled_year", formater("en")), "Last three quarters");
  assert.equal(libelleTrimestre("pooled_year", formater("fr")), "3 derniers trimestres");
  // a quarter and an unknown label are unchanged
  assert.equal(libelleTrimestre("2026-Q1", (id, v) => catalogues.en[id].replace("{quarter}", v.quarter).replace("{year}", v.year)), "Q1 2026");
  assert.equal(libelleTrimestre("x", formater("en")), "x");
});
