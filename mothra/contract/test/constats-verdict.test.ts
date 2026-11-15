// Audit #629, finding A-01 (a verdict without its reason, Q6): the contract names, in codes, why a verdict is what it is, so that the sheet
// can say it in one sentence under the badge. The codes come from the verdict functions that decide the verdict, never from a second
// computation. Starting values from ./depart.ts. Invented figures, no real data.
import assert from "node:assert/strict";
import { test } from "node:test";

import { SchemaReponseFiche, SchemaReponseFicheReduite } from "../src/fiche-schema.ts";
import { CONSTATS_DE_VERDICT } from "../src/listes-fiche.ts";
import { chargerCasVerdict, jouerCasVerdict } from "../src/parite-verdict.ts";
import { constatsFinaux, h1Evaluer, h1Verdict, h5Evaluer, h5Verdict } from "../src/verdict.ts";
import type { ConstatDeVerdict, TrimestreH5 } from "../src/verdict.ts";
import { DEPART_H1, DEPART_H5 } from "./depart.ts";

const CHEMIN = new URL("../test-data/cas-verdict.json", import.meta.url);

const q = (median: number, throughput: number | null = 100, p85 = 20): TrimestreH5 => ({ median, p85, throughput, medianSufficient: true, p85Sufficient: true });
const REFERENCE = { median: 10, p85: 20, throughput: 100 };
const stables = [q(10), q(10), q(10), q(10)];

function h1(medianRatio: number | null, p85Ratio: number | null, suffisants = { median: true, p85: true }) {
  return h1Evaluer({
    medianRatio,
    p85Ratio,
    ...DEPART_H1,
    medianSampleSufficient: suffisants.median,
    p85SampleSufficient: suffisants.p85,
  });
}

function h5(quarters: TrimestreH5[]) {
  return h5Evaluer({ quarters, reference: REFERENCE, config: DEPART_H5 });
}

test("hypothesis 1: each branch of the verdict names its finding", () => {
  assert.deepEqual(h1(1.2, 1.2), { verdict: "refuted", reasons: [], findings: ["h1_median_under_lower"] });
  assert.deepEqual(h1(2, 2), { verdict: "not_settled", reasons: [], findings: ["h1_median_in_grey_zone"] });
  assert.deepEqual(h1(3.5, 2), { verdict: "not_settled", reasons: [], findings: ["h1_p85_not_above_upper"] });
  assert.deepEqual(h1(3.5, 3.6), { verdict: "confirmed", reasons: [], findings: ["h1_above_upper"] });
  assert.deepEqual(h1(3.5, null), { verdict: "not_settled", reasons: ["p85_masked"], findings: ["h1_p85_not_readable"] });
  assert.deepEqual(h1(3.5, 3.6, { median: true, p85: false }), { verdict: "not_settled", reasons: ["p85_insufficient_sample"], findings: ["h1_p85_not_readable"] });
});

test("hypothesis 1: an insufficient sample or a masked median gives no finding, the page states that case by its own sentence", () => {
  assert.deepEqual(h1(null, 3.6), { verdict: "insufficient_sample", reasons: ["median_masked"], findings: [] });
  assert.deepEqual(h1(3.5, 3.6, { median: false, p85: true }), { verdict: "insufficient_sample", reasons: ["median_insufficient_sample"], findings: [] });
});

test("hypothesis 5: a refutation names every cause it holds, in a fixed order", () => {
  const basse = h5([q(10), q(10), q(10), q(10, 50)]);
  assert.equal(basse.verdict, "refuted");
  assert.deepEqual(basse.findings, ["h5_under_low_floor"]);
  const doubleBande = h5([q(10), q(10, 100, 40), q(10), q(10, 100, 40)]);
  assert.equal(doubleBande.verdict, "refuted");
  assert.deepEqual(doubleBande.findings, ["h5_double_band"]);
  const serie = h5([q(10), q(10.6), q(11.2), q(11.8)]);
  assert.equal(serie.verdict, "refuted");
  assert.deepEqual(serie.findings, ["h5_rising_run"]);
  const les3 = h5([q(10), q(14, 100, 28), q(18, 100, 36), q(22, 50, 44)]);
  assert.equal(les3.verdict, "refuted");
  assert.deepEqual(les3.findings, ["h5_double_band", "h5_rising_run", "h5_under_low_floor"]);
});

