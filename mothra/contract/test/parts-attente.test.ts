// Lot 1b of mothra-demo-habillage (D3b, D14, D15, task 4.2; R-20261101-05, -20, -22, -32, -34, -43, -70 (Q163)): `partsDAttente`, the bars of the share of waiting served as
// `waitShares`. Every sheet answer comes from corpsDepuisVues applied to synthetic view rows (fiche-de-vues.ts), full or reduced by
// reduceToStatistics, never from an object written by hand.
// R-20261101-43: the tests of the markers and of the shares of the measured period, which lot 1 held in composition.test.ts, are here, each
// with its expected value, now on `waitShares`. Exception, flagged in the commit: a threshold of 1 or under had a share (0, -100) or `null`
// in lot 1; D3b (R-20261101-20) says no share, so the assertion is "no share".
import assert from "node:assert/strict";
import { test } from "node:test";
import Value from "typebox/value";

import type { CorpsFiche } from "../src/fiche.ts";
import { SchemaReponseFiche, SchemaReponseFicheReduite } from "../src/fiche-schema.ts";
import { partsDAttente } from "../src/parts-attente.ts";
import type { PartsDAttente } from "../src/parts-attente.ts";
import { reduceToStatistics } from "../src/reduction.ts";
import { DEPART_H1 } from "./depart.ts";
import { TROIS, fiche } from "./fiche-de-vues.ts";

const proche = (a: number | undefined, b: number): void => assert.ok(a !== undefined && Math.abs(a - b) < 1e-9, `${String(a)} != ${String(b)}`);

function bars(f: CorpsFiche): PartsDAttente {
  const p = partsDAttente(f);
  assert.ok(p !== undefined);
  return p;
}

// The result is fixed for given ratios and thresholds (Q151, R-20261101-32): a change of these values is an author's decision written in D34
// point 5 of mothra-slices, and changes this test in the same reviewed commit, citing it. The name says so on purpose.
test("FIXED FORMULA: a median ratio of 2.5 gives a share of waiting of 60, a P85 ratio of 2 gives 50 (a change of the formula fails this test)", () => {
  const f = fiche("lead_cycle_h1", TROIS, { lm: 25, cm: 10, lp: 40, cp: 20 });
  assert.deepEqual(f.ratios?.pooledYear?.median, { state: "value", value: 2.5 });
  assert.deepEqual(f.ratios?.pooledYear?.p85, { state: "value", value: 2 });
  const p = bars(f);
  assert.deepEqual(p.median, { state: "value", ratio: 2.5, waitShare: 60, workShare: 40 });
  assert.deepEqual(p.p85, { state: "value", ratio: 2, waitShare: 50, workShare: 50 });
});

test("the median and P85 bars come from the pooled-year ratios, each with its ratio unchanged", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10, lp: 90, cp: 20 }));
  assert.equal(p.median.state, "value");
  assert.equal(p.p85.state, "value");
  if (p.median.state === "value" && p.p85.state === "value") {
    assert.equal(p.median.ratio, 3.6);
    assert.equal(p.p85.ratio, 4.5);
    proche(p.p85.waitShare, 100 * (1 - 1 / 4.5));
  }
});

// Moved from composition.test.ts (R-20261101-43), "values": median lead time 36 and cycle time 10, shares summing to 100, expected (100 * 26) / 36.
test("values: median lead time 36 and cycle time 10 give a share of waiting of 100 x 26 / 36 and shares summing to 100", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10 }));
  assert.equal(p.median.state, "value");
  if (p.median.state === "value") {
    proche(p.median.waitShare, (100 * 26) / 36);
    proche(p.median.waitShare + p.median.workShare, 100);
  }
});

// Moved from composition.test.ts (R-20261101-43), "markers": the adopted thresholds as shares of waiting, 100 x (1 - 1/threshold).
test("markers: the adopted thresholds as ratios and as shares of waiting, 100 x (1 - 1/threshold)", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10 }));
  proche(p.markers.refutation.share, 100 * (1 - 1 / DEPART_H1.lower));
  proche(p.markers.confirmation.share, 100 * (1 - 1 / DEPART_H1.upper));
  assert.equal(p.markers.refutation.inScale, true);
  assert.equal(p.markers.confirmation.inScale, true);
  assert.equal(p.markers.refutation.ratio, DEPART_H1.lower);
  assert.equal(p.markers.confirmation.ratio, DEPART_H1.upper);
  assert.equal(p.markers.applicable, true);
});

test("thresholds of 1.5 and 2.5 are carried as the ratios 1.5 and 2.5 and their shares", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10 }, { h1_lower: 1.5, h1_upper: 2.5 }));
  assert.equal(p.markers.refutation.ratio, 1.5);
  proche(p.markers.refutation.share, 100 / 3);
  assert.deepEqual(p.markers.confirmation, { ratio: 2.5, inScale: true, share: 60 });
});

// Moved from composition.test.ts (R-20261101-43), "a threshold of 1 or under puts its marker out of scale" and "a threshold of 0 or under".
test("a threshold of 1 or under: inScale false and no share, never zero or negative; the other marker keeps its own", () => {
  const un = bars(fiche("lead_cycle_h1", TROIS, {}, { h1_lower: 1 }));
  assert.deepEqual(un.markers.refutation, { ratio: 1, inScale: false });
  assert.equal(un.markers.refutation.share, undefined);
  assert.equal(un.markers.confirmation.inScale, true);
  const moins = bars(fiche("lead_cycle_h1", TROIS, {}, { h1_lower: 0.5 }));
  assert.deepEqual(moins.markers.refutation, { ratio: 0.5, inScale: false });
  const zero = bars(fiche("lead_cycle_h1", TROIS, {}, { h1_lower: 0 }));
  assert.deepEqual(zero.markers.refutation, { ratio: 0, inScale: false });
});

