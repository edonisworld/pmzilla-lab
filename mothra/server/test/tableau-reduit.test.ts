// Task 19.6 (B1 to B3): the route of the dashboard "lead time against cycle time" and its single entry `servirTableau`. On real data with counts
// not allowed the answer holds medians and their states only; on the synthetic dataset it is complete, counts included. Raw rows with
// distinctive sentinel counts; the mode is injected (the real mode is impossible on the throwaway database); no database.
import assert from "node:assert/strict";
import { test } from "node:test";

import { identifiantEquipe } from "@mothra/contract/equipe";
import type { ReponseLeadCycle, Vue } from "@mothra/contract";

import { BaseIndisponible } from "../src/db/acces.ts";
import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { creerCalculTableau } from "../src/fiches/tableau.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import { servirTableau } from "../src/service.ts";
import type { ModeDonnees } from "../src/service.ts";
import { SENTINELLE, contrat } from "./aide.ts";
import { controler } from "./controle.ts";
import { DepotMemoire } from "./depot-memoire.ts";

const S1 = 7919;
const S3 = 4999;
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters (R-20261114-49)
const REEL: ModeDonnees = { jeu: "real", comptesAutorises: false };
const SYNTHETIQUE: ModeDonnees = { jeu: "synthetic", comptesAutorises: false };

class AccesLead implements AccesVues {
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    if (vue.name !== "v_team_lead_time_throughput") return [];
    const ligne = (debut: string | null, effectif: number): LigneBase => ({
      team: "team-a",
      period: debut === null ? "pooled_year" : "quarter",
      quarter_start: debut,
      throughput: S1,
      items_lt: effectif,
      items_ct: effectif,
      items_old: S1,
      items_without_commitment: S1,
      lead_median_days: 15,
      lead_p85_days: 30,
      cycle_median_days: 10,
      cycle_p85_days: 20,
      ticket_key: SENTINELLE, // a column the contract does not list: it must never come out
    });
    return [...DEBUTS.map((d) => ligne(d, S1)), ligne(null, S3)];
  }
}

async function depotAvecEchantillons(): Promise<DepotMemoire> {
  const depot = new DepotMemoire();
  await depot.ajouterSeuil({ code: "sample_median_min_items", value: 10, setOn: "2026-10-27", setBy: "author-1" });
  await depot.ajouterSeuil({ code: "sample_p85_min_items", value: 20, setOn: "2026-10-27", setBy: "author-1" });
  return depot;
}

async function monter(mode: ModeDonnees, depot?: DepotMemoire) {
  const d = depot ?? (await depotAvecEchantillons());
  const calcul = creerCalculTableau({ acces: new AccesLead(), contrat, seuil: 5, depot: d, identifiantEquipe, aujourdhui: () => "2026-10-05" });
  const { app } = construireServeur({ contrat, acces: new AccesLead(), reglageSeuil: null, journal: false, tableaux: { ...calcul, mode } });
  return { app, calcul };
}

const sentinelles = (x: unknown): string[] => [S1, S3].map(String).filter((s) => new RegExp(`(?<![0-9.])${s}(?![0-9])`).test(JSON.stringify(x)));

test("synthetic dataset: the complete answer, counts included, with the code dataset synthetic", async () => {
  const { app } = await monter(SYNTHETIQUE);
  const r = await app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(r.statusCode, 200);
  const corps = r.json() as ReponseLeadCycle;
  assert.equal(corps.dataset, "synthetic");
  assert.ok(sentinelles(corps).length > 0);
  assert.deepEqual(corps.teams[0].points[0].items, { state: "value", value: S1 });
  assert.match(corps.teams[0].teamId, /^[a-z0-9_-]{1,59}$/);
  await app.close();
});

test("real dataset, counts not allowed: medians with their states, no items in the series, the product row or the points, no sentinel", async () => {
  const { app } = await monter(REEL);
  const r = await app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(r.statusCode, 200);
  const corps = r.json() as { dataset: string; teams: Array<{ points: Array<Record<string, unknown>> }>; product: unknown[] };
  assert.equal(corps.dataset, "real");
  assert.deepEqual(sentinelles(corps), []);
  assert.ok(!r.body.includes('"items"'));
  assert.equal(corps.teams[0].points.length, 4);      // three quarters and the pooled year (before: four quarters, 5)
  assert.deepEqual(corps.teams[0].points[0].lead, { state: "value", value: 15 });
  assert.deepEqual(Object.keys(corps.teams[0].points[0]).sort(), ["cycle", "lead", "quarter"]);
  await app.close();
});

