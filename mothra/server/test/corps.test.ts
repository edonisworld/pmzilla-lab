// Task 18.4: the real implementation of the port `calculerCorps` (server/src/fiches/corps.ts) over a fake view access that gives RAW rows,
// as the database does (columns beyond the contract, a sentinel, counts under the threshold). The masking is the one of the service.
// DEPENDS ON TASK 15.3 (masquerVue: statistics and shares become masked cells): written before its merge, it is played after the rebase on
// main that holds 15.3. Invented team and figures; no database.
import assert from "node:assert/strict";
import { test } from "node:test";

import { corpsDepuisVues } from "@mothra/contract";
import type { Vue } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import { BaseIndisponible } from "../src/db/acces.ts";
import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { VUES_DE_LA_FICHE, creerCalculCorps } from "../src/fiches/corps.ts";
import { empreinte } from "../src/fiches/depot.ts";
import { lireVueMasquee } from "../src/service.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import { SENTINELLE, contrat } from "./aide.ts";
import { DepotMemoire } from "./depot-memoire.ts";

const DATE = "2026-10-05";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters (R-20261114-49)
const JUGE = DEBUTS[2];
// The real identifier and scope of the contract (review of 18.4, A1): the team of the rows is "team-a".
const identifiant = identifiantEquipe;
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe("team-a") });

class AccesParVue implements AccesVues {
  lignes = new Map<string, LigneBase[]>();
  echec: Error | null = null;
  appels: string[] = [];
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    this.appels.push(vue.name);
    if (this.echec !== null) throw this.echec;
    return this.lignes.get(vue.name) ?? [];
  }
}

function brute(debut: string | null, o: { n?: number; ct?: number } = {}): LigneBase {
  return {
    team: "team-a",
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: o.n ?? 30,
    items_lt: 30,
    items_ct: o.ct ?? 30,
    items_old: 5,
    items_without_commitment: 0,
    lead_median_days: 15,
    lead_p85_days: 30,
    cycle_median_days: 10,
    cycle_p85_days: 20,
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: 15,
    lead_p85_days_excl_old: 30,
    cycle_median_days_excl_old: 10,
    cycle_p85_days_excl_old: 20,
    ticket_key: SENTINELLE, // a column the contract does not list: it must never come out
  };
}

function acces(trimestres: Array<{ n?: number; ct?: number }> = [{}, {}, {}]): AccesParVue {
  const a = new AccesParVue();
  a.lignes.set("v_team_lead_time_throughput", [...trimestres.map((o, i) => brute(DEBUTS[i], o)), brute(null)]);
  a.lignes.set("v_task_without_team_share", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: 30, tasks_without_team: 6, share_percent: 20 })));
  a.lignes.set("v_unplanned_share", DEBUTS.map((d) => ({ quarter_start: d, unplanned: 10, unplanned_n: 80, share_percent: 12.5 })));
  a.lignes.set("v_team_ready_queue", [{ team: "team-a", quarter_start: JUGE, ready: 12 }]);
  a.lignes.set("v_team_blocked_share", [{ team: "team-a", quarter_start: JUGE, blocked_n: 30, blocked: 9, share_percent: 30 }]);
  return a;
}

const SEUILS: Array<[string, number]> = [
  ["h5_band", 0.2],
  ["h5_double_band", 0.4],
  ["h5_run_rises", 2],
  ["h5_run_min_cumulative_rise", 0.1],
  ["h5_floor", 0.8],
  ["h5_low_floor", 0.6],
  ["h1_lower", 1.5],
  ["h1_upper", 3],
  ["attachment_threshold_points", 10],
  ["sample_median_min_items", 10],
  ["sample_p85_min_items", 20],
];

async function depotAvecSeuils(): Promise<DepotMemoire> {
  const depot = new DepotMemoire();
  for (const [code, value] of SEUILS) await depot.ajouterSeuil({ code, value, setOn: "2026-10-27", setBy: "author-1" });
  return depot;
}

async function monter(a: AccesParVue, depot: DepotMemoire) {
  const calcul = creerCalculCorps({ acces: a, contrat, seuil: 5, depot, identifiantEquipe: identifiant, mode: { jeu: "synthetic", comptesAutorises: false } });
  const { app } = construireServeur({
    contrat,
    acces: a,
    reglageSeuil: null,
    journal: false,
    fiches: { depot, calculerCorps: calcul.calculerCorps, verifierCreation: calcul.verifierCreation, motifsNoms: [], reduite: false, aujourdhui: () => "2026-11-12" },
  });
  return { app, calcul };
}

