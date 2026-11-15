// Task 7.1: the minimal design tokens (issue 202, invariant 8) and the static test against colour, size and spacing literals.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { genererCss } from "../scripts/generer-jetons.ts";
import type { Jetons } from "../scripts/generer-jetons.ts";
import { controlerFraicheur } from "./jetons.ts";
import { COULEURS_NOMMEES, sources, valeursEnDur, valeursEnDurDesSources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const TOKENS = "src/styles/tokens.css";

test("the checker names the file and the line of a colour literal", () => {
  assert.deepEqual(valeursEnDur("a.css", "p {\n  color: #fff;\n}"), ["a.css:2"]);
  assert.deepEqual(valeursEnDur("a.css", "p { background: rgb(1, 2, 3); }"), ["a.css:1"]);
  assert.deepEqual(valeursEnDur("a.css", "p {\n\n  border-color: red;\n}"), ["a.css:3"]);
  assert.deepEqual(valeursEnDur("a.ts", 'const s = { color: "#a1b2c3" };'), ["a.ts:1"]);
});

test("a .tsx file holding a colour literal is reported", () => {
  assert.deepEqual(valeursEnDur("a.tsx", 'export const A = () => <p style={{ color: "#fff" }}>x</p>;'), ["a.tsx:1"]);
  assert.deepEqual(valeursEnDur("a.tsx", "const a = 1;\nconst s = { color: '#a1b2c3' };"), ["a.tsx:2"]);
  assert.deepEqual(valeursEnDur("a.tsx", "// #fff in a comment\nexport const A = () => <p className=\"x\" />;"), []);
});

test("the style prop is refused in scripts, in both of its forms; a class name is not", () => {
  assert.deepEqual(valeursEnDur("a.ts", 'h("p", { style: { margin: 0 } });'), ["a.ts:1"]);
  assert.deepEqual(valeursEnDur("a.tsx", "const A = () =>\n  <p style={{ margin: 0 }}>x</p>;"), ["a.tsx:2"]);
  assert.deepEqual(valeursEnDur("a.ts", 'h("p", { className: "x" });'), []);
  assert.deepEqual(valeursEnDur("a.ts", 'const style = "font-style: italic";'), []);
});

test("every named colour of CSS Color 4 is refused in a colour property, transparent and currentcolor are admitted", () => {
  assert.equal(COULEURS_NOMMEES.size, 148);
  assert.deepEqual(valeursEnDur("a.css", "p {\n  color: tomato;\n}"), ["a.css:2"]);
  assert.deepEqual(valeursEnDur("a.css", "p { background: rebeccapurple; }"), ["a.css:1"]);
  assert.deepEqual(valeursEnDur("a.css", "p { border-color: LightGoldenRodYellow; }"), ["a.css:1"]);
  assert.deepEqual(valeursEnDur("a.css", "p { color: currentcolor; background: transparent; }"), []);
});

test("the checker names the file and the line of a size or spacing literal", () => {
  assert.deepEqual(valeursEnDur("a.css", "p {\n  margin: 8px;\n}"), ["a.css:2"]);
  assert.deepEqual(valeursEnDur("a.css", "p { padding: 0.5rem 1em; }"), ["a.css:1"]);
  assert.deepEqual(valeursEnDur("a.ts", 'const style = { width: "12px" };'), ["a.ts:1"]);
});

test("tokens, zero, percentages, comments and a colour word inside a token name pass", () => {
  const css = [
    "/* a comment: #fff, 4px, red */",
    "p {",
    "  color: var(--color-red);",
    "  margin: 0 auto;",
    "  width: 100%;",
    "  padding: var(--space-2) var(--space-3);",
    "  border: var(--border-width) solid var(--color-border);",
    "}",
  ].join("\n");
  assert.deepEqual(valeursEnDur("a.css", css), []);
  assert.deepEqual(valeursEnDur("a.ts", "// 12px and #fff in a comment\nconst a = 1;"), []);
});

test("the tokens file defines the light theme base, the spacing and the masked-cell style", () => {
  const css = readFileSync(`${FRONT}${TOKENS}`, "utf8");
  assert.match(css, /:root\s*\{/);
  for (const jeton of [
    "--color-surface",
    "--color-text",
    "--color-border",
    "--space-1",
    "--space-2",
    "--space-3",
    "--cell-masked-background",
    "--cell-masked-color",
    "--cell-masked-font-style",
    "--cell-masked-border-color",
    "--color-state-masked-border",
  ]) {
    assert.ok(css.includes(`${jeton}:`), `jeton absent : ${jeton}`);
  }
});

test("the masked cell is styled only through its tokens", () => {
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  const bloc = /\.cellule-masquee\s*\{([^}]*)\}/.exec(css);
  assert.ok(bloc, "règle .cellule-masquee absente");
  assert.match(bloc[1], /var\(--cell-masked-background\)/);
  assert.match(bloc[1], /var\(--cell-masked-color\)/);
  assert.match(bloc[1], /border-color:\s*var\(--cell-masked-border-color\)/);
  const tableau = /\.tableau\s*\{([^}]*)\}/.exec(css);
  assert.ok(tableau && /background:\s*var\(--color-surface\)/.test(tableau[1]), "règle .tableau sans fond surface");
  assert.match(/\.tableau th\s*\{([^}]*)\}/.exec(css)?.[1] ?? "", /background:\s*var\(--color-bg\)/);
});

