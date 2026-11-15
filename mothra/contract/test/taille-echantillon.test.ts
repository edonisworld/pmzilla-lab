// Task 22.1 (D16, "Sample size of H1", R-20261106-18; R-20261105-30): the sample size of H1 is a pure function of the published cells, never published itself.
// items_lt (lead time) or items_ct (cycle time) minus items_old when both are shown; no size (the verdict "insufficient sample") when either is masked, whatever
// the rule that masked it: no lower bound is taken. Python counterpart: `taille_echantillon_h1` of tools/flow_views.py (parity cases H1a to H1c of
// contrats/cas-masquage.json, played by cas-masquage.test.ts).
import assert from "node:assert/strict";
import { test } from "node:test";

import { tailleEchantillonH1 } from "../src/taille-echantillon.ts";

const valeur = (value: number) => ({ state: "value" as const, value });
const masquee = { state: "masked" as const, threshold: 5 };

test("both cells shown: the count minus items_old, for the lead time and for the cycle time", () => {
  assert.equal(tailleEchantillonH1("lead", { items_lt: valeur(20), items_ct: valeur(18), items_old: valeur(6) }), 14);
  assert.equal(tailleEchantillonH1("cycle", { items_lt: valeur(20), items_ct: valeur(18), items_old: valeur(6) }), 12);
});

test("a shown zero of items_old gives the whole count", () => {
  assert.equal(tailleEchantillonH1("lead", { items_lt: valeur(20), items_ct: valeur(20), items_old: { state: "value", value: 0 } }), 20);
});

test("items_old masked: no size, whatever the count, even when the remainder looks large (no lower bound)", () => {
  assert.equal(tailleEchantillonH1("lead", { items_lt: valeur(20), items_ct: valeur(20), items_old: masquee }), null);
  assert.equal(tailleEchantillonH1("cycle", { items_lt: valeur(20), items_ct: valeur(20), items_old: masquee }), null);
});

test("the count masked: no size", () => {
  assert.equal(tailleEchantillonH1("lead", { items_lt: masquee, items_ct: valeur(30), items_old: valeur(6) }), null);
  assert.equal(tailleEchantillonH1("cycle", { items_lt: masquee, items_ct: valeur(30), items_old: valeur(6) }), 24);
});

test("a missing cell is no size, an unknown kind is refused", () => {
  assert.equal(tailleEchantillonH1("lead", { items_lt: valeur(20) }), null);
  assert.throws(() => tailleEchantillonH1("other" as "lead", { items_lt: valeur(20), items_ct: valeur(20), items_old: valeur(6) }), TypeError);
});
