// Author's decision 5 of 2026-10-27: no chart series takes the hue of a state colour. Measured, not judged by eye: every series colour
// is at least SEUIL_ECART00 (CIEDE2000, CIELAB D65) away from every state colour, in normal vision and in the simulations of protanopia,
// deuteranopia and tritanopia (Machado, Oliveira and Fernandes 2009, severity 1.0, on linear RGB). No package: test/couleurs.ts.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { valeurJeton } from "../scripts/generer-jetons.ts";
import type { Jetons } from "../scripts/generer-jetons.ts";
import { ecart00, hexVersLab, hexVersLineaire, lineaireVersLab, PROTANOPIE, simuler, VISIONS, vue } from "./couleurs.ts";
import type { Lab } from "./couleurs.ts";
import { ratio } from "./jetons.ts";
import { sansCommentairesCss } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const REEL = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;

// The threshold: 10 is about the gap between two clearly different colours side by side (a just noticeable difference is about 1, two
// shades of one hue about 5); it is reachable among the dark colours of this palette, as the table of the diagnostic shows.
export const SEUIL_ECART00 = 10;

const SERIES = ["series-lead", "series-cycle"];
// The state colours: every verdict and state token, and the information colour (a semantic colour with a meaning of its own).
const ETATS = Object.keys(REEL.light).filter((n) => /^(?:state-|verdict-)/.test(n) || n === "info");

function couleur(nom: string): string {
  const v = valeurJeton(REEL, nom);
  assert.ok(v !== undefined, nom);
  return v;
}

function proche(a: readonly number[], b: readonly number[], tolerance: number): void {
  a.forEach((x, i) => assert.ok(Math.abs(x - b[i]) <= tolerance, `${a.join(",")} différent de ${b.join(",")}`));
}

// ---- reference values --------------------------------------------------------------------------------------------------------

test("sRGB to CIELAB D65 on reference colours: white, black, red, and a mid grey", () => {
  proche(hexVersLab("#FFFFFF"), [100, 0, 0], 0.01);
  proche(hexVersLab("#000000"), [0, 0, 0], 0.01);
  proche(hexVersLab("#FF0000"), [53.2408, 80.0925, 67.2032], 0.01);
  proche(hexVersLab("#808080"), [53.5850, 0, 0], 0.01);
});

test("CIEDE2000 on pairs 1 to 3, 7 to 14 and 16 of the data of Sharma, Wu and Dalal (2005)", () => {
  const paires: Array<[Lab, Lab, number]> = [
    [[50, 2.6772, -79.7751], [50, 0, -82.7485], 2.0425],
    [[50, 3.1571, -77.2803], [50, 0, -82.7485], 2.8615],
    [[50, 2.8361, -74.02], [50, 0, -82.7485], 3.4412],
    // pairs 7 and 8: a small difference near the neutral axis, both orders
    [[50, 0, 0], [50, -1, 2], 2.3669],
    [[50, -1, 2], [50, 0, 0], 2.3669],
    // pairs 9 to 12: opposite hues across the 180 degree wrap of the hue difference
    [[50, 2.49, -0.001], [50, -2.49, 0.0009], 7.1792],
    [[50, 2.49, -0.001], [50, -2.49, 0.001], 7.1792],
    [[50, 2.49, -0.001], [50, -2.49, 0.0011], 7.2195],
    [[50, 2.49, -0.001], [50, -2.49, 0.0012], 7.2195],
    // pairs 13, 14 and 16: larger differences in lightness and chroma
    [[50, 2.5, 0], [50, 0, -2.5], 4.3065],
    [[50, 2.5, 0], [73, 25, -18], 27.1492],
    [[50, 2.5, 0], [56, -27, -3], 31.903],
  ];
  for (const [a, b, attendu] of paires) {
    assert.ok(Math.abs(ecart00(a, b) - attendu) < 0.0001, `${a} ${b} : ${ecart00(a, b)} au lieu de ${attendu}`);
    assert.ok(Math.abs(ecart00(b, a) - attendu) < 0.0001, "symétrie");
  }
  assert.equal(ecart00([50, 10, 10], [50, 10, 10]), 0);
});

test("the dichromacy simulation keeps white and black, and sends pure red toward a dark olive yellow under protanopia", () => {
  proche(simuler(hexVersLineaire("#FFFFFF"), PROTANOPIE), [1, 1, 1], 0.001);
  proche(simuler(hexVersLineaire("#000000"), PROTANOPIE), [0, 0, 0], 0);
  const [L, a, b] = lineaireVersLab(simuler(hexVersLineaire("#FF0000"), PROTANOPIE));
  assert.ok(L < 45 && Math.abs(a) < 10 && b > 30, `${L} ${a} ${b}`);
});

