// Tasks 24.3 and 24.5: the contrast test per declared pair of design D32 (WCAG 2.1), on fake sources and on the real one.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { genererCss } from "../scripts/generer-jetons.ts";
import type { Jetons } from "../scripts/generer-jetons.ts";
import { controlerContrastes, controlerMarquesCss, controlerPairesCss, mesures, ratio } from "./jetons.ts";
import { sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;

function source(partiel: Partial<Jetons>): Jetons {
  return {
    raw: { ink: "#16231C", paper: "#F6F2E7", amber: "#D98A1C", blue: "#2F7DE1" },
    derived: {},
    light: { bg: "paper", text: "ink" },
    scale: {},
    pairs: [],
    states: {},
    ...partiel,
  };
}

test("the WCAG 2.1 ratio of black on white is 21 and of a colour on itself is 1", () => {
  assert.equal(ratio("#000000", "#FFFFFF"), 21);
  assert.equal(ratio("#FFFFFF", "#000000"), 21);
  assert.equal(ratio("#336699", "#336699"), 1);
});

test("a pair under its threshold fails with the ratio truncated to two decimals (amber on paper, kind text)", () => {
  const s = source({ pairs: [{ foreground: "amber", background: "paper", kind: "text", usage: "fake" }] });
  // The exact ratio is 2.4699...: D32 and task 24.3 write 2.47 (hand-rounded), the truncation rule gives 2.46.
  assert.deepEqual(controlerContrastes(s), ["contraste insuffisant : amber sur paper (2.46 < 4.5)"]);
});

test("the threshold is 4.5 for text and 3 for large text and interface", () => {
  const paire = (kind: "text" | "large-text" | "interface") => source({ pairs: [{ foreground: "blue", background: "paper", kind, usage: "fake" }] });
  assert.deepEqual(controlerContrastes(paire("text")).map((m) => m.replace(/\(.* </, "(x <")), ["contraste insuffisant : blue sur paper (x < 4.5)"]);
  assert.deepEqual(controlerContrastes(paire("large-text")), []);
  assert.deepEqual(controlerContrastes(paire("interface")), []);
  const faible = source({ pairs: [{ foreground: "amber", background: "paper", kind: "interface", usage: "fake" }] });
  assert.deepEqual(controlerContrastes(faible), ["contraste insuffisant : amber sur paper (2.46 < 3)"]);
});

test("a pair that meets its threshold passes, and a semantic token is followed to its value", () => {
  const s = source({ pairs: [{ foreground: "text", background: "bg", kind: "text", usage: "fake" }] });
  assert.deepEqual(controlerContrastes(s), []);
});

test("a pair naming an absent token fails with the token name", () => {
  const s = source({
    pairs: [
      { foreground: "ghost", background: "bg", kind: "text", usage: "fake" },
      { foreground: "text", background: "phantom", kind: "text", usage: "fake" },
    ],
  });
  assert.deepEqual(controlerContrastes(s), ["jeton inconnu dans une paire : ghost", "jeton inconnu dans une paire : phantom"]);
});

const PAIRES = [{ foreground: "text", background: "bg", kind: "text" as const, usage: "fake" }];

test("a style rule using an undeclared pair fails with the pair, the file and the line", () => {
  const s = source({ pairs: PAIRES });
  const css = "/* c */\n.ok {\n  color: var(--color-text);\n  background: var(--color-bg);\n}\n\n.mauvais {\n  background-color: var(--color-bg);\n  color: var(--color-amber);\n}\n";
  assert.deepEqual(controlerPairesCss(s, [{ nom: "src/styles/a.css", contenu: css }]), ["paire non déclarée : amber sur bg (src/styles/a.css:7)"]);
});

test("a rule with only one of the two, a non .css file and the generated file are not read", () => {
  const s = source({ pairs: PAIRES });
  const seule = ".a { color: var(--color-amber); }\n.b { background: var(--color-amber); }";
  assert.deepEqual(controlerPairesCss(s, [{ nom: "src/styles/a.css", contenu: seule }]), []);
  const paire = ".a { color: var(--color-amber); background: var(--color-bg); }";
  assert.deepEqual(controlerPairesCss(s, [{ nom: "src/x.ts", contenu: paire }]), []);
  assert.deepEqual(controlerPairesCss(s, [{ nom: "src/styles/tokens.css", contenu: paire }]), []);
});

test("a style variable that references a colour token is followed to it", () => {
  const s = source({ pairs: PAIRES, light: { bg: "paper", text: "ink", muet: "#112233" }, scale: { "cell-color": "{muet}" } });
  const css = ".a { color: var(--cell-color); background: var(--color-bg); }";
  assert.deepEqual(controlerPairesCss(s, [{ nom: "src/styles/a.css", contenu: css }]), ["paire non déclarée : muet sur bg (src/styles/a.css:1)"]);
});

// ---- the real source ---------------------------------------------------------------------------------------------------------

const REEL = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;

test("every declared pair of the real token source meets its threshold", () => {
  assert.deepEqual(controlerContrastes(REEL), []);
});

test("every declared pair of the real source is measured", () => {
  const mesurees = mesures(REEL);
  assert.equal(mesurees.length, REEL.pairs.length);
  assert.ok(mesurees.every((m) => m.ratio !== undefined));
  assert.ok(REEL.pairs.some((p) => p.foreground === "state-masked-border" && p.kind === "interface"));
});

test("no style rule of the front uses an undeclared colour pair", () => {
  assert.deepEqual(controlerPairesCss(REEL, sources(FRONT, "src", [".css"])), []);
});

test("the brand tokens are reserved to the logos: no style rule uses them", () => {
  const css = ".a { color: var(--color-brand-mothra); }\n.b {\n  background: var(--color-brand-pmzilla-x);\n}";
  assert.deepEqual(controlerMarquesCss([{ nom: "src/styles/a.css", contenu: css }]), [
    "jeton de marque dans une règle : src/styles/a.css:1",
    "jeton de marque dans une règle : src/styles/a.css:3",
  ]);
  assert.deepEqual(controlerMarquesCss([{ nom: "src/styles/tokens.css", contenu: css }]), []);
  assert.deepEqual(controlerMarquesCss([{ nom: "src/x.ts", contenu: css }]), []);
  assert.deepEqual(controlerMarquesCss(sources(FRONT, "src", [".css"])), []);
});

// ---- hexadecimal values, border colours, explicit references -----------------------------------------------------------------

test("a colour value that is not #RRGGBB in capitals fails with the token name, in a pair or not", () => {
  const court = source({ raw: { ink: "#16231C", paper: "#F6F2E7", court: "#FFF" }, pairs: [{ foreground: "court", background: "paper", kind: "text", usage: "fake" }] });
  assert.deepEqual(controlerContrastes(court), ["valeur de jeton invalide : court"]);
  const faux = source({ light: { bg: "paper", text: "ink", faux: "#GGGGGG" } });
  assert.deepEqual(controlerContrastes(faux), ["valeur de jeton invalide : faux"]);
  const minuscules = source({ light: { bg: "paper", text: "ink", bas: "#abcdef" } });
  assert.deepEqual(controlerContrastes(minuscules), ["valeur de jeton invalide : bas"]);
  assert.throws(() => genererCss(faux), /valeur de jeton invalide : faux/);
  assert.throws(() => genererCss(court), /valeur de jeton invalide : court/);
});

test("a border or outline colour on a background must be a declared pair, a text pair is not required", () => {
  const s = source({ pairs: PAIRES, light: { bg: "paper", text: "ink", bord: "#112233" } });
  const css = ".a { border-color: var(--color-bord); background: var(--color-bg); }\n.b { outline-color: var(--color-bord); background-color: var(--color-bg); }";
  assert.deepEqual(controlerPairesCss(s, [{ nom: "src/styles/a.css", contenu: css }]), [
    "paire non déclarée : bord sur bg (src/styles/a.css:1)",
    "paire non déclarée : bord sur bg (src/styles/a.css:2)",
  ]);
  const declaree = source({ pairs: [...PAIRES, { foreground: "bord", background: "bg", kind: "interface", usage: "fake" }], light: s.light });
  assert.deepEqual(controlerPairesCss(declaree, [{ nom: "src/styles/a.css", contenu: css }]), []);
});

test("a scale reference is written in braces, an unknown one fails in the generator, a plain word is a literal", () => {
  const s = source({ scale: { "cell-bord": "{bg}", mot: "text" } });
  const css = genererCss(s);
  assert.ok(css.includes("--cell-bord: var(--color-bg);") && css.includes("--mot: text;"));
  assert.throws(() => genererCss(source({ scale: { x: "{absent}" } })), /absent/);
  assert.throws(() => genererCss(source({ scale: { x: "{constructor}" } })), /constructor/, "no prototype key is a token");
});
