// Task 7.3: the table and masked-cell components (design D3, D8): the catalogue label of the masked state, distinct from empty and zero,
// the threshold stated once per table, and no total or difference derived from cells.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import type { Valeur } from "../src/api/vue.ts";
import { CelluleMasquee } from "../src/composants/Cellule.ts";
import { Tableau } from "../src/composants/Tableau.ts";
import { rendre, texte } from "./rendu.ts";
import { derivations, sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const COLONNES = ["team", "status", "tickets"];

function lignes(...comptes: Valeur[]): Array<Record<string, Valeur>> {
  return comptes.map((compte, rang) => ({ team: `Team ${rang + 1}`, status: "open", tickets: compte }));
}

const MASQUEE: Valeur = { state: "masked", threshold: 5 };

function cellules(html: string, classe: string): string[] {
  return [...html.matchAll(new RegExp(`<td class="[^"]*${classe}[^"]*"[^>]*>([^<]*)</td>`, "g"))].map((m) => m[1]);
}

test("a masked cell shows the label of the masked state in each language, with the masked-cell style", () => {
  const anglais = rendre(h("table", null, h("tbody", null, h("tr", null, h(CelluleMasquee)))), "en");
  const francais = rendre(h("table", null, h("tbody", null, h("tr", null, h(CelluleMasquee)))), "fr");
  assert.match(anglais, /<td class="cellule cellule-masquee" data-state="masked">masked<\/td>/);
  assert.match(francais, /<td class="cellule cellule-masquee" data-state="masked">masqué<\/td>/);
});

test("a masked cell holds neither the threshold nor any number", () => {
  const html = rendre(h("table", null, h("tbody", null, h("tr", null, h(CelluleMasquee)))), "en");
  assert.doesNotMatch(texte(html), /\d/);
});

test("a masked cell is distinct from an empty cell and from a zero", () => {
  const html = rendre(h(Tableau, { colonnes: COLONNES, lignes: lignes(MASQUEE, 0, null), seuil: 5 }), "en");
  assert.deepEqual(cellules(html, "cellule-masquee"), ["masked"]);
  assert.deepEqual(cellules(html, "cellule-valeur"), ["0"]);
  assert.deepEqual(cellules(html, "cellule-vide"), [""]);
  assert.match(html, /data-state="empty"/);
});

test("a value cell shows the value as received, with the number format of the language", () => {
  const valeur: Valeur = { state: "value", value: 1234 };
  assert.deepEqual(cellules(rendre(h(Tableau, { colonnes: COLONNES, lignes: lignes(valeur), seuil: 5 }), "en"), "cellule-valeur"), ["1,234"]);
  const francais = cellules(rendre(h(Tableau, { colonnes: COLONNES, lignes: lignes(valeur), seuil: 5 }), "fr"), "cellule-valeur");
  assert.equal(francais.length, 1);
  assert.match(francais[0].replace(/\s/g, ""), /^1.?234$/);
});

test("the threshold is stated once per table, from the catalogue, in each language", () => {
  const table = lignes(MASQUEE, MASQUEE, { state: "value", value: 12 }, MASQUEE);
  const anglais = texte(rendre(h(Tableau, { colonnes: COLONNES, lignes: table, seuil: 5 }), "en"));
  const francais = texte(rendre(h(Tableau, { colonnes: COLONNES, lignes: table, seuil: 5 }), "fr"));
  assert.equal(anglais.split("Counts under 5 are masked.").length - 1, 1);
  assert.equal(francais.split("Les effectifs inférieurs à 5 sont masqués.").length - 1, 1);
  assert.equal(anglais.split("masked").length - 1, 4); // three masked cells and the legend
});

test("two tables state their own threshold once each", () => {
  const deux = h("div", null, h(Tableau, { colonnes: COLONNES, lignes: lignes(MASQUEE), seuil: 5 }), h(Tableau, { colonnes: COLONNES, lignes: lignes(MASQUEE), seuil: 8 }));
  const html = texte(rendre(deux, "en"));
  assert.equal(html.split("Counts under 5 are masked.").length - 1, 1);
  assert.equal(html.split("Counts under 8 are masked.").length - 1, 1);
});

test("column codes are translated, an unknown code is shown as received", () => {
  const html = rendre(h(Tableau, { colonnes: ["team", "tickets", "constructor"], lignes: [], seuil: 5 }), "fr");
  assert.match(html, /<th scope="col">Équipe<\/th>/);
  assert.match(html, /<th scope="col">Tickets<\/th>/);
  assert.match(html, /<th scope="col">constructor<\/th>/);
});

test("an empty table says so and keeps its header", () => {
  const html = rendre(h(Tableau, { colonnes: COLONNES, lignes: [], seuil: 5 }), "en");
  assert.match(html, /No rows\./);
  assert.match(html, /<th scope="col">Team<\/th>/);
});

test("no total and no difference is displayed when the server sends none", () => {
  const donnees: Valeur[] = [{ state: "value", value: 12 }, { state: "value", value: 8 }, MASQUEE];
  const html = rendre(h(Tableau, { colonnes: COLONNES, lignes: lignes(...donnees), seuil: 5 }), "en");
  const corps = /<tbody>([\s\S]*)<\/tbody>/.exec(html)?.[1] ?? "";
  assert.equal((corps.match(/<tr>/g) ?? []).length, 3);
  assert.deepEqual(texte(corps).match(/\d+/g)?.filter((n) => Number(n) > 3), ["12", "8"]); // no 20, no 4, no other derived figure
  assert.doesNotMatch(texte(html), /total/i);
});

test("a total sent by the server is shown as an ordinary row, as received", () => {
  const html = rendre(h(Tableau, { colonnes: COLONNES, lignes: [...lignes({ state: "value", value: 12 }), { team: "Total", status: "open", tickets: { state: "value", value: 99 } }], seuil: 5 }), "en");
  assert.match(html, />99</);
});

test("the checker names the file and the line of a derivation from cells", () => {
  assert.deepEqual(derivations("a.ts", "const t = cellules.reduce((a, c) => a + c.value, 0);"), ["a.ts:1"]);
  assert.deepEqual(derivations("a.ts", "let somme = 0;\nsomme += 1;"), ["a.ts:2"]);
  assert.deepEqual(derivations("a.ts", "const d = a.value - b.value;"), ["a.ts:1"]);
  assert.deepEqual(derivations("a.ts", "const m = Math.max(a, b);"), ["a.ts:1"]);
  assert.deepEqual(derivations("a.ts", "const s = x.threshold + 1;"), ["a.ts:1"]);
  assert.deepEqual(derivations("a.ts", "// a.value - b.value in a comment\nconst v = cell.value;"), []);
});

test("no source of the front derives a number from cells", () => {
  const trouves = sources(FRONT, "src", [".ts", ".tsx"]).flatMap((s) => derivations(s.nom, s.contenu));
  assert.deepEqual(trouves, []);
});
