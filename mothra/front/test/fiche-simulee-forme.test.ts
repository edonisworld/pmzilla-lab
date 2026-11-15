// R-20261031-61, Q114: `ficheSimulee()` (fiche-simulee.ts) stays as RENDER STATES, not as an answer of the server. This test compares its keys
// and the shape of its `method.scope` to a real body, built by `corpsDepuisVues` from masked synthetic views (reponses-contrat.ts), so that a
// key added to or removed from the body of the contract is noticed here. The values are not compared: the states are invented.
import assert from "node:assert/strict";
import { test } from "node:test";

import { ficheSimulee } from "./fiche-simulee.ts";
import { corpsReel } from "./reponses-contrat.ts";

// Keys the service adds to the body of the contract (`CorpsDepuisVues` omits them): the identifier, the state, the two free texts.
const AJOUTEES_PAR_LE_SERVICE = ["id", "state", "effect", "cause"];
// Keys of the body that the contract declares optional ("a body without chart figures stays valid"): the simulated states carry none of them.
const FIGURES_FACULTATIVES = ["chart", "p85", "throughputPositions", "ratios", "dataset"];

const simulee = ficheSimulee();
const reel = corpsReel("lead_cycle_h5");
const clesReelles = Object.keys(reel);

test("every key of the simulated sheet is a key of a real body (or one the service adds)", () => {
  const inconnues = Object.keys(simulee).filter((cle) => !clesReelles.includes(cle) && !AJOUTEES_PAR_LE_SERVICE.includes(cle));
  assert.deepEqual(inconnues, [], "clé de ficheSimulee() absente du corps réel : mettre fiche-simulee.ts à jour");
});

test("every key of a real body is in the simulated sheet, but the optional figures the contract declares", () => {
  const manquantes = clesReelles.filter((cle) => !(cle in simulee) && !FIGURES_FACULTATIVES.includes(cle));
  assert.deepEqual(manquantes, [], "clé du corps réel absente de ficheSimulee() : mettre fiche-simulee.ts à jour");
});

test("a key present in both has the same kind of value (text, number, list, object)", () => {
  const genre = (v: unknown): string => (Array.isArray(v) ? "list" : v === null ? "null" : typeof v);
  for (const cle of clesReelles.filter((c) => c in simulee)) {
    assert.equal(genre((simulee as unknown as Record<string, unknown>)[cle]), genre((reel as unknown as Record<string, unknown>)[cle]), cle);
  }
});

test("the keys of the simulated method are the keys of the real method", () => {
  assert.deepEqual(Object.keys(simulee.method).sort(), Object.keys(reel.method).sort());
});

test("the scope of the simulated method has the shape of the real one: a level and an identifier, both text", () => {
  assert.deepEqual(Object.keys(simulee.method.scope).sort(), Object.keys(reel.method.scope).sort());
  assert.deepEqual(Object.keys(reel.method.scope).sort(), ["id", "level"]);
  assert.equal(typeof simulee.method.scope.id, "string");
  assert.equal(typeof reel.method.scope.id, "string");
  assert.equal(simulee.method.scope.level, reel.method.scope.level);
  assert.ok(["team", "product"].includes(simulee.method.scope.level));
  // the real identifier is the scope code of the sheet, `team.<opaque identifier>`, never a team name
  assert.match(reel.method.scope.id, /^team\.[a-z0-9_-]{1,59}$/);
});

// The known gap of value, stated: the simulated identifier is a name-like text, the real one a scope code. The sheet screen renders either
// as received, so no existing render test depends on it; changing it is the author's call (it would change what those tests render).
test("known gap: the simulated scope.id is not a scope code, the real one is", () => {
  assert.equal(simulee.method.scope.id, "team A");
  assert.doesNotMatch(simulee.method.scope.id, /^team\.[a-z0-9_-]{1,59}$/);
});