test("a ratio under 1: the bar is not_comparable and has no share, never a corrected number", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lm: 8, cm: 10 }));
  assert.deepEqual(p.median, { state: "not_comparable" });
});

test("a ratio of exactly 1 is a bar of 0 waiting and 100 work", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lm: 10, cm: 10 }));
  assert.deepEqual(p.median, { state: "value", ratio: 1, waitShare: 0, workShare: 100 });
});

test("a masked P85 ratio: the P85 bar is the masked cell with its threshold and no number", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lp: "m" }));
  assert.deepEqual(p.p85, { state: "masked", threshold: 5 });
});

test("a masked median ratio: the median bar is the masked cell; on the verdict insufficient sample the other bar serves no share either", () => {
  const f = fiche("lead_cycle_h1", TROIS, { lm: "m" });
  assert.equal(f.verdict, "insufficient_sample");
  const p = bars(f);
  assert.deepEqual(p.median, { state: "masked", threshold: 5 });
  assert.deepEqual(p.p85, { state: "insufficient_sample" });
  assert.equal(p.markers.applicable, false);
});

test("an insufficient ratio (P85 of 15 items): that bar is insufficient_sample, the other keeps its value", () => {
  const f = fiche("lead_cycle_h1", TROIS, { ltN: 15, ctN: 15, lm: 36, cm: 10 });
  assert.equal(f.verdict, "not_settled");
  const p = bars(f);
  assert.equal(p.median.state, "value");
  assert.deepEqual(p.p85, { state: "insufficient_sample" });
  assert.equal(p.markers.applicable, true);
});

// Moved from composition.test.ts (R-20261101-43): on the verdict insufficient sample no share is served, markers not applicable.
test("the verdict insufficient sample: no share on any bar, even when a median is visible, and the markers are not applicable", () => {
  const f = fiche("lead_cycle_h1", TROIS, { ctN: 7, lm: 36, cm: 10 });
  assert.equal(f.verdict, "insufficient_sample");
  const p = bars(f);
  assert.deepEqual(p.median, { state: "insufficient_sample" });
  assert.deepEqual(p.p85, { state: "insufficient_sample" });
  assert.equal(p.markers.applicable, false);
  const courte = fiche("lead_cycle_h1", TROIS, { ltN: 7, ctN: 7 });
  assert.equal(courte.verdict, "insufficient_sample");
  assert.deepEqual(bars(courte).median, { state: "insufficient_sample" });
  assert.equal(bars(courte).markers.applicable, false);
});

// Moved from composition.test.ts (R-20261101-43): hypothesis 5 had no markers.
test("hypothesis 5: no waitShares, the function gives nothing", () => {
  const f = fiche("lead_cycle_h5", TROIS);
  assert.equal(f.ratios, undefined);
  assert.equal(partsDAttente(f), undefined);
  const masquee = fiche("lead_cycle_h5", [null, {}, { cm: "m" }]);
  assert.equal(partsDAttente(masquee), undefined);
});

test("waitShares is optional: absent on an answer built without the service layer, and in both schemas", () => {
  const f: CorpsFiche = fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10 });
  assert.equal(f.waitShares, undefined);
  for (const schema of [SchemaReponseFiche, SchemaReponseFicheReduite]) {
    assert.ok(Object.hasOwn(schema.properties, "waitShares"));
    assert.ok(!((schema.required as readonly string[] | undefined) ?? []).includes("waitShares"));
    assert.equal(Value.Check(schema.properties.waitShares, partsDAttente(f)), true);
  }
});

test("the schemas of waitShares refuse a field it does not declare (a count, an estimate)", () => {
  const p = bars(fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10 }));
  const schema = SchemaReponseFiche.properties.waitShares;
  assert.equal(Value.Check(schema, { ...p, items: 30 }), false);
  assert.equal(Value.Check(schema, { ...p, median: { ...p.median, items: 30 } }), false);
  assert.equal(Value.Check(schema, { ...p, median: { state: "masked", threshold: 5, value: 3 } }), false);
});

test("reduced answer: reduceToStatistics keeps the ratios, so waitShares is the same, and it holds no count", () => {
  const f = fiche("lead_cycle_h1", TROIS, { lm: 36, cm: 10, lp: 90, cp: 20 });
  const reduite = reduceToStatistics(f);
  const complet = partsDAttente(f);
  const reduit = partsDAttente(reduite);
  assert.deepEqual(reduit, complet);
  const texte = JSON.stringify(reduit);
  for (const interdit of ["items", "throughput", "coverage", "count"]) {
    assert.ok(!texte.includes(interdit), interdit);
  }
  assert.equal(Value.Check(SchemaReponseFicheReduite.properties.waitShares, reduit), true);
});

test("a frozen version read again: waitShares is recomputed from its frozen ratios and thresholds, never stored", () => {
  const f = fiche("lead_cycle_h1", TROIS, { lm: 25, cm: 10, lp: 40, cp: 20 });
  // What the freeze stores: the reduced body as the service gave it, without waitShares; read back from storage as JSON.
  const figee = JSON.parse(JSON.stringify(reduceToStatistics(f))) as CorpsFiche;
  assert.equal(figee.waitShares, undefined);
  const premiere = partsDAttente(figee);
  const seconde = partsDAttente(JSON.parse(JSON.stringify(figee)) as CorpsFiche);
  assert.deepEqual(premiere, seconde);
  assert.deepEqual(premiere?.median, { state: "value", ratio: 2.5, waitShare: 60, workShare: 40 });
  assert.deepEqual(premiere?.p85, { state: "value", ratio: 2, waitShare: 50, workShare: 50 });
  assert.equal(figee.waitShares, undefined);
});
