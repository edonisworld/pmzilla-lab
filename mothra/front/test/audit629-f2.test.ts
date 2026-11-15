// Tests du groupe F2 de l'audit #629 (robustesse et accessibilité du front) : noms accessibles du formulaire (A-07), plage des trimestres (A-81),
// conteneurs défilants atteignables au clavier (A-85), bannière dans un repère (A-99). Rendu serveur, valeurs fictives seulement.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import type { PanneauStoriesInout } from "@mothra/contract";

import { plageEffective } from "../src/api/filtres.ts";
import { ChampsFiche, valeursVides } from "../src/composants/ChampsFiche.ts";
import { ChoixDesactive } from "../src/composants/ChoixDesactive.ts";
import { FicheMethode } from "../src/composants/FicheMethode.ts";
import { VuePanneau } from "../src/composants/PanneauxProduit.ts";
import { Tableau } from "../src/composants/Tableau.ts";
import { TableauLeadCycle } from "../src/composants/TableauLeadCycle.ts";
import { Coquille } from "../src/gabarits/Coquille.ts";
import { NavigationLaterale } from "../src/composants/NavigationLaterale.ts";
import { ficheSimulee } from "./fiche-simulee.ts";
import { rendre } from "./rendu.ts";

test("A-07 : chaque liste de langue est reliée à son libellé par for et id, sans envelopper la liste", () => {
  const html = rendre(h(ChampsFiche, { valeurs: valeursVides("en"), surChangement: () => undefined }), "en");
  const listes = [...html.matchAll(/<select\b[^>]*\bid="([^"]+)"[^>]*data-champ-langue="[^"]*"/g)].map((m) => m[1]);
  assert.equal(listes.length, 2);
  for (const id of listes) {
    const libelle = new RegExp(`<label\\b[^>]*\\bfor="${id.replace(/[:.]/g, "\\$&")}"[^>]*>Language of this text</label>`);
    assert.match(html, libelle);
  }
  assert.equal(new Set(listes).size, 2, "deux identifiants distincts");
  assert.doesNotMatch(html, /<label[^>]*>Language of this text<select/);
});

test("A-07 : le choix désactivé relie son libellé à la case par for et id", () => {
  const html = rendre(h(ChoixDesactive, { nom: "g", valeur: "lead_cycle_h5", libelle: "conviction.nav.lead_cycle_h5", raison: "tableau.form.h5RealUnavailable" }), "en");
  const pour = /<label\b[^>]*\bfor="([^"]+)"/.exec(html)?.[1];
  const id = /<input\b[^>]*\bid="([^"]+)"/.exec(html)?.[1];
  assert.ok(pour !== undefined && id !== undefined);
  assert.equal(pour, id);
});

test("A-81 : un trimestre hors de la barre revient au trimestre offert, une plage inversée est remise dans l'ordre", () => {
  const offerts = ["2026-Q1", "2026-Q2", "2026-Q3"];
  assert.deepEqual(plageEffective(undefined, undefined, offerts), { from: "2026-Q1", to: "2026-Q3" });
  assert.deepEqual(plageEffective("2020-Q1", "2030-Q4", offerts), { from: "2026-Q1", to: "2026-Q3" });
  assert.deepEqual(plageEffective("2026-Q2", "2026-Q2", offerts), { from: "2026-Q2", to: "2026-Q2" });
  assert.deepEqual(plageEffective("2026-Q3", "2026-Q1", offerts), { from: "2026-Q1", to: "2026-Q3" });
  assert.deepEqual(plageEffective("2026-Q2", undefined, []), { from: undefined, to: undefined });
});

test("A-85 : le conteneur défilant du tableau est atteignable au clavier", () => {
  const valeur = (n: number) => ({ state: "value" as const, value: n });
  const html = rendre(h(TableauLeadCycle, { points: [{ quarter: "2026-Q1", lead: valeur(20), cycle: valeur(8), items: valeur(30) }], seuil: 5 }), "en");
  assert.match(html, /<div class="tableau-conteneur" tabindex="0">/);
});

test("A-85 : le conteneur défilant du tableau générique est atteignable au clavier", () => {
  const html = rendre(h(Tableau, { colonnes: ["team"], lignes: [{ team: "team-a" }], seuil: 5 }), "en");
  assert.match(html, /<div class="tableau-conteneur" tabindex="0">/);
});

test("A-85 : le conteneur défilant d'un panneau du produit est atteignable au clavier", () => {
  const valeur = (n: number) => ({ state: "value" as const, value: n });
  const panneau: PanneauStoriesInout = {
    scope: "product",
    from: "2026-Q1",
    to: "2026-Q1",
    threshold: 5,
    dataDate: "2026-10-27",
    dataset: "synthetic",
    panel: "stories-inout",
    hypothesis: "h1_second_half",
    mentions: ["indirect_indicator"],
    points: [{ quarter: "2026-Q1", created: valeur(10), done: valeur(8) }],
    total: { created: valeur(10), done: valeur(8) },
  };
  const html = rendre(h(VuePanneau, { reponse: panneau, demandee: "product" }), "en");
  assert.match(html, /<div class="tableau-conteneur" tabindex="0">/);
});

test("A-85 : le conteneur défilant des cellules masquées de la face méthode est atteignable au clavier", () => {
  const methode = { ...ficheSimulee().method, maskedCells: [{ measure: "cycle_median_days@2026-04-01", cell: { state: "masked" as const, threshold: 5 } }] };
  const html = rendre(h(FicheMethode, { methode, id: "methode" }), "en");
  assert.match(html, /<div class="tableau-conteneur" tabindex="0">(?:(?!<\/div>).)*data-tableau="masquees"/s);
});

test("A-99 : la bannière est dans un repère (header), avant la colonne principale", () => {
  const nav = h(NavigationLaterale, { accueilCourant: true, convictions: [] });
  const html = rendre(h(Coquille, { navigation: nav, jeu: "synthetic" }, h("p", null, "x")), "en");
  assert.match(html, /<header><div role="note" class="banniere"/);
  assert.ok(html.indexOf('<header><div role="note"') < html.indexOf("<main"));
  assert.doesNotMatch(rendre(h(Coquille, { navigation: nav }), "en"), /<header><div role="note"/);
});
