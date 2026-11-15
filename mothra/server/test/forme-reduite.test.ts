// Task 19.5 (A5, A6, A7): the reduced form of a sheet on real data, in the service layer and over HTTP. The dataset is injected as a mode of
// the service (the real mode is impossible on the throwaway database, the marker forbids it); no database. Raw rows with distinctive sentinel
// counts (7919, 6007, 4999) come out of the fake access; no answer, no frozen version may hold one. Invented team and figures.
import assert from "node:assert/strict";
import { test } from "node:test";

import { corpsDepuisVues } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";
import type { Vue } from "@mothra/contract";

import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { creerCalculCorps } from "../src/fiches/corps.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import type { ModeDonnees } from "../src/service.ts";
import { contrat } from "./aide.ts";
import { DepotMemoire } from "./depot-memoire.ts";

const S1 = 7919;
const S2 = 6007;
const S3 = 4999;
const DATE = "2026-10-05";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters (R-20261114-49)
const JUGE = DEBUTS[2];
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe("team-a") });

class AccesParVue implements AccesVues {
  lignes = new Map<string, LigneBase[]>();
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    return this.lignes.get(vue.name) ?? [];
  }
}

function brute(debut: string | null): LigneBase {
  return {
    team: "team-a",
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: S1,
    items_lt: S1,
    items_ct: debut === null ? S3 : S1,
    items_old: 0, // R-20261106-66 : valait l'effectif S1, donc une taille de H1 nulle
    items_without_commitment: S1,
    lead_median_days: 15,
    lead_p85_days: 30,
    cycle_median_days: 10,
    cycle_p85_days: 20,
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: 15,
    lead_p85_days_excl_old: 30,
    cycle_median_days_excl_old: 10,
    cycle_p85_days_excl_old: 20,
  };
}

function acces(): AccesParVue {
  const a = new AccesParVue();
  a.lignes.set("v_team_lead_time_throughput", [...DEBUTS.map(brute), brute(null)]);
  a.lignes.set("v_task_without_team_share", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: S3, tasks_without_team: S3, share_percent: 20 })));
  a.lignes.set("v_unplanned_share", DEBUTS.map((d) => ({ quarter_start: d, unplanned: S3, unplanned_n: S3, share_percent: 12.5 })));
  a.lignes.set("v_team_ready_queue", [{ team: "team-a", quarter_start: JUGE, ready: S2 }]);
  a.lignes.set("v_team_blocked_share", [{ team: "team-a", quarter_start: JUGE, blocked_n: S1, blocked: S2, share_percent: 30 }]);
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

const REEL: ModeDonnees = { jeu: "real", comptesAutorises: false };
const SYNTHETIQUE: ModeDonnees = { jeu: "synthetic", comptesAutorises: false };

async function monter(mode: ModeDonnees, reduite: boolean) {
  const a = acces();
  const depot = await depotAvecSeuils();
  const calcul = creerCalculCorps({ acces: a, contrat, seuil: 5, depot, identifiantEquipe, mode });
  const { app } = construireServeur({
    contrat,
    acces: a,
    reglageSeuil: null,
    journal: false,
    fiches: { depot, calculerCorps: calcul.calculerCorps, verifierCreation: calcul.verifierCreation, motifsNoms: [], reduite, aujourdhui: () => "2026-11-12" },
  });
  return { app, depot, calcul };
}

const sentinelles = (x: unknown): string[] =>
  [S1, S2, S3].map(String).filter((s) => new RegExp(`(?<![0-9.])${s}(?![0-9])`).test(JSON.stringify(x)));

test("on the synthetic dataset the body is complete, counts included, with the code dataset synthetic", async () => {
  const { calcul, depot } = await monter(SYNTHETIQUE, false);
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const corps = await calcul.calculerCorps({ id, chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE });
  assert.equal(corps.dataset, "synthetic");
  assert.ok(sentinelles(corps).length > 0);
  assert.notEqual(corps.method.coverage, undefined);
});