test("hypothesis 5: not settled names the quarter condition, confirmed names the band, a masked throughput leaves its own reason", () => {
  assert.deepEqual(h5([q(10), q(10), q(10), q(10, 70)]).findings, ["h5_under_floor"]);
  assert.deepEqual(h5([q(10), q(10), q(10), q(12.5)]).findings, ["h5_out_of_band"]);
  assert.deepEqual(h5([q(10), q(10), q(10), q(12.5, 70)]).findings, ["h5_out_of_band", "h5_under_floor"]);
  assert.deepEqual(h5(stables).findings, ["h5_within_band"]);
  const masque = h5([q(10), q(10), q(10), q(10, null)]);
  assert.equal(masque.verdict, "not_settled");
  assert.deepEqual(masque.reasons, ["throughput_masked"]);
  assert.deepEqual(masque.findings, []);
});

test("no reference, or nothing to compare, gives no finding", () => {
  assert.deepEqual(h5Evaluer({ quarters: stables, reference: null, config: DEPART_H5 }).findings, []);
  const rien: TrimestreH5 = { median: 0, p85: 0, throughput: null, medianSufficient: false, p85Sufficient: false };
  assert.deepEqual(h5Evaluer({ quarters: [rien, rien, rien, rien], reference: REFERENCE, config: DEPART_H5 }).findings, []);
});

test("the verdict functions keep their result: the finding is an addition, not a change", () => {
  const complet1 = h1(3.5, 2);
  assert.deepEqual(h1Verdict({ medianRatio: 3.5, p85Ratio: 2, ...DEPART_H1, medianSampleSufficient: true, p85SampleSufficient: true }), { verdict: complet1.verdict, reasons: complet1.reasons });
  const complet5 = h5([q(10), q(10), q(10), q(10, 50)]);
  assert.deepEqual(h5Verdict({ quarters: [q(10), q(10), q(10), q(10, 50)], reference: REFERENCE, config: DEPART_H5 }), {
    verdict: complet5.verdict,
    excluded: complet5.excluded,
    reasons: complet5.reasons,
  });
});

test("a confirmation barred by a competing explanation says so, in place of the finding of the figures", () => {
  assert.deepEqual(constatsFinaux({ raw: "confirmed", findings: ["h1_above_upper"], final: "not_settled" }), ["confirmation_barred"]);
  assert.deepEqual(constatsFinaux({ raw: "confirmed", findings: ["h5_within_band"], final: "confirmed" }), ["h5_within_band"]);
  assert.deepEqual(constatsFinaux({ raw: "refuted", findings: ["h5_under_low_floor"], final: "refuted" }), ["h5_under_low_floor"]);
  assert.deepEqual(constatsFinaux({ raw: "not_settled", findings: ["h1_median_in_grey_zone"], final: "not_settled" }), ["h1_median_in_grey_zone"]);
  assert.deepEqual(constatsFinaux({ raw: "insufficient_sample", findings: [], final: "insufficient_sample" }), []);
});

test("the closed list holds every code the functions can give, once, and nothing else", () => {
  const donnes = new Set<ConstatDeVerdict>();
  for (const r of [h1(1.2, 1.2), h1(2, 2), h1(3.5, 2), h1(3.5, 3.6), h1(3.5, null)]) r.findings.forEach((c) => donnes.add(c));
  for (const r of [
    h5([q(10), q(10), q(10), q(10, 50)]),
    h5([q(10), q(10, 100, 40), q(10), q(10, 100, 40)]),
    h5([q(10), q(10.6), q(11.2), q(11.8)]),
    h5([q(10), q(10), q(10), q(10, 70)]),
    h5([q(10), q(10), q(10), q(12.5)]),
    h5(stables),
  ]) {
    r.findings.forEach((c) => donnes.add(c));
  }
  donnes.add("confirmation_barred");
  assert.deepEqual([...donnes].sort(), [...CONSTATS_DE_VERDICT].sort());
  assert.equal(new Set(CONSTATS_DE_VERDICT).size, CONSTATS_DE_VERDICT.length);
});

test("the answer schemas declare the findings as a list of codes, optional, and still refuse an undeclared field", () => {
  for (const schema of [SchemaReponseFiche, SchemaReponseFicheReduite]) {
    const forme = schema as unknown as { properties: Record<string, unknown>; required?: readonly string[]; additionalProperties?: unknown };
    assert.ok("verdictFindings" in forme.properties, "verdictFindings déclaré");
    assert.ok(!(forme.required ?? []).includes("verdictFindings"), "facultatif : une version figée plus ancienne n'en porte pas");
    assert.equal(forme.additionalProperties, false);
  }
});

test("the shared verdict cases hold the cases of the findings", () => {
  const cas = chargerCasVerdict(CHEMIN);
  const fonctions = new Set(cas.map((c) => c.fn));
  for (const f of ["h1Evaluer", "h5Evaluer", "constatsFinaux"]) assert.ok(fonctions.has(f), f);
  jouerCasVerdict(cas.filter((c) => ["h1Evaluer", "h5Evaluer", "constatsFinaux"].includes(c.fn)));
});
