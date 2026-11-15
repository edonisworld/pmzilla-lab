// Colour-vision rule of design D32 (author's decision of 2026-10-27): the three verdict colours differ in lightness (CIELAB L*, D65),
// not only in hue, so that they stay distinct under protanopia and deuteranopia; "confirmed" never gets close to the ink of the text.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { controlerContrastes, controlerEncre, controlerLuminosites, ECART_L_MINIMUM, luminosites } from "./jetons.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const REEL = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;

function source(light: Record<string, string>): Jetons {
  const etat = { label: "x", icon: "x", outline: "solid" };
  return { raw: {}, derived: {}, light, scale: {}, pairs: [], states: Object.fromEntries(Object.keys(light).map((j) => [j, etat])) };
}

test("the minimum lightness gap is a named parameter of 15", () => {
  assert.equal(ECART_L_MINIMUM, 15);
});

test("L* of black, white and a mid grey (sRGB, D65)", () => {
  const l = luminosites(source({ "verdict-a": "#000000", "verdict-b": "#FFFFFF", "verdict-c": "#777777" }));
  assert.equal(l["verdict-a"], 0);
  assert.ok(Math.abs(l["verdict-b"] - 100) < 1e-9);
  assert.ok(Math.abs(l["verdict-c"] - 50.0) < 0.2);
});

test("two verdict colours closer than the gap fail, naming both tokens and the gap truncated to two decimals", () => {
  const proches = source({ "verdict-a": "#0E6E63", "verdict-b": "#555B57", "verdict-c": "#5B3FA0" });
  const trouves = controlerLuminosites(proches);
  assert.equal(trouves.length, 3);
  assert.match(trouves[0], /^luminosités trop proches : verdict-a et verdict-b \(ΔL\* \d+\.\d\d < 15\)$/);
  assert.match(trouves[1], /^luminosités trop proches : verdict-a et verdict-c \(ΔL\* /);
  assert.deepEqual(controlerLuminosites(source({ "verdict-a": "#000000", "verdict-b": "#777777", "verdict-c": "#FFFFFF" })), []);
});

test("the error colour is not part of the lightness comparison (its contrast is tested elsewhere)", () => {
  assert.deepEqual(controlerLuminosites(source({ "verdict-a": "#0E6E63", "state-error": "#0E6E63" })), []);
  assert.deepEqual(Object.keys(luminosites(source({ "verdict-a": "#0E6E63", "state-error": "#B42318" }))), ["verdict-a"]);
});

test("confirmed keeps at least 15 L* from the ink of the text, failing with the token and the gap", () => {
  const encre = (confirmee: string) => source({ text: "#16231C", "verdict-confirmed": confirmee });
  assert.deepEqual(controlerEncre(encre("#0E6E63")), []);
  assert.deepEqual(controlerEncre(encre("#04221E")).map((m) => m.replace(/\d+\.\d\d/, "N")), ["verdict trop proche de l'encre : verdict-confirmed (ΔL* N < 15)"]);
  assert.match(controlerEncre(encre("#04221E"))[0], /^verdict trop proche de l'encre : verdict-confirmed \(ΔL\* \d+\.\d\d < 15\)$/);
  assert.deepEqual(controlerEncre(encre("#04221E"), 1), []);
  assert.deepEqual(controlerEncre(source({ "verdict-a": "#000000" })), []);
});

test("the gap is a parameter: a smaller threshold admits a pair the default refuses", () => {
  const s = source({ "verdict-a": "#000000", "verdict-b": "#202020" });
  assert.equal(controlerLuminosites(s).length, 1);
  assert.deepEqual(controlerLuminosites(s, 5), []);
});

test("states that are not a verdict (the error, masked and loading states) are not compared", () => {
  assert.deepEqual(controlerLuminosites(source({ "verdict-a": "#000000", "state-masked": "#010101", "state-loading": "#000000" })), []);
});

test("the real verdicts differ in lightness by at least 15 L*, and confirmed keeps 15 L* from the ink", () => {
  assert.deepEqual(controlerLuminosites(REEL), []);
  assert.deepEqual(controlerEncre(REEL), []);
});

test("the lightness of the real verdict colours, one decimal (refuted darkest, confirmed mid, not settled mid grey)", () => {
  const l = luminosites(REEL);
  const arrondi = Object.fromEntries(Object.entries(l).map(([j, v]) => [j, Math.round(v * 10) / 10]));
  assert.deepEqual(arrondi, { "verdict-confirmed": 41.4, "verdict-refuted": 21.4, "verdict-not-settled": 59.8 });
  assert.ok(l["verdict-refuted"] < l["verdict-confirmed"] && l["verdict-confirmed"] < l["verdict-not-settled"]);
});

test("the real refuted colour stays violet and the real confirmed colour stays blue-green, the error stays far from the amber", () => {
  assert.equal(REEL.light["verdict-confirmed"], "#0E6E63");
  assert.equal(REEL.light["verdict-refuted"], "#3B2470");
  assert.equal(REEL.light["verdict-not-settled"], "#909090");
});

test("not settled is a mid grey shown with a border: its pair against the surface is of kind interface, 3:1 at least", () => {
  const paires = REEL.pairs.filter((p) => p.foreground === "verdict-not-settled");
  assert.deepEqual(paires.map((p) => [p.background, p.kind]), [["surface", "interface"]]);
  assert.deepEqual(controlerContrastes(REEL), []);
});
