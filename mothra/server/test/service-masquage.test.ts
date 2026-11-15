// Task 15.3: the server applies the masking of the contract package to every view it serves, at one point (composerReponse).
import assert from "node:assert/strict";
import { test } from "node:test";

import { chargerContrat, estReponseVue, schemaReponseDeVue } from "@mothra/contract";
import type { Cellule } from "@mothra/contract";
import { servirVue } from "@mothra/contract";
import Value from "typebox/value";

import { composerReponse, lireVueMasquee } from "../src/service.ts";

const CONTRAT = chargerContrat(new URL("../../../contrats/vues.json", import.meta.url));

function vue(nom: string) {
  const v = CONTRAT.views.find((x) => x.name === nom);
  assert.ok(v, nom);
  return v;
}

test("the lead time view is masked by the pair and series rules at a raised threshold, counts read as bigint or digit strings", () => {
  const v = vue("v_team_lead_time_throughput");
  const ligne = {
    team: "A", period: "quarter", quarter_start: "2026-01-01", throughput: 20n, items_lt: "15", lead_median_days: 3, lead_p85_days: 9,
    items_ct: 6, cycle_median_days: 4, cycle_p85_days: 8, items_old: 0, items_without_commitment: 14,
  };
  const reponse = composerReponse(v, [ligne], 10);
  assert.ok(estReponseVue(reponse));
  assert.ok(Value.Check(schemaReponseDeVue(v), servirVue(reponse, { afficherNoms: true })));
  const [sortie] = reponse.rows;
  assert.deepEqual(sortie.throughput, { state: "value", value: 20 });
  for (const col of ["items_lt", "items_ct", "items_without_commitment"]) {
    assert.deepEqual(sortie[col], { state: "masked", threshold: 10 } satisfies Cellule, col);
  }
  for (const col of ["lead_median_days", "lead_p85_days", "cycle_median_days", "cycle_p85_days"]) {
    assert.deepEqual(sortie[col], { state: "masked", threshold: 10 } satisfies Cellule, col);
  }
  assert.ok(!JSON.stringify(reponse).includes("15"));
});

test("a share of the blocked view is masked with its part when the rest is under the threshold", () => {
  const v = vue("v_team_blocked_share");
  const reponse = composerReponse(v, [{ team: "A", quarter_start: "2026-01-01", blocked_n: 30, blocked: 23, share_percent: 76.7 }], 10);
  const [sortie] = reponse.rows;
  assert.deepEqual(sortie.blocked_n, { state: "value", value: 30 });
  assert.deepEqual(sortie.blocked, { state: "masked", threshold: 10 });
  assert.deepEqual(sortie.share_percent, { state: "masked", threshold: 10 } satisfies Cellule);
});

test("a statistic read as a numeric string is served as a value cell holding the number when its headcount is shown", () => {
  const v = vue("v_team_lead_time_throughput");
  const ligne = {
    team: "A", period: "quarter", quarter_start: "2026-01-01", throughput: 40, items_lt: 30, lead_median_days: "3.50", lead_p85_days: "9.00",
    items_ct: 30, cycle_median_days: 4, cycle_p85_days: 8, items_old: 0, items_without_commitment: 10,
  };
  const reponse = composerReponse(v, [ligne], 10);
  assert.ok(Value.Check(schemaReponseDeVue(v), servirVue(reponse, { afficherNoms: true })));
  assert.deepEqual(reponse.rows[0].lead_median_days, { state: "value", value: 3.5 });
  assert.deepEqual(reponse.columns.slice(0, 3), ["team", "period", "quarter_start"]);
});

// Relation T3 (masking-sums D17, R-20261031-11): lireVueMasquee reads the weekly view with the same access and the rule (b) applies at run time.
test("lireVueMasquee masks the throughput when the remainder of the weekly rows pins a value (T3, rule b)", async () => {
  const v = vue("v_team_lead_time_throughput");
  const debit = { team: "A", period: "quarter", quarter_start: new Date(2026, 3, 1), throughput: 23, items_lt: null, lead_median_days: null, lead_p85_days: null,
    items_ct: null, cycle_median_days: null, cycle_p85_days: null, items_old: null, items_without_commitment: null };
  const semaine = (type: string, jour: number, tickets: number | null) => ({ team: "A", type, week_start: new Date(2026, 3, jour), tickets });
  const fabrique = (hebdo: Array<Record<string, unknown>>) => {
    const appels: string[] = [];
    const acces = {
      async lireVue(x: { name: string }) {
        appels.push(x.name);
        return x.name === "v_team_weekly_resolved" ? hebdo : [debit];
      },
    };
    return { acces, appels };
  };
  // throughput 23, visible cells 12 + 8 = 20, one masked row: the remainder 3 would be read
  const un = fabrique([semaine("Story", 6, 12), semaine("Task", 6, 8), semaine("Story", 13, null)]);
  const masquee = await lireVueMasquee(un.acces, v, 5);
  assert.deepEqual(masquee.rows[0].throughput, { state: "masked", threshold: 5 });
  assert.deepEqual(un.appels, ["v_team_lead_time_throughput", "v_team_weekly_resolved"]);
  // two masked rows with a remainder of 5: nothing is pinned, the throughput stays
  const deux = fabrique([semaine("Story", 6, 12), semaine("Task", 6, 6), semaine("Story", 13, null), semaine("Task", 13, null)]);
  assert.deepEqual((await lireVueMasquee(deux.acces, v, 5)).rows[0].throughput, { state: "value", value: 23 });
});

test("the floor still applies when no threshold above it is set", () => {
  const reponse = composerReponse(vue("v_team_status"), [{ team: "A", type: "Story", status_category: "Done", status: "Closed", tickets: 4 }], 5);
  assert.deepEqual(reponse.rows[0].tickets, { state: "masked", threshold: 5 });
});