test("the body is the pure function of the contract applied to the masked views, with the fingerprint of what was read", async () => {
  const a = acces();
  const depot = await depotAvecSeuils();
  const { calcul } = await monter(a, depot);
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const corps = await calcul.calculerCorps({ id, chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE });
  assert.deepEqual([...new Set(a.appels)].sort(), [...Object.values(VUES_DE_LA_FICHE), "v_team_weekly_resolved"].sort());
  const lues = Object.fromEntries(
    await Promise.all(Object.entries(VUES_DE_LA_FICHE).map(async ([cle, nom]) => [cle, await lireVueMasquee(a, contrat.views.find((v) => v.name === nom) as Vue, 5)])),
  ) as Parameters<typeof corpsDepuisVues>[0]["vues"];
  const attendu = corpsDepuisVues({
    chart: "lead_cycle_h5",
    scope: SCOPE,
    dataDate: DATE,
    premiereLecture: "2026-10-30",
    historique: SEUILS.map(([code, value]) => ({ code, value, setOn: "2026-10-27" })),
    vues: lues,
    identifiantEquipe: identifiant,
    empreinte: empreinte(lues),
  });
  assert.deepEqual(corps, { ...attendu, dataset: "synthetic" });
  assert.equal(corps.method.hypothesis, "h5");
});

test("columns beyond the contract and counts under the threshold never reach the body", async () => {
  const a = acces([{}, {}, { n: 3 }]);
  const depot = await depotAvecSeuils();
  const { calcul } = await monter(a, depot);
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const corps = await calcul.calculerCorps({ id, chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE });
  const texte = JSON.stringify(corps);
  assert.ok(!texte.includes(SENTINELLE));
  assert.ok(!texte.includes('"value":3,') && !texte.includes('"value":3}'), "a count under the threshold is the masked cell");
  assert.ok(corps.method.maskedCells.some((m) => m.measure === `throughput@${JUGE}` && m.cell.state === "masked" && m.cell.threshold === 5));
});

test("a failing access is BaseIndisponible, answered 503 by the route", async () => {
  const a = acces();
  a.echec = new Error("connection refused: details that must not come out");
  const depot = await depotAvecSeuils();
  const { app, calcul } = await monter(a, depot);
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  await assert.rejects(calcul.calculerCorps({ id, chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE }), BaseIndisponible);
  const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(r.statusCode, 503);
  assert.deepEqual(r.json(), { error: "DATABASE_UNAVAILABLE" });
  await app.close();
});

test("without thresholds in the history: creation and reading are refused THRESHOLDS_NOT_SET; an unknown chart is an invalid request", async () => {
  const a = acces();
  const depot = new DepotMemoire();
  const { app } = await monter(a, depot);
  const en = { "x-mothra-user": "agile-lead-1" };
  const cree = await app.inject({ method: "POST", url: "/api/sheets", headers: en, payload: { chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE } });
  assert.equal(cree.statusCode, 409);
  assert.deepEqual(cree.json(), { error: "THRESHOLDS_NOT_SET" });
  const inconnu = await app.inject({ method: "POST", url: "/api/sheets", headers: en, payload: { chart: "lead-cycle", scope: SCOPE, dataDate: DATE } });
  assert.equal(inconnu.statusCode, 400);
  // A team name, the product level and an unknown text are not scopes of a sheet (A1 and the product scope of the review): 400.
  for (const scope of ["team-a", "product", "equipe-e"]) {
    const refuse = await app.inject({ method: "POST", url: "/api/sheets", headers: en, payload: { chart: "lead_cycle_h5", scope, dataDate: DATE } });
    assert.equal(refuse.statusCode, 400, scope);
    assert.deepEqual(refuse.json(), { error: "INVALID_REQUEST" });
  }
  assert.equal(depot.fiches.size, 0);
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const lu = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(lu.statusCode, 409);
  assert.deepEqual(lu.json(), { error: "THRESHOLDS_NOT_SET" });
  await app.close();
});

test("a sheet from creation to publication: the verdict is computed, the publication freezes the computed body and its fingerprint", async () => {
  const a = acces();
  const depot = await depotAvecSeuils();
  const { app } = await monter(a, depot);
  const auteur = { "x-mothra-user": "agile-lead-1" };
  const relecteur = { "x-mothra-user": "agile-lead-2" };
  const cree = await app.inject({
    method: "POST",
    url: "/api/sheets",
    headers: auteur,
    payload: { chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, managementQuestion: "predictability", effect: { text: "Effect.", lang: "en" }, cause: { text: "Cause.", lang: "en" } },
  });
  assert.equal(cree.statusCode, 200);
  const id = (cree.json() as { id: string }).id;
  const brouillon = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(brouillon.statusCode, 200);
  const corps = brouillon.json() as { verdict: string; explanations: Array<{ name: string; measure?: unknown }>; chart?: { quarters: unknown[] }; method: { fingerprint: string } };
  assert.equal(corps.verdict, "not_settled");
  assert.equal(corps.chart?.quarters.length, 3);
  assert.deepEqual(corps.explanations.find((e) => e.name === "capacity")?.measure, { state: "value", value: 12 });
  assert.match(corps.method.fingerprint, /^[0-9a-f]{64}$/);
  assert.equal((await app.inject({ method: "POST", url: `/api/sheets/${id}/review`, headers: relecteur })).statusCode, 200);
  const publiee = await app.inject({ method: "POST", url: `/api/sheets/${id}/publish`, headers: auteur });
  assert.equal(publiee.statusCode, 200);
  a.lignes.set("v_team_ready_queue", []); // the views change after the publication: the frozen sheet does not
  const relue = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.deepEqual((relue.json() as { explanations: unknown }).explanations, corps.explanations);
  await app.close();
});
