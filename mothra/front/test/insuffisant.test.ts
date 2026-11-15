// "Insufficient sample" is told apart from the masked cell by more than its label (author's decision of 2026-10-27): its own border
// colour token and pair, a different border pattern, its own icon, and a style rule that is not the masked cell's.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { controlerContrastes, controlerEtats, controlerPairesCss, mesures } from "./jetons.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { sansCommentairesCss, sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const REEL = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
const CSS = sansCommentairesCss(readFileSync(`${FRONT}src/styles/styles.css`, "utf8"));

function declarations(classe: string): string[] {
  const bloc = new RegExp(`\\.${classe}\\s*\\{([^}]*)\\}`).exec(CSS);
  assert.ok(bloc, `règle .${classe} absente`);
  return bloc[1].split(";").map((d) => d.replace(/\s+/g, " ").trim()).filter((d) => d !== "").sort();
}

test("the border of the insufficient sample is the 24th declared pair, with its own semantic token, on the surface, 3:1 at least", () => {
  // exact total: 33 of R-20261030-57, 20 of the demo dressing (R-20261031-74) and 2 of lot 3b for the insufficient sample drawn without fill on
  // the page (review of lots 3a and 3b, D9)
  assert.equal(REEL.pairs.length, 55);
  const paire = REEL.pairs.filter((p) => p.foreground === "state-insufficient-border");
  assert.deepEqual(paire.map((p) => [p.background, p.kind]), [["surface", "interface"], ["bg", "interface"]]);
  assert.equal(REEL.light["state-insufficient-border"], "ink-muted");
  const mesure = mesures(REEL).find((m) => m.foreground === "state-insufficient-border");
  assert.ok(mesure?.ratio !== undefined && mesure.ratio >= 3);
  assert.deepEqual(controlerContrastes(REEL), []);
  assert.ok(!REEL.pairs.some((p) => p.foreground === "state-masked-border" && /insufficient/.test(p.usage)), "la paire du masqué ne sert plus l'échantillon insuffisant");
});

test("the insufficient sample has its own icon, label and border pattern in states, different from the masked cell's", () => {
  const insuffisant = REEL.states["state-insufficient"];
  const masque = REEL.states["state-masked"];
  assert.equal(insuffisant.label, "state.insufficient_sample");
  assert.ok(insuffisant.icon !== "" && insuffisant.icon !== "none", "icône propre attendue");
  assert.notEqual(insuffisant.icon, masque.icon);
  assert.notEqual(insuffisant.outline, masque.outline);
  assert.notEqual(catalogues.en[insuffisant.label], catalogues.en[masque.label]);
  assert.deepEqual(controlerEtats(REEL, catalogues), []);
});

test("the border pattern of the insufficient sample is dotted, the masked cell's is dashed", () => {
  assert.equal(REEL.scale["cell-insufficient-border-style"], "dotted");
  assert.equal(REEL.scale["cell-masked-border-style"], "dashed");
  assert.equal(REEL.scale["cell-insufficient-border-color"], "{state-insufficient-border}");
});

test("the two style rules are not the same set of declarations, and each follows its own border tokens", () => {
  const masquee = declarations("cellule-masquee");
  const insuffisante = declarations("cellule-insuffisante");
  assert.notDeepEqual(insuffisante, masquee);
  assert.ok(insuffisante.includes("border-style: var(--cell-insufficient-border-style)"));
  assert.ok(insuffisante.includes("border-color: var(--cell-insufficient-border-color)"));
  assert.ok(masquee.includes("border-style: var(--cell-masked-border-style)"));
  assert.ok(!insuffisante.some((d) => /italic|cell-masked/.test(d)), "ni italique ni jeton du masqué");
  assert.ok(!insuffisante.some((d) => d.startsWith("background")), "contour sans remplissage");
  assert.ok(!masquee.some((d) => /insufficient/.test(d)));
});

test("no style rule of the front uses an undeclared colour pair with the new border", () => {
  assert.deepEqual(controlerPairesCss(REEL, sources(FRONT, "src", [".css"])), []);
});