test("on real data with counts not allowed the service layer hands a reduced body: no sentinel, the code dataset real, a coverage state", async () => {
  const { calcul, depot } = await monter(REEL, true);
  for (const chart of ["lead_cycle_h5", "lead_cycle_h1"]) {
    const id = await depot.creer({ chart, scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
    const corps = await calcul.calculerCorps({ id, chart, scope: SCOPE, dataDate: DATE });
    assert.deepEqual(sentinelles(corps), [], chart);
    assert.equal(corps.dataset, "real");
    assert.equal(corps.method.coverage, undefined);
    assert.equal(corps.method.coverageState, "coverage_sufficient");
    assert.ok(corps.method.limits.includes("reduced_form"));
  }
});

test("the day the constant allows counts, a real answer is complete again (the switch reads the constant, nothing else)", async () => {
  const { calcul, depot } = await monter({ jeu: "real", comptesAutorises: true }, false);
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const corps = await calcul.calculerCorps({ id, chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE });
  assert.ok(sentinelles(corps).length > 0);
  assert.equal(corps.dataset, "real");
});

test("a reduced answer over HTTP holds no count, whatever the sheet kind, and reads the same verdict as the complete one", async () => {
  const reel = await monter(REEL, true);
  const synthetique = await monter(SYNTHETIQUE, false);
  for (const chart of ["lead_cycle_h5", "lead_cycle_h1"]) {
    const verdicts: string[] = [];
    for (const { app, depot } of [reel, synthetique]) {
      const id = await depot.creer({ chart, scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
      const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
      assert.equal(r.statusCode, 200);
      const corps = r.json() as { verdict: string; dataset: string };
      verdicts.push(corps.verdict);
      if (app === reel.app) {
        assert.deepEqual(sentinelles(r.json()), [], chart);
        assert.equal(corps.dataset, "real");
      } else {
        assert.equal(corps.dataset, "synthetic");
      }
    }
    assert.equal(verdicts[0], verdicts[1], chart);
  }
  await reel.app.close();
  await synthetique.app.close();
});

test("the reduced response schema declares no count field: a service that hands a complete body still gets it omitted", async () => {
  // A double of the service that ignores the mode and gives the complete body of the contract.
  const a = acces();
  const depot = await depotAvecSeuils();
  const { app } = construireServeur({
    contrat,
    acces: a,
    reglageSeuil: null,
    journal: false,
    fiches: {
      depot,
      motifsNoms: [],
      reduite: true,
      aujourdhui: () => "2026-11-12",
      calculerCorps: async () => {
        const vues = {
          leadCycle: { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows: [], sources: ["flow"] },
          sansEquipe: { view: "x", threshold: 5, columns: [], rows: [], sources: ["flow"] },
          nonPlanifie: { view: "x", threshold: 5, columns: [], rows: [], sources: ["flow"] },
          fileEnAttente: { view: "x", threshold: 5, columns: [], rows: [], sources: ["flow"] },
          bloque: { view: "x", threshold: 5, columns: [], rows: [], sources: ["flow"] },
        };
        const cell = (n: number) => ({ state: "value" as const, value: n });
        const ligne = (debut: string | null) => ({
          team: "team-a",
          period: debut === null ? "pooled_year" : "quarter",
          quarter_start: debut,
          throughput: cell(S1),
          items_lt: cell(S1),
          items_ct: cell(S1),
          items_old: cell(0), // R-20261106-66 : valait l'effectif S1
          items_without_commitment: cell(S1),
          lead_median_days: cell(15),
          lead_p85_days: cell(30),
          cycle_median_days: cell(10),
          cycle_p85_days: cell(20),
          // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
          lead_median_days_excl_old: cell(15),
          lead_p85_days_excl_old: cell(30),
          cycle_median_days_excl_old: cell(10),
          cycle_p85_days_excl_old: cell(20),
        });
        vues.leadCycle.rows = [...DEBUTS.map(ligne), ligne(null)] as never;
        vues.fileEnAttente.rows = [{ team: "team-a", quarter_start: JUGE, ready: cell(S2) }] as never;
        const complet = corpsDepuisVues({
          chart: "lead_cycle_h5",
          scope: SCOPE,
          dataDate: DATE,
          premiereLecture: null,
          historique: SEUILS.map(([code, value]) => ({ code, value, setOn: "2026-10-27" })),
          vues,
          identifiantEquipe,
          empreinte: "f".repeat(64),
        });
        // The reduced schema requires the coverage state; the double adds it and keeps every count of the complete body.
        return { ...complet, method: { ...complet.method, coverageState: "coverage_sufficient" as const } };
      },
    },
  });
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(r.statusCode, 200);
  assert.deepEqual(sentinelles(r.json()), []);
  const texte = r.body;
  for (const interdite of ['"items"', '"measure"', '"coverage"', '"unplannedProductShare"', '"tasksWithoutTeamShare"']) {
    assert.ok(!texte.includes(interdite), interdite);
  }
  await app.close();
});

test("publication on real data freezes the reduced body and its fingerprint only: the frozen version holds no sentinel", async () => {
  const { app, depot } = await monter(REEL, true);
  const auteur = { "x-mothra-user": "agile-lead-1" };
  const relecteur = { "x-mothra-user": "agile-lead-2" };
  const cree = await app.inject({
    method: "POST",
    url: "/api/sheets",
    headers: auteur,
    payload: { chart: "lead_cycle_h1", scope: SCOPE, dataDate: DATE, managementQuestion: "predictability", effect: { text: "Effect.", lang: "en" }, cause: { text: "Cause.", lang: "en" } },
  });
  assert.equal(cree.statusCode, 200);
  const id = (cree.json() as { id: string }).id;
  assert.equal((await app.inject({ method: "POST", url: `/api/sheets/${id}/review`, headers: relecteur })).statusCode, 200);
  const publiee = await app.inject({ method: "POST", url: `/api/sheets/${id}/publish`, headers: auteur });
  assert.equal(publiee.statusCode, 200);
  assert.deepEqual(sentinelles(publiee.json()), []);
  const figee = depot.fiches.get(id)?.published;
  assert.ok(figee !== undefined);
  assert.deepEqual(sentinelles(figee.content), []);
  assert.match(figee.fingerprint, /^[0-9a-f]{64}$/);
  const relue = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.deepEqual(sentinelles(relue.json()), []);
  // "Make it a sheet" from a reduced chart gives a draft in the reduced form (task 19.6, B4): the draft read back is reduced.
  assert.equal((relue.json() as { dataset: string }).dataset, "real");
  await app.close();
});

// Q48 (a) of R-20261031-19: on real data the sheet of hypothesis 5 is not created (the existing 404 NOT_FOUND, nothing stored); on the synthetic
// dataset it is accepted. Falls with the author's decision of 12 November (R-20261031-18).
test("creating a sheet of hypothesis 5 is refused 404 NOT_FOUND on real data, nothing stored; accepted on synthetic; hypothesis 1 accepted on real", async () => {
  const auteur = { "x-mothra-user": "agile-lead-1" };
  const demande = (chart: string) => ({ method: "POST" as const, url: "/api/sheets", headers: auteur, payload: { chart, scope: SCOPE, dataDate: DATE } });
  const reel = await monter(REEL, true);
  const refus = await reel.app.inject(demande("lead_cycle_h5"));
  assert.equal(refus.statusCode, 404);
  assert.deepEqual(refus.json(), { error: "NOT_FOUND" });
  assert.equal(reel.depot.fiches.size, 0);
  assert.equal((await reel.app.inject(demande("lead_cycle_h1"))).statusCode, 200);
  const synthetique = await monter(SYNTHETIQUE, false);
  assert.equal((await synthetique.app.inject(demande("lead_cycle_h5"))).statusCode, 200);
  await reel.app.close();
  await synthetique.app.close();
});