test("servirTableau: the reduction is the service's; the day counts are allowed on real data the answer is complete again", () => {
  const plein: ReponseLeadCycle = {
    threshold: 5,
    dataDate: "2026-10-05",
    product: [],
    teams: [
      {
        team: "team-a",
        teamId: "abcd",
        points: [{ quarter: "2026-Q3", lead: { state: "value", value: 15 }, cycle: { state: "insufficient_sample" }, items: { state: "value", value: S1 } }],
      },
    ],
  };
  assert.deepEqual(sentinelles(servirTableau(plein, REEL)), []);
  // R-20261104-36 N1 (a), task 45.1: without the setting `afficherNoms`, the series carry no `team` (the identifier and the points stay).
  const sansNom = { ...plein, teams: [{ teamId: "abcd", points: plein.teams[0].points }] };
  assert.deepEqual(servirTableau(plein, { jeu: "real", comptesAutorises: true }), { ...sansNom, dataset: "real" });
  assert.deepEqual(servirTableau(plein, SYNTHETIQUE), { ...sansNom, dataset: "synthetic" });
  assert.deepEqual(servirTableau(plein, { ...SYNTHETIQUE, afficherNoms: true }), { ...plein, dataset: "synthetic" });
});

test("the reduced response schema declares no count field: a port that hands a complete answer still gets it omitted", async () => {
  const complet: ReponseLeadCycle = {
    threshold: 5,
    dataDate: "2026-10-05",
    product: [{ quarter: "2026-Q3", lead: { state: "value", value: 1 }, cycle: { state: "value", value: 1 }, items: { state: "value", value: S1 } }],
    teams: [],
  };
  const { app } = construireServeur({
    contrat,
    acces: new AccesLead(),
    reglageSeuil: null,
    journal: false,
    tableaux: {
      calculerTableau: async () => complet,
      // The schema alone (review, N1): the route is registered with the reduced schema (real mode) and the service entry is replaced by one
      // that does not reduce, so that only the serializer can omit the counts.
      mode: REEL,
      servir: (reponse) => reponse,
    },
  });
  const r = await app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(r.statusCode, 200);
  assert.deepEqual(sentinelles(r.json()), []);
  assert.ok(!r.body.includes('"items"'));
  await app.close();
});

test("a database failure of the port is answered 503 DATABASE_UNAVAILABLE, a fault 500 INTERNAL, codes only", async () => {
  const monte = (erreur: Error) =>
    construireServeur({
      contrat,
      acces: new AccesLead(),
      reglageSeuil: null,
      journal: false,
      tableaux: {
        calculerTableau: async () => {
          throw erreur;
        },
        mode: SYNTHETIQUE,
      },
    }).app;
  const indisponible = monte(new BaseIndisponible());
  const r = await indisponible.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(r.statusCode, 503);
  assert.deepEqual(r.json(), { error: "DATABASE_UNAVAILABLE" });
  const panne = monte(new Error("details that must not come out"));
  const p = await panne.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(p.statusCode, 500);
  assert.deepEqual(p.json(), { error: "INTERNAL" });
  await indisponible.close();
  await panne.close();
});

test("the no real data walk of tasks 6.7 and 18.2 extended to the dashboard route: no key, no sentinel, in either mode", async () => {
  for (const mode of [SYNTHETIQUE, REEL]) {
    const { app } = await monter(mode);
    const r = await app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
    assert.equal(r.statusCode, 200);
    assert.deepEqual(controler("GET /api/dashboards/lead_cycle", r.json(), [], [SENTINELLE]), []);
    await app.close();
  }
});

test("thresholds missing from the history: 409 THRESHOLDS_NOT_SET; a query parameter: 400 INVALID_REQUEST", async () => {
  const { app } = await monter(SYNTHETIQUE, new DepotMemoire());
  const r = await app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(r.statusCode, 409);
  assert.deepEqual(r.json(), { error: "THRESHOLDS_NOT_SET" });
  const avec = await monter(SYNTHETIQUE);
  const q = await avec.app.inject({ method: "GET", url: "/api/dashboards/lead_cycle?team=team-a" });
  assert.equal(q.statusCode, 400);
  assert.deepEqual(q.json(), { error: "INVALID_REQUEST" });
  await app.close();
  await avec.app.close();
});
