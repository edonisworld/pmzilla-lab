// Lot 1b of mothra-demo-habillage (D3b, R-20261101-20 and -32): the server's service layer calls `partsDAttente` after `reduceToStatistics`, the
// routes serve the result as `waitShares` at each reading and never store it. Same set-up as forme-reduite.test.ts: fake access, the mode of the
// service injected, no database. Invented team and figures; no route is added.
import assert from "node:assert/strict";
import { test } from "node:test";

import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";
import type { Vue } from "@mothra/contract";

import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { creerCalculCorps } from "../src/fiches/corps.ts";
import { empreinte } from "../src/fiches/depot.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import type { ModeDonnees } from "../src/service.ts";
import { contrat } from "./aide.ts";
import { DepotMemoire } from "./depot-memoire.ts";

const S1 = 7919;
const DATE = "2026-10-05";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters (R-20261114-49)
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
    items_ct: S1,
    items_old: 0, // R-20261106-66 : valait l'effectif S1, donc une taille de H1 nulle
    items_without_commitment: S1,
    lead_median_days: 25,
    lead_p85_days: 40,
    cycle_median_days: 10,
    cycle_p85_days: 20,
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: 25,
    lead_p85_days_excl_old: 40,
    cycle_median_days_excl_old: 10,
    cycle_p85_days_excl_old: 20,
  };
}

function acces(): AccesParVue {
  const a = new AccesParVue();
  a.lignes.set("v_team_lead_time_throughput", [...DEBUTS.map(brute), brute(null)]);
  a.lignes.set("v_task_without_team_share", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: S1, tasks_without_team: S1, share_percent: 20 })));
  a.lignes.set("v_unplanned_share", DEBUTS.map((d) => ({ quarter_start: d, unplanned: S1, unplanned_n: S1, share_percent: 12.5 })));
  a.lignes.set("v_team_ready_queue", [{ team: "team-a", quarter_start: DEBUTS[2], ready: S1 }]);
  a.lignes.set("v_team_blocked_share", [{ team: "team-a", quarter_start: DEBUTS[2], blocked_n: S1, blocked: S1, share_percent: 30 }]);
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

const REEL: ModeDonnees = { jeu: "real", comptesAutorises: false };
const SYNTHETIQUE: ModeDonnees = { jeu: "synthetic", comptesAutorises: false };

// `avecService` false: the routes get no `completer`, like the test doubles of the other suites.
async function monter(mode: ModeDonnees, reduite: boolean, avecService: boolean) {
  const a = acces();
  const depot = new DepotMemoire();
  for (const [code, value] of SEUILS) await depot.ajouterSeuil({ code, value, setOn: "2026-10-27", setBy: "author-1" });
  const calcul = creerCalculCorps({ acces: a, contrat, seuil: 5, depot, identifiantEquipe, mode });
  const { app } = construireServeur({
    contrat,
    acces: a,
    reglageSeuil: null,
    journal: false,
    fiches: {
      depot,
      calculerCorps: calcul.calculerCorps,
      verifierCreation: calcul.verifierCreation,
      ...(avecService ? { completer: calcul.completer } : {}),
      motifsNoms: [],
      reduite,
      aujourdhui: () => "2026-11-12", // A-66: the data dates of the sheets (October 2026) lie in the day's quarter, whatever the real clock
    },
  });
  return { app, depot, calcul };
}

type Barres = {
  median: { state: string; ratio?: number; waitShare?: number; workShare?: number };
  p85: { state: string; ratio?: number; waitShare?: number };
  markers: { refutation: { ratio: number; inScale: boolean; share?: number }; confirmation: { ratio: number; inScale: boolean; share?: number }; applicable: boolean };
};

const proche = (a: number | undefined, b: number): void => assert.ok(a !== undefined && Math.abs(a - b) < 1e-9, `${String(a)} != ${String(b)}`);