test("no source of the front holds a colour, size or spacing literal outside the tokens file", () => {
  const fichiers = [
    ...sources(FRONT, "src", [".css", ".ts", ".tsx"]),
    { nom: "index.html", contenu: readFileSync(`${FRONT}index.html`, "utf8") },
  ];
  assert.ok(fichiers.length > 0);
  assert.deepEqual(valeursEnDurDesSources(fichiers), []);
});

test("task 24.1: the checker exempts exactly tokens.json and tokens.css, and names file and line elsewhere", () => {
  const litteral = "p { color: #fff; }";
  assert.deepEqual(valeursEnDurDesSources([{ nom: "src/styles/tokens.json", contenu: '{ "x": "#FFF", "y": "4px" }' }]), []);
  assert.deepEqual(valeursEnDurDesSources([{ nom: "src/styles/tokens.css", contenu: ":root { --a: #fff; }" }]), []);
  assert.deepEqual(valeursEnDurDesSources([{ nom: "src/styles/autre.css", contenu: `a {}\n${litteral}` }]), ["src/styles/autre.css:2"]);
  assert.deepEqual(valeursEnDurDesSources([{ nom: "src/styles/tokens2.css", contenu: litteral }]), ["src/styles/tokens2.css:1"]);
  assert.deepEqual(valeursEnDurDesSources([{ nom: "src/pages/tokens.css", contenu: litteral }]), ["src/pages/tokens.css:1"]);
  assert.deepEqual(valeursEnDurDesSources([{ nom: "src/styles/couleurs.ts", contenu: 'export const c = "#abc123";' }]), ["src/styles/couleurs.ts:1"]);
  assert.deepEqual(valeursEnDurDesSources([{ nom: "src/styles/c.tsx", contenu: 'const A = () => <p style={{ color: "#fff" }}>x</p>;' }]), ["src/styles/c.tsx:1"]);
});

const SOURCE_FAUSSE: Jetons = {
  raw: { ink: "#16231C", paper: "#F6F2E7" },
  derived: {},
  light: { bg: "paper", text: "ink" },
  scale: { "space-1": "0.25rem" },
  pairs: [],
  states: {},
};

test("task 24.1: a stale generated file fails with the file name, an up-to-date pair passes", () => {
  const fichier = "src/styles/tokens.css";
  assert.deepEqual(controlerFraicheur(SOURCE_FAUSSE, genererCss(SOURCE_FAUSSE), fichier), []);
  assert.deepEqual(controlerFraicheur(SOURCE_FAUSSE, genererCss(SOURCE_FAUSSE).replace("#F6F2E7", "#000000"), fichier), [
    "jetons CSS périmés : src/styles/tokens.css (régénérer)",
  ]);
  const modifiee = { ...SOURCE_FAUSSE, raw: { ...SOURCE_FAUSSE.raw, paper: "#FFFFFF" } };
  assert.deepEqual(controlerFraicheur(modifiee, genererCss(SOURCE_FAUSSE), fichier), ["jetons CSS périmés : src/styles/tokens.css (régénérer)"]);
});

test("task 24.1: the generated file is headed by its generated notice and holds the semantic tokens", () => {
  const css = genererCss(SOURCE_FAUSSE);
  assert.match(css.split("\n")[0], /Generated from tokens\.json by `npm run generate-tokens`: do not edit/);
  assert.ok(css.includes("--color-bg: #F6F2E7;") && css.includes("--space-1: 0.25rem;"));
});

test("task 24.1: the tracked tokens.css is the generation of tokens.json", () => {
  const source = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
  assert.deepEqual(controlerFraicheur(source, readFileSync(`${FRONT}${TOKENS}`, "utf8"), TOKENS), []);
});
