// Task 19.5 (A1, A3): the throughput positions and the coverage state of the reduced form (design D34, D29). Pure functions of the
// verdict service; the floors come from the caller. Invented figures.
import assert from "node:assert/strict";
import { test } from "node:test";

import { coverageState, h5Verdict, throughputPositions } from "../src/verdict.ts";
import { DEPART_ECHANTILLON, DEPART_H5 } from "./depart.ts";

const { floor, lowFloor } = DEPART_H5; // 0.8 and 0.6
const REF = 100;
const position = (debit: number | null) => throughputPositions({ quarters: [{ quarter: "2026-Q3", throughput: debit }], reference: REF, floor, lowFloor })[0].position;

test("exactly at the floor: within the band; just under: under the floor", () => {
  assert.equal(position(80), "throughput_within_band");
  assert.equal(position(79), "throughput_under_floor");
});

test("exactly at the low floor: under the floor; just under: under the low floor", () => {
  assert.equal(position(60), "throughput_under_floor");
  assert.equal(position(59), "throughput_under_low_floor");
});

test("a masked throughput gives masked, never an estimate", () => {
  assert.equal(position(null), "masked");
});

test("no reference: no position at all (R-20261031-01, Q11 (a)); the verdict stays insufficient sample", () => {
  assert.deepEqual(throughputPositions({ quarters: [{ quarter: "2026-Q3", throughput: 50 }], reference: null, floor, lowFloor }), []);
});

test("a position is a code: no number, no percentage, whatever the input", () => {
  const positions = throughputPositions({
    quarters: [
      { quarter: "2026-Q1", throughput: 7919 },
      { quarter: "2026-Q2", throughput: 3 },
      { quarter: "2026-Q3", throughput: null },
    ],
    reference: 6007,
    floor,
    lowFloor,
  });
  assert.equal(positions.length, 3);
  for (const p of positions) {
    assert.deepEqual(Object.keys(p).sort(), ["position", "quarter"]);
    assert.equal(typeof p.quarter, "string");
    assert.equal(typeof p.position, "string");
    assert.ok(!/[0-9]/.test(p.position), "no figure in a position");
  }
});

test("parity with the verdict: a position under the low floor is what refutes hypothesis 5, a position within the band never does", () => {
  const trimestre = (throughput: number) => ({ median: 10, p85: 20, throughput, medianSufficient: true, p85Sufficient: true });
  const reference = { median: 10, p85: 20, throughput: REF };
  for (const debit of [59, 60, 79, 80, 100]) {
    const verdict = h5Verdict({ quarters: [trimestre(debit)], reference, config: DEPART_H5 }).verdict;
    const pos = position(debit);
    assert.equal(verdict === "refuted", pos === "throughput_under_low_floor", String(debit));
    assert.equal(verdict === "confirmed", pos === "throughput_within_band", String(debit));
  }
});

test("coverage state: exactly at the P85 size is sufficient, one under insufficient, a masked cell masked", () => {
  const taille = DEPART_ECHANTILLON.p85MinItems;
  assert.equal(coverageState({ state: "value", value: taille }, taille), "coverage_sufficient");
  assert.equal(coverageState({ state: "value", value: taille - 1 }, taille), "coverage_insufficient");
  assert.equal(coverageState({ state: "masked", threshold: 5 }, taille), "coverage_masked");
});