// ---- the series against the state colours ------------------------------------------------------------------------------------

function ecarts(serie: string): Array<{ etat: string; vision: string; ecart: number }> {
  return ETATS.flatMap((etat) =>
    VISIONS.map(([vision, matrice]) => ({ etat, vision, ecart: ecart00(vue(couleur(serie), matrice), vue(couleur(etat), matrice)) })),
  );
}

test("every series colour is at least the threshold away from every state colour, in normal vision and in three simulated deficiencies", (t) => {
  assert.ok(ETATS.length >= 8, ETATS.join(" "));
  const lignes: string[] = [];
  for (const serie of SERIES) {
    const tous = ecarts(serie);
    const pire = tous.reduce((m, e) => (e.ecart < m.ecart ? e : m));
    lignes.push(`${serie} ${couleur(serie)} : minimum ${pire.ecart.toFixed(1)} (${pire.etat}, ${pire.vision})`);
    for (const [vision] of VISIONS) {
      const dansVision = tous.filter((e) => e.vision === vision);
      const m = dansVision.reduce((a, e) => (e.ecart < a.ecart ? e : a));
      lignes.push(`  ${vision.padEnd(12)} ${m.ecart.toFixed(1)} (${m.etat})`);
    }
    const trop = tous.filter((e) => e.ecart < SEUIL_ECART00);
    assert.deepEqual(trop.map((e) => `${serie} / ${e.etat} / ${e.vision} : ${e.ecart.toFixed(1)}`), [], lignes.join("\n"));
  }
  t.diagnostic(lignes.join("\n"));
});

test("the two series are at least the threshold apart from each other, in every vision", () => {
  for (const [vision, matrice] of VISIONS) {
    const e = ecart00(vue(couleur("series-lead"), matrice), vue(couleur("series-cycle"), matrice));
    assert.ok(e >= SEUIL_ECART00, `${vision} : ${e.toFixed(1)}`);
  }
});

test("each series colour has its declared interface pair on the surface and on the page, at 3:1 at least", () => {
  for (const serie of SERIES) {
    for (const fond of ["surface", "bg"]) {
      const paire = REEL.pairs.find((p) => p.foreground === serie && p.background === fond);
      assert.ok(paire !== undefined && paire.kind === "interface", `${serie} sur ${fond}`);
      assert.ok(ratio(couleur(serie), couleur(fond)) >= 3, `${serie} sur ${fond}`);
    }
  }
});

// ---- the focus ring is recognised by its shape, not by its colour --------------------------------------------------------------

// A token length in pixels (px as written, rem on the 16 px default of the browser).
function enPx(longueur: string): number {
  return longueur.endsWith("rem") ? Number.parseFloat(longueur) * 16 : Number.parseFloat(longueur);
}

test("the focus ring is at least twice as thick as a series line and set off the outline by at least 2 px, both from the tokens", () => {
  const css = sansCommentairesCss(readFileSync(`${FRONT}src/styles/styles.css`, "utf8"));
  const regle = /(?:^|\n):focus-visible\s*\{([^}]*)\}/.exec(css);
  assert.ok(regle, "règle :focus-visible absente");
  assert.match(regle[1], /outline:\s*var\(--focus-ring-width\)\s+solid\s+var\(--color-focus\)/);
  assert.match(regle[1], /outline-offset:\s*var\(--focus-ring-offset\)/);
  const epaisseur = enPx(REEL.scale["focus-ring-width"]);
  const decalage = enPx(REEL.scale["focus-ring-offset"]);
  const trait = enPx(REEL.scale["series-line-width"]);
  assert.ok(epaisseur >= 2 * trait, `anneau ${epaisseur} px, trait ${trait} px`);
  assert.ok(decalage >= 2, `décalage ${decalage} px`);
  // no other rule of the stylesheet gives an element its own outline, so the one ring above is the ring of every focusable element
  assert.equal([...css.matchAll(/(?<![-\w])outline(?:-[a-z]+)?\s*:/g)].length, 2);
});

test("no series colour is the same colour as a state colour", () => {
  for (const serie of SERIES) for (const etat of ETATS) assert.notEqual(couleur(serie).toUpperCase(), couleur(etat).toUpperCase(), `${serie} ${etat}`);
});