async function lire(app: Awaited<ReturnType<typeof monter>>["app"], depot: DepotMemoire, chart: string): Promise<{ id: string; corps: { waitShares?: Barres } & Record<string, unknown> }> {
  const id = await depot.creer({ chart, scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(r.statusCode, 200);
  return { id, corps: r.json() as { waitShares?: Barres } & Record<string, unknown> };
}

test("on the synthetic dataset a hypothesis 1 sheet carries waitShares, from the ratios 2.5 and 2 and the adopted thresholds", async () => {
  const { app, depot } = await monter(SYNTHETIQUE, false, true);
  const { corps } = await lire(app, depot, "lead_cycle_h1");
  const w = corps.waitShares;
  assert.ok(w !== undefined);
  assert.deepEqual(w.median, { state: "value", ratio: 2.5, waitShare: 60, workShare: 40 });
  assert.deepEqual(w.p85, { state: "value", ratio: 2, waitShare: 50, workShare: 50 });
  assert.equal(w.markers.refutation.ratio, 1.5);
  proche(w.markers.refutation.share, 100 / 3);
  assert.deepEqual(w.markers.confirmation, { ratio: 3, inScale: true, share: 100 - 100 / 3 });
  assert.equal(w.markers.applicable, true);
  await app.close();
});

test("on real data (reduced form) it carries waitShares too, and no count anywhere", async () => {
  const { app, depot } = await monter(REEL, true, true);
  const { corps } = await lire(app, depot, "lead_cycle_h1");
  assert.deepEqual(corps.waitShares?.median, { state: "value", ratio: 2.5, waitShare: 60, workShare: 40 });
  assert.ok(!JSON.stringify(corps).includes(String(S1)));
  assert.equal((corps as { dataset?: string }).dataset, "real");
  await app.close();
});

test("a hypothesis 5 sheet carries no waitShares", async () => {
  const { app, depot } = await monter(SYNTHETIQUE, false, true);
  const { corps } = await lire(app, depot, "lead_cycle_h5");
  assert.equal(corps.waitShares, undefined);
  assert.ok(!("waitShares" in corps));
  await app.close();
});

test("without the service layer (the option absent, as in the test doubles) the answer carries no waitShares, and is not an error", async () => {
  const { app, depot } = await monter(SYNTHETIQUE, false, false);
  const { corps } = await lire(app, depot, "lead_cycle_h1");
  assert.ok(!("waitShares" in corps));
  await app.close();
});

test("the freeze stores no waitShares and the fingerprint is unchanged by the field; a frozen version read again gets its bars, recomputed", async () => {
  const { app, depot } = await monter(REEL, true, true);
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
  assert.deepEqual((publiee.json() as { waitShares?: Barres }).waitShares?.median, { state: "value", ratio: 2.5, waitShare: 60, workShare: 40 });
  const figee = depot.fiches.get(id)?.published;
  assert.ok(figee !== undefined);
  assert.ok(!("waitShares" in figee.content), "the frozen content holds no waitShares");
  assert.equal(figee.fingerprint, empreinte(figee.content), "the fingerprint is that of the stored content, which holds no waitShares");
  const relue = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(relue.statusCode, 200);
  assert.deepEqual((relue.json() as { waitShares?: Barres }).waitShares, (publiee.json() as { waitShares?: Barres }).waitShares);
  assert.ok(!("waitShares" in (depot.fiches.get(id)?.published?.content ?? {})));
  assert.equal(depot.fiches.get(id)?.published?.fingerprint, empreinte(depot.fiches.get(id)?.published?.content as never));
  await app.close();
});

// Scenario "published before the field existed": a frozen version inserted directly into the storage, without waitShares.
test("a frozen version inserted without waitShares is read with its bars recomputed from its frozen ratios and thresholds", async () => {
  const { app, depot, calcul } = await monter(REEL, true, true);
  const id = await depot.creer({ chart: "lead_cycle_h1", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const corps = await calcul.calculerCorps({ id, chart: "lead_cycle_h1", scope: SCOPE, dataDate: DATE });
  const content = { ...corps, effect: { text: "Effect.", lang: "en" as const }, cause: { text: "Cause.", lang: "en" as const }, managementQuestion: "predictability" as const };
  assert.ok(!("waitShares" in content));
  const fiche = depot.fiches.get(id);
  assert.ok(fiche !== undefined);
  fiche.state = "published";
  fiche.published = { version: 1, content, fingerprint: empreinte(content), publishedBy: "agile-lead-1", publishedOn: "2026-10-30" };
  const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(r.statusCode, 200);
  assert.deepEqual((r.json() as { waitShares?: Barres }).waitShares?.median, { state: "value", ratio: 2.5, waitShare: 60, workShare: 40 });
  assert.deepEqual(depot.fiches.get(id)?.published?.content, content, "the frozen version is unchanged");
  await app.close();
});

// A closed list of the sheet routes (those of main), and the same routes whatever the option: lot 1b adds none.
test("no route is added: the sheet routes are the closed list of main, identical with and without the service layer", async () => {
  const avec = await monter(SYNTHETIQUE, false, true);
  const sans = await monter(SYNTHETIQUE, false, false);
  await avec.app.ready();
  await sans.app.ready();
  const routes = avec.app.printRoutes({ commonPrefix: false });
  assert.equal(routes, sans.app.printRoutes({ commonPrefix: false }));
  // The sheet routes of main, read by Fastify's hasRoute (the printRoutes tree splits paths into segments, so a path is not a substring).
  const fiches: Array<[string, string]> = [
    ["POST", "/api/sheets"],
    ["GET", "/api/sheets/:id"],
    ["PATCH", "/api/sheets/:id"],
    ["POST", "/api/sheets/:id/review"],
    ["POST", "/api/sheets/:id/publish"],
  ];
  for (const [method, url] of fiches) {
    assert.ok(avec.app.hasRoute({ method, url }), `${method} ${url}`);
    assert.ok(sans.app.hasRoute({ method, url }), `${method} ${url}`);
  }
  assert.ok(!routes.toLowerCase().includes("wait"), routes);
  await avec.app.close();
  await sans.app.close();
});
