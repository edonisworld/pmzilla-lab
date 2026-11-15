// Audit #629, A-63 (L3-04, R-20261107-20 order 4): the bounds of the thresholds, the closed list of the codes, the pair that stays ordered.
import assert from "node:assert/strict";
import { test } from "node:test";

import { BORNES_SEUILS, codeDeSeuilConnu, couplesIncoherents, seuilDansLesBornes } from "../src/bornes-seuils.ts";
import { SeuilsIncoherents, TOUS_LES_CODES_SEUILS, lireSeuils } from "../src/corps-fiche.ts";
import { PLANCHER } from "../src/plancher.ts";

test("les bornes couvrent exactement la liste fermée CODES_SEUILS (source : listes-fiche.ts)", () => {
  assert.deepEqual(Object.keys(BORNES_SEUILS).sort(), [...TOUS_LES_CODES_SEUILS].sort());
  assert.equal(codeDeSeuilConnu("code_invente"), false);
  assert.equal(codeDeSeuilConnu("toString"), false);
});

test("une taille d'échantillon n'est jamais sous le plancher du contrat, ni fractionnaire", () => {
  for (const code of ["sample_median_min_items", "sample_p85_min_items"]) {
    assert.equal(seuilDansLesBornes(code, 0), false, code);
    assert.equal(seuilDansLesBornes(code, PLANCHER - 1), false, code);
    assert.equal(seuilDansLesBornes(code, 7.5), false, code);
    assert.equal(seuilDansLesBornes(code, PLANCHER), true, code);
    assert.equal(seuilDansLesBornes(code, 20), true, code);
  }
});

test("les valeurs de départ des fiches sont dans les bornes", () => {
  const depart: Array<[string, number]> = [
    ["h5_band", 0.2], ["h5_double_band", 0.4], ["h5_run_rises", 2], ["h5_run_min_cumulative_rise", 0.1], ["h5_floor", 0.8], ["h5_low_floor", 0.6],
    ["h1_lower", 1.5], ["h1_upper", 3], ["attachment_threshold_points", 10], ["sample_median_min_items", 10], ["sample_p85_min_items", 20],
  ];
  for (const [code, valeur] of depart) assert.equal(seuilDansLesBornes(code, valeur), true, code);
  assert.equal(seuilDansLesBornes("h5_band", Number.NaN), false);
  assert.equal(seuilDansLesBornes("h5_band", Number.POSITIVE_INFINITY), false);
});

test("un historique dont le couple bas >= haut est déjà écrit donne SeuilsIncoherents, jamais un RangeError", () => {
  const historique = [
    { code: "h1_lower", value: 5, setOn: "2026-10-30" },
    { code: "h1_upper", value: 2, setOn: "2026-10-30" },
  ];
  assert.deepEqual(couplesIncoherents(historique), ["h1_lower", "h1_upper"]);
  assert.throws(() => lireSeuils(historique, ["h1_lower", "h1_upper"], null), SeuilsIncoherents);
  assert.deepEqual(couplesIncoherents([{ code: "h1_lower", value: 1.5, setOn: "2026-10-30" }, { code: "h1_upper", value: 3, setOn: "2026-10-30" }]), []);
});

test("R-20261107-29 décision 7 : les couples H5 sont ordonnés au sens large (l'égalité est permise), le couple H1 reste strict", () => {
  const ecrit = (code: string, value: number) => ({ code, value, setOn: "2026-10-30" });
  assert.deepEqual(couplesIncoherents([ecrit("h5_band", 0.5), ecrit("h5_double_band", 0.4)]), ["h5_band", "h5_double_band"]);
  assert.deepEqual(couplesIncoherents([ecrit("h5_band", 0.4), ecrit("h5_double_band", 0.4)]), []);
  assert.deepEqual(couplesIncoherents([ecrit("h5_low_floor", 0.9), ecrit("h5_floor", 0.8)]), ["h5_low_floor", "h5_floor"]);
  assert.deepEqual(couplesIncoherents([ecrit("h5_low_floor", 0.8), ecrit("h5_floor", 0.8)]), []);
  assert.deepEqual(couplesIncoherents([ecrit("h1_lower", 2), ecrit("h1_upper", 2)]), ["h1_lower", "h1_upper"]);
});

test("une dernière valeur hors bornes (taille à 0 écrite avant le contrôle) donne SeuilsIncoherents, jamais un garde-fou levé", () => {
  const historique = [{ code: "sample_median_min_items", value: 0, setOn: "2026-10-30" }];
  assert.throws(() => lireSeuils(historique, ["sample_median_min_items"], null), SeuilsIncoherents);
  // Only the latest value counts: a former value outside the bounds, replaced by a valid one, is read.
  const corrige = [...historique, { code: "sample_median_min_items", value: 10, setOn: "2026-11-01" }];
  assert.equal(lireSeuils(corrige, ["sample_median_min_items"], null)[0].value, 10);
});
