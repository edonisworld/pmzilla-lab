// The table of the state patterns, as data in tokens.json (author's decision of 2026-10-27): for each state and verdict an outline, an
// icon and a label, so that no two states share the same look. Colour never carries a state alone.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { controlerContrastes, controlerEtats, controlerStyles, mesures } from "./jetons.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const REEL = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;

function source(etats: Record<string, { outline?: string; icon: string }>): Jetons {
  return {
    raw: {},
    derived: {},
    light: {},
    scale: {},
    pairs: [],
    states: Object.fromEntries(Object.entries(etats).map(([j, e]) => [j, { label: "x", ...e }])),
  };
}

test("two states with the same outline and the same icon fail, naming both tokens", () => {
  const s = source({ "state-a": { outline: "dotted", icon: "dots" }, "state-b": { outline: "dotted", icon: "dots" }, "state-c": { outline: "solid", icon: "dots" } });
  assert.deepEqual(controlerStyles(s), ["styles confondus : state-a et state-b"]);
  const trois = source({ "state-a": { outline: "solid", icon: "x" }, "state-b": { outline: "solid", icon: "x" }, "state-c": { outline: "solid", icon: "x" } });
  assert.deepEqual(controlerStyles(trois), ["styles confondus : state-a et state-b", "styles confondus : state-a et state-c", "styles confondus : state-b et state-c"]);
});

test("a different outline or a different icon is enough to tell two states apart", () => {
  assert.deepEqual(controlerStyles(source({ "state-a": { outline: "solid", icon: "x" }, "state-b": { outline: "dashed", icon: "x" } })), []);
  assert.deepEqual(controlerStyles(source({ "state-a": { outline: "solid", icon: "x" }, "state-b": { outline: "solid", icon: "y" } })), []);
});

test("a state without an outline fails and names the token", () => {
  assert.deepEqual(controlerStyles(source({ "state-a": { icon: "x" } })), ["contour manquant : state-a"]);
  assert.deepEqual(controlerStyles(source({ "state-a": { outline: " ", icon: "x" } })), ["contour manquant : state-a"]);
});

test("the real table: outline, icon and label of each state and verdict", () => {
  const table = Object.fromEntries(Object.entries(REEL.states).map(([j, e]) => [j, [e.outline, e.icon, e.label]]));
  assert.deepEqual(table, {
    "verdict-confirmed": ["solid", "check", "verdict.confirmed"],
    "verdict-refuted": ["solid", "cross", "verdict.refuted"],
    "verdict-not-settled": ["solid", "tilde", "verdict.not_settled"],
    "state-masked": ["dashed", "none", "cellState.masked"],
    "state-insufficient": ["dotted", "ellipsis", "state.insufficient_sample"],
    "state-error": ["solid", "alert", "state.error"],
    "state-loading": ["none", "indicator", "page.loading"],
    "state-in-progress": ["double", "clock", "state.in_progress"],
    "state-not-tested": ["solid", "circle-empty", "state.not_tested"],
    "state-partial-evidence": ["hatched", "info", "state.partial_evidence_signals"],
  });
  assert.deepEqual(controlerStyles(REEL), []);
  assert.deepEqual(controlerEtats(REEL, catalogues), []);
});

test("a fake state-in-progress in dotted and ellipsis fails against state-insufficient, in the order of the section", () => {
  const faux: Jetons = { ...REEL, states: { ...REEL.states, "state-in-progress": { label: "state.in_progress", icon: "ellipsis", outline: "dotted" } } };
  assert.deepEqual(controlerStyles(faux), ["styles confondus : state-insufficient et state-in-progress"]);
});

test("the outline is compared without regard to case: Solid and solid are the same look", () => {
  assert.deepEqual(controlerStyles(source({ "state-a": { outline: "Solid", icon: "x" }, "state-b": { outline: "solid", icon: "x" } })), ["styles confondus : state-a et state-b"]);
});

test("the masked cell stays in italics: the token is italic and styles.css uses it", () => {
  assert.equal(REEL.scale["cell-masked-font-style"], "italic");
  assert.match(readFileSync(`${FRONT}src/styles/styles.css`, "utf8"), /font-style:\s*var\(--cell-masked-font-style\)/);
});

test("no link shape is left in tokens.json nor in the style sheets (D32): the state is carried by outline, icon and label", () => {
  const LIEN = /full-link|half-filled-link|hatched-info-link|link-shape|forme de lien/i;
  const fichiers = [`${FRONT}src/styles/tokens.json`, `${FRONT}src/styles/tokens.css`, ...readdirSync(`${FRONT}src/styles`).filter((f) => f.endsWith(".css")).map((f) => `${FRONT}src/styles/${f}`)];
  for (const f of fichiers) assert.doesNotMatch(readFileSync(f, "utf8"), LIEN, f);
  for (const [j, e] of Object.entries(REEL.states)) assert.deepEqual(Object.keys(e).sort(), ["icon", "label", "outline"], j);
});

test("the new states are in both catalogues, with the labels of D29", () => {
  assert.deepEqual(
    [catalogues.en["state.in_progress"], catalogues.en["state.not_tested"], catalogues.en["state.partial_evidence_signals"]],
    ["in progress", "not tested", "partial evidence, signals"],
  );
  assert.deepEqual(
    [catalogues.fr["state.in_progress"], catalogues.fr["state.not_tested"], catalogues.fr["state.partial_evidence_signals"]],
    ["en cours", "non testée", "preuve partielle, signaux"],
  );
});

test("the new states have their colour token and their declared pairs, which all meet their threshold", () => {
  for (const j of ["state-in-progress", "state-not-tested", "state-partial-evidence"]) assert.ok(Object.hasOwn(REEL.light, j), j);
  assert.equal(REEL.light["state-partial-evidence"], "info");
  const paires = (j: string) => REEL.pairs.filter((p) => p.foreground === j).map((p) => [p.background, p.kind]);
  assert.deepEqual(paires("state-in-progress"), [["surface", "interface"]]);
  assert.deepEqual(paires("state-not-tested"), [["surface", "interface"]]);
  assert.deepEqual(paires("state-partial-evidence"), [["bg", "text"], ["surface", "text"]]);
  assert.deepEqual(controlerContrastes(REEL), []);
  assert.ok(mesures(REEL).every((m) => m.ratio !== undefined));
});
