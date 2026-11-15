// Task 22.1 (D16, "Grouped year without the old items", R-20261105-30, R-20261106-58): the four statistics without the old items of
// v_team_lead_time_throughput, in the contract and in `masquerVue`. Masked with their headcount (items_lt for the lead time, items_ct for the cycle time), and
// masked unless items_old of the row is shown and the headcount minus items_old reaches the threshold; a NULL is a masked cell. Python counterpart:
// tests/flow_views/test_stats_sans_anciens.py (same rule, `masquer_vue`). Invented rows (team A).
import assert from "node:assert/strict";
import { test } from "node:test";

import { chargerContrat } from "../src/chargeur.ts";
import { type LigneBrute, masquerVue } from "../src/masquage.ts";
import type { Vue } from "../src/vues.ts";

const CONTRAT = chargerContrat(new URL("../../../contrats/vues.json", import.meta.url));
const VUE = CONTRAT.views.find((v) => v.name === "v_team_lead_time_throughput") as Vue;
const NOUVELLES = ["lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old"];

function ligne(n: number, m: number, c: number, o: number, stats: (number | null)[] = [2, 6, 3, 7]): LigneBrute {
  return {
    team: "A", period: "quarter", quarter_start: "2026-01-01", throughput: n, items_lt: m, lead_median_days: 3, lead_p85_days: 9, items_ct: c,
    cycle_median_days: 4, cycle_p85_days: 8, items_old: o, items_without_commitment: n - c,
    lead_median_days_excl_old: stats[0], lead_p85_days_excl_old: stats[1], cycle_median_days_excl_old: stats[2], cycle_p85_days_excl_old: stats[3],
  };
}

const masquee = (x: unknown): boolean => typeof x === "object" && x !== null && (x as { state: string }).state === "masked";

test("the contract lists the four columns after the existing statistics and adds no count", () => {
  assert.deepEqual(VUE.maskableColumns, ["lead_median_days", "lead_p85_days", "cycle_median_days", "cycle_p85_days", ...NOUVELLES]);
  assert.deepEqual(VUE.countColumns, ["throughput", "items_lt", "items_ct", "items_old", "items_without_commitment"]);
});

test("items_old shown and the remainder at the threshold: the four statistics are shown", () => {
  for (const [seuil, o] of [[5, 6], [5, 0], [10, 0], [10, 10]] as const) {
    const [r] = masquerVue(VUE, [ligne(30, 30, 30, o)], seuil);
    assert.equal(masquee(r.items_old), false, `${seuil} ${o}`);
    NOUVELLES.forEach((nom, k) => assert.deepEqual(r[nom], { state: "value", value: [2, 6, 3, 7][k] }, `${seuil} ${o} ${nom}`));
  }
});

test("items_old masked: the four statistics are masked even when the remainder looks large", () => {
  const [r] = masquerVue(VUE, [ligne(20, 20, 20, 3)], 5);
  assert.equal(masquee(r.items_old), true);
  for (const nom of NOUVELLES) assert.equal(masquee(r[nom]), true, nom);
});

test("a remainder under the threshold, or none, masks the statistic", () => {
  for (const nom of NOUVELLES) assert.equal(masquee(masquerVue(VUE, [ligne(12, 12, 12, 6)], 10)[0][nom]), true, nom);
  for (const nom of NOUVELLES) assert.equal(masquee(masquerVue(VUE, [ligne(20, 20, 20, 20)], 5)[0][nom]), true, nom);
});

test("a masked headcount masks its statistics only", () => {
  const [r] = masquerVue(VUE, [ligne(40, 7, 30, 0)], 10);
  assert.equal(masquee(r.items_lt), true);
  assert.equal(masquee(r.lead_median_days_excl_old), true);
  assert.equal(masquee(r.lead_p85_days_excl_old), true);
  assert.deepEqual(r.cycle_median_days_excl_old, { state: "value", value: 3 });
  assert.deepEqual(r.cycle_p85_days_excl_old, { state: "value", value: 7 });
});

test("a NULL statistic is a masked cell, and the existing statistics are untouched", () => {
  const [r] = masquerVue(VUE, [ligne(30, 30, 30, 3, [null, null, null, null])], 5);
  for (const nom of NOUVELLES) assert.equal(masquee(r[nom]), true, nom);
  assert.deepEqual(r.lead_median_days, { state: "value", value: 3 });
  assert.deepEqual(r.cycle_p85_days, { state: "value", value: 8 });
});
