// Lot 2 of the demo dressing (design D9, D10, D16): the tokens and colour pairs of the redesign, the fonts. Each pair meets its threshold,
// the verdict and state colours do not move, "not settled" keeps its grey as border and its label in the ink on its tint.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { valeurJeton } from "../scripts/generer-jetons.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { controlerContrastes, controlerEtats, controlerLuminosites, controlerPairesCss, controlerMarquesCss, ECART_L_MINIMUM, lightnessCielab, mesures } from "./jetons.ts";
import { sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const REEL = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;

// The exact total of declared pairs: the 33 of R-20261030-57 plus the 20 pairs of the redesign below (R-20261031-74).
const NOUVELLES: ReadonlyArray<[string, string, "text" | "interface"]> = [
  ["nav-text", "nav-bg", "text"],
  ["nav-text-muted", "nav-bg", "text"],
  ["nav-heading", "nav-bg", "text"],
  ["nav-current-text", "nav-current-bg", "text"],
  ["nav-line", "nav-bg", "interface"],
  ["nav-mark-confirmed", "nav-bg", "interface"],
  ["nav-mark-refuted", "nav-bg", "interface"],
  ["nav-mark-neutral", "nav-bg", "interface"],
  ["nav-mark-confirmed", "nav-current-bg", "interface"],
  ["nav-mark-refuted", "nav-current-bg", "interface"],
  ["nav-mark-neutral", "nav-current-bg", "interface"],
  ["banner-text", "banner-bg", "text"],
  ["banner-line", "banner-bg", "interface"],
  ["data-wait-text", "data-wait", "text"],
  ["text", "data-work-tint", "text"],
  ["data-wait-strong", "surface", "text"],
  ["data-work-strong", "surface", "text"],
  ["card-line", "surface", "interface"],
  ["verdict-refuted", "verdict-refuted-tint", "text"],
  ["data-work", "surface", "interface"],
  // Lot 3b (review of lots 3a and 3b): the insufficient sample drawn without fill, directly on the page.
  ["state-insufficient", "bg", "text"],
  ["state-insufficient-border", "bg", "interface"],
];
const TOTAL_ATTENDU = 33 + NOUVELLES.length;

test("the source declares exactly the 33 earlier pairs and the 22 pairs of the redesign and of lot 3b, each with its kind", () => {
  assert.equal(NOUVELLES.length, 22);
  assert.equal(TOTAL_ATTENDU, 55);
  assert.equal(REEL.pairs.length, TOTAL_ATTENDU);
  for (const [fg, bg, kind] of NOUVELLES) {
    const trouvees = REEL.pairs.filter((p) => p.foreground === fg && p.background === bg);
    assert.deepEqual(trouvees.map((p) => p.kind), [kind], `${fg} sur ${bg}`);
  }
  const doubles = REEL.pairs.map((p) => `${p.foreground}|${p.background}`);
  assert.equal(new Set(doubles).size, doubles.length, "aucune paire déclarée deux fois");
});

test("every pair of the redesign meets its threshold: 4.5:1 for text, 3:1 for interface", () => {
  assert.deepEqual(controlerContrastes(REEL), []);
  const mesurees = mesures(REEL);
  for (const [fg, bg, kind] of NOUVELLES) {
    const m = mesurees.find((x) => x.foreground === fg && x.background === bg);
    assert.ok(m?.ratio !== undefined, `${fg} sur ${bg} mesurée`);
    assert.ok(m.ratio >= (kind === "text" ? 4.5 : 3), `${fg} sur ${bg} : ${m.ratio}`);
  }
});

test("the work label is in ink on a lighter work tint: no white label on the blue of the work part", () => {
  assert.ok(REEL.pairs.some((p) => p.foreground === "text" && p.background === "data-work-tint" && p.kind === "text"));
  assert.ok(!REEL.pairs.some((p) => p.background === "data-work" && p.kind === "text"), "pas de texte sur le bleu du travail");
  assert.equal(REEL.light["data-work"], "series-cycle");
  // A white label on the blue of the work part fails the contrast test (about 3.9:1 in the mockups).
  const blanc: Jetons = { ...REEL, raw: { ...REEL.raw, white: "#FFFFFF" }, pairs: [{ foreground: "white", background: "data-work", kind: "text", usage: "fake" }] };
  assert.match(controlerContrastes(blanc).join("\n"), /contraste insuffisant : white sur data-work/);
});

test("the card line meets 3:1 on the surface: a decorative line under 3:1 is not admitted", () => {
  const m = mesures(REEL).find((x) => x.foreground === "card-line" && x.background === "surface");
  assert.ok(m?.ratio !== undefined && m.ratio >= 3);
  assert.notEqual(valeurJeton(REEL, "card-line"), "#E3DCC8");
});

test("not settled keeps #909090 as border and marker, and its badge text is the ink on its tint", () => {
  assert.equal(REEL.light["verdict-not-settled"], "#909090");
  assert.ok(REEL.pairs.some((p) => p.foreground === "verdict-not-settled" && p.background === "surface" && p.kind === "interface"));
  assert.ok(REEL.pairs.some((p) => p.foreground === "text" && p.background === "verdict-not-settled-tint" && p.kind === "text"));
  assert.ok(!REEL.pairs.some((p) => p.foreground === "verdict-not-settled" && p.kind === "text"), "jamais en texte");
  assert.notEqual(valeurJeton(REEL, "verdict-not-settled"), "#4A4F4C");
});

test("no verdict or state colour changes for the redesign, and the new refuted tint is distinct", () => {
  assert.equal(REEL.light["verdict-confirmed"], "#0E6E63");
  assert.equal(REEL.light["verdict-confirmed-tint"], "#DDEFEA");
  assert.equal(REEL.light["verdict-refuted"], "#3B2470");
  assert.equal(REEL.light["verdict-not-settled-tint"], "#E8EAE8");
  assert.equal(REEL.light["state-error"], "#C62A1E");
  assert.equal(REEL.light["state-masked"], "#3E4A44");
  assert.equal(REEL.light["state-masked-bg"], "#E4E6DF");
  assert.equal(REEL.light["verdict-refuted-tint"], "#E9E3F4");
  assert.deepEqual(Object.keys(REEL.states), [
    "verdict-confirmed",
    "verdict-refuted",
    "verdict-not-settled",
    "state-masked",
    "state-insufficient",
    "state-error",
    "state-loading",
    "state-in-progress",
    "state-not-tested",
    "state-partial-evidence",
  ]);
  assert.deepEqual(controlerEtats(REEL, catalogues), []);
  assert.deepEqual(controlerLuminosites(REEL), []);
});

test("the three side-column marker colours are three distinct values", () => {
  const couleurs = ["nav-mark-confirmed", "nav-mark-refuted", "nav-mark-neutral"].map((j) => valeurJeton(REEL, j));
  assert.equal(new Set(couleurs).size, 3);
});

// Lightness rule of 2026-10-27 applied to the markers (jetonsDeLuminosite untouched): at least ECART_L_MINIMUM of CIELAB L* between any two.
test("the side-column markers keep the lightness gap of the verdict colours between them", () => {
  const jetons = ["nav-mark-confirmed", "nav-mark-refuted", "nav-mark-neutral"];
  const l = jetons.map((j) => lightnessCielab(valeurJeton(REEL, j) as string));
  for (let a = 0; a < jetons.length; a++) {
    for (let b = a + 1; b < jetons.length; b++) {
      assert.ok(Math.abs(l[a] - l[b]) >= ECART_L_MINIMUM, `${jetons[a]} et ${jetons[b]} : ΔL* ${Math.abs(l[a] - l[b])}`);
    }
  }
});

// data-work-tint: the lighter tint of the work part, whose label is in ink (Q131); a white label on the blue is refused above.

test("the tokens of the redesign exist, as colour tokens or in the scale, under their role names", () => {
  for (const jeton of [
    "nav-bg", "nav-text", "nav-text-muted", "nav-heading", "nav-current-bg", "nav-current-text", "nav-line",
    "banner-bg", "banner-text", "banner-line",
    "data-wait", "data-work", "data-wait-text", "data-work-tint",
    "data-wait-strong", "data-work-strong",
    "nav-mark-confirmed", "nav-mark-refuted", "nav-mark-neutral",
    "card-line", "verdict-refuted-tint",
    "brand-primary", "brand-secondary", "brand-lab",
  ]) {
    assert.ok(Object.hasOwn(REEL.light, jeton), `jeton absent : ${jeton}`);
  }
  for (const jeton of ["font-family", "font-family-heading", "font-size-statement", "font-size-figure"]) {
    assert.ok(Object.hasOwn(REEL.scale, jeton), `jeton d'échelle absent : ${jeton}`);
  }
  // The earlier names are gone, same values under the new ones.
  for (const ancien of ["series-wait", "series-work", "series-wait-label", "series-work-tint", "figure-wait", "figure-work", "brand-mothra", "brand-mothra-hind", "brand-pmzilla"]) {
    assert.ok(!Object.hasOwn(REEL.light, ancien), `ancien jeton encore là : ${ancien}`);
  }
  assert.ok(!Object.hasOwn(REEL.scale, "font-family-statement"));
  assert.equal(valeurJeton(REEL, "brand-primary"), "#D98A1C");
  assert.equal(valeurJeton(REEL, "brand-secondary"), "#F2B630");
  assert.equal(valeurJeton(REEL, "brand-lab"), "#2F7DE1");
});

// Role names (decision 13): a semantic or scale token is never named after a product (Q134, R-20261031-77).
const MARQUES = /mothra|pmzilla/i;
function controlerNomsDeMarque(source: Jetons): string[] {
  return [...Object.keys(source.light), ...Object.keys(source.scale)].filter((j) => MARQUES.test(j)).map((j) => `jeton nommé d'après une marque : ${j}`);
}

test("a semantic or scale token named after a product fails with its name; the real source has none", () => {
  assert.deepEqual(controlerNomsDeMarque(REEL), []);
  const faux: Jetons = { ...REEL, light: { ...REEL.light, "brand-mothra": "amber", "nav-pmzilla": "ink" }, scale: { ...REEL.scale, "font-mothra": "serif" } };
  assert.deepEqual(controlerNomsDeMarque(faux), [
    "jeton nommé d'après une marque : brand-mothra",
    "jeton nommé d'après une marque : nav-pmzilla",
    "jeton nommé d'après une marque : font-mothra",
  ]);
});

test("the brand checker still refuses a style rule reading a brand token under its role name", () => {
  assert.deepEqual(controlerMarquesCss([{ nom: "src/styles/a.css", contenu: ".a { color: var(--color-brand-primary); }" }]), ["jeton de marque dans une règle : src/styles/a.css:1"]);
});

test("the fonts: IBM Plex Sans for the texts, IBM Plex Serif for the statement, the system stack as fallback", () => {
  assert.match(REEL.scale["font-family"], /^"?IBM Plex Sans"?, system-ui, sans-serif$/);
  assert.match(REEL.scale["font-family-heading"], /^"?IBM Plex Serif"?, (?:Georgia, )?serif$/);
  assert.ok(!/http|\/\//.test(REEL.scale["font-family"] + REEL.scale["font-family-heading"]), "aucune ressource externe");
});

test("main.ts imports the font style sheets of the local Fontsource packages, nothing from another host", () => {
  const main = readFileSync(`${FRONT}src/main.ts`, "utf8");
  const imports = [...main.matchAll(/^import\s+"(@fontsource\/[^"]+)";$/gm)].map((m) => m[1]);
  assert.deepEqual(imports, [
    "@fontsource/ibm-plex-sans/latin-400.css",
    "@fontsource/ibm-plex-sans/latin-500.css",
    "@fontsource/ibm-plex-sans/latin-600.css",
    "@fontsource/ibm-plex-sans/latin-700.css",
    "@fontsource/ibm-plex-serif/latin-500.css",
    "@fontsource/ibm-plex-serif/latin-600.css",
  ]);
  assert.ok(!/https?:|\/\/fonts\./.test(main));
});

test("the two Fontsource packages are direct dependencies of the front at an exact version", () => {
  const paquet = JSON.parse(readFileSync(`${FRONT}package.json`, "utf8")) as { dependencies: Record<string, string> };
  assert.equal(paquet.dependencies["@fontsource/ibm-plex-sans"], "5.3.0");
  assert.equal(paquet.dependencies["@fontsource/ibm-plex-serif"], "5.3.0");
});

test("no style rule of the front uses an undeclared colour pair with the new tokens", () => {
  assert.deepEqual(controlerPairesCss(REEL, sources(FRONT, "src", [".css"])), []);
});
