// Task 42.2 (part R-150): the "no real data" test of tasks 6.7 and 18.2 extended to the product-scope dashboard routes already on main
// (`/api/dashboards/lead_cycle` and the four `/api/panels/<code>` of task 37.1), both mounted on ONE server. Dataset `real` and counts not
// allowed: no count and no share of a count in any answer, with key sentinels (a ticket key, a key-shaped string) and a title sentinel in
// columns the contract does not list. The page of cycle preparation arrives with its route (task 40.3): not here. New cases only; no database.
// Relation to the neighbouring walks: panneaux.test.ts (the walk "extended to the four routes") and tableau-reduit.test.ts (the walk
// "extended to the dashboard route") already walk their own routes. Replaces: nothing. This test is the SOURCE for the coverage of every
// route of the product-scope dashboard (/api/dashboards/ and /api/panels/); a route added there and missing from ROUTES makes the coverage
// case fail (registered routes compared with the routes walked, as test/db/aucune-donnee-reelle.test.ts does). Removal: permanent.
import assert from "node:assert/strict";
import { test } from "node:test";

import { identifiantEquipe } from "@mothra/contract/equipe";
import { CODES_PANNEAUX } from "@mothra/contract";
import type { Contrat, Vue } from "@mothra/contract";

import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { creerCalculPanneaux } from "../src/fiches/panneaux.ts";
import { creerCalculTableau } from "../src/fiches/tableau.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import type { ModeDonnees } from "../src/service.ts";
import { SENTINELLE, contrat } from "./aide.ts";
import { controler } from "./controle.ts";
import { DepotMemoire } from "./depot-memoire.ts";

const VUE_FLUX: Vue = {
  name: "v_team_flow_inout",
  schema: "flow",
  roleKind: "flow",
  countColumns: ["created", "done"],
  plainColumns: ["team", "quarter_start", "type_group"],
};
const CONTRAT: Contrat = { ...contrat, views: [...contrat.views, VUE_FLUX] };

const REEL: ModeDonnees = { jeu: "real", comptesAutorises: false };
const SYNTHETIQUE: ModeDonnees = { jeu: "synthetic", comptesAutorises: false };
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters (R-20261114-49)
// The single date of the day of the test (a day of the quarter after the range).
const AUJOURDHUI = "2026-10-05";
const PLAGE = "from=2026-Q1&to=2026-Q3";
const ID_A = identifiantEquipe("team-a");

// Sentinels of key and of title: a ticket key, a key-shaped string, a title; none is a column of the contract.
const CLE = "ZZSENT-4242";
const TITRE = "Titre-sentinelle-ne-doit-jamais-sortir";
// Distinctive counts, found nowhere else in an answer (medians are 15 and 10, days).
const COMPTES = [7919, 4999, 6143, 3571, 8209, 2927];
// Every value a row can serve: COMPTES[k] + i for each quarter i (the rows add the quarter index).
const TOUS_LES_COMPTES = COMPTES.flatMap((c) => DEBUTS.map((_, i) => c + i));

const UNIQUES: Record<string, unknown> = { ticket_key: CLE, title: TITRE, summary: SENTINELLE };

function flux(): LigneBase[] {
  const lignes: LigneBase[] = [];
  DEBUTS.forEach((d, i) => {
    lignes.push({ team: "(produit)", quarter_start: d, type_group: "story", created: COMPTES[0] + i, done: COMPTES[1] + i, ...UNIQUES });
    lignes.push({ team: "(produit)", quarter_start: d, type_group: "defect", created: COMPTES[2] + i, done: COMPTES[3] + i, ...UNIQUES });
    lignes.push({ team: "team-a", quarter_start: d, type_group: "story", created: COMPTES[4] + i, done: COMPTES[5] + i, ...UNIQUES });
    // H-05 (rule of tools/flow_views.py:444): the defect group needs a team row, or its product row is masked. Counts at or above the threshold,
    // not distinctive. Permanent, as long as the rule of the product row stands.
    lignes.push({ team: "team-a", quarter_start: d, type_group: "defect", created: 21 + i, done: 23 + i, ...UNIQUES });
  });
  return lignes;
}

function bloque(): LigneBase[] {
  return DEBUTS.map((d, i) => ({ team: "team-a", quarter_start: d, blocked_n: COMPTES[0] + i, blocked: COMPTES[1] + i, share_percent: 37 + i, ...UNIQUES }));
}

function leadCycle(): LigneBase[] {
  const ligne = (debut: string | null): LigneBase => ({
    team: "team-a",
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: COMPTES[0],
    items_lt: COMPTES[1],
    items_ct: COMPTES[1],
    items_old: COMPTES[2],
    items_without_commitment: COMPTES[3],
    lead_median_days: 15,
    lead_p85_days: 30,
    cycle_median_days: 10,
    cycle_p85_days: 20,
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: 15,
    lead_p85_days_excl_old: 30,
    cycle_median_days_excl_old: 10,
    cycle_p85_days_excl_old: 20,
    ...UNIQUES,
  });
  return [...DEBUTS.map((d) => ligne(d)), ligne(null)];
}

class AccesProduit implements AccesVues {
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    if (vue.name === "v_team_flow_inout") return flux();
    if (vue.name === "v_team_blocked_share") return bloque();
    if (vue.name === "v_team_lead_time_throughput") return leadCycle();
    return [];
  }
}

async function monter(mode: ModeDonnees, vuesFermees = false) {
  const depot = new DepotMemoire();
  await depot.ajouterSeuil({ code: "sample_median_min_items", value: 10, setOn: "2026-10-27", setBy: "author-1" });
  await depot.ajouterSeuil({ code: "sample_p85_min_items", value: 20, setOn: "2026-10-27", setBy: "author-1" });
  const acces = new AccesProduit();
  const tableau = creerCalculTableau({ acces, contrat: CONTRAT, seuil: 5, depot, identifiantEquipe, aujourdhui: () => AUJOURDHUI });
  const panneaux = creerCalculPanneaux({ acces, contrat: CONTRAT, seuil: 5, identifiantEquipe });
  return construireServeur({
    contrat: CONTRAT,
    acces,
    reglageSeuil: null,
    journal: false,
    vuesFermees,
    tableaux: { ...tableau, mode },
    panneaux: { ...panneaux, mode, aujourdhui: () => AUJOURDHUI },
  });
}

// One entry per walked answer; `chemin` is the registered path without the query. Panel codes come from the contract.
const ROUTES: Array<{ route: string; chemin: string; url: string }> = [
  { route: "GET /api/dashboards/lead_cycle", chemin: "/api/dashboards/lead_cycle", url: "/api/dashboards/lead_cycle" },
  ...CODES_PANNEAUX.map((code) => {
    const equipe = code === "blocked-share" ? `team=${ID_A}&` : "";
    return { route: `GET /api/panels/${code}`, chemin: `/api/panels/${code}`, url: `/api/panels/${code}?${equipe}${PLAGE}` };
  }),
  { route: "GET /api/panels/stories-inout (team)", chemin: "/api/panels/stories-inout", url: `/api/panels/stories-inout?team=${ID_A}&${PLAGE}` },
];

// Keys that carry a count or a share of a count, whatever the route.
const CLES_DE_COMPTE = /^(items|created|done|blocked|blockedN|share|total|throughput|defectsDone|storiesDone|count|n)$/;

function cles(valeur: unknown, sortie: string[] = []): string[] {
  if (Array.isArray(valeur)) valeur.forEach((v) => cles(v, sortie));
  else if (valeur !== null && typeof valeur === "object") {
    for (const [cle, interne] of Object.entries(valeur)) {
      sortie.push(cle);
      cles(interne, sortie);
    }
  }
  return sortie;
}

const contientNombre = (texte: string, nombre: number): boolean => new RegExp(`(?<![0-9.])${nombre}(?![0-9])`).test(texte);

test("coverage: every route registered under /api/dashboards/ and /api/panels/ is walked here, and none is walked that is not registered", async () => {
  const { app, routes } = await monter(REEL);
  const enregistrees = [...new Set(routes.filter((r) => r.url.startsWith("/api/dashboards/") || r.url.startsWith("/api/panels/")).map((r) => `${r.method} ${r.url}`))].sort();
  const parcourues = [...new Set(ROUTES.map((r) => `GET ${r.chemin}`))].sort();
  assert.deepEqual(parcourues, enregistrees);
  await app.close();
});

test("real dataset, counts not allowed: no key, no title sentinel and no count in any answer of the product-scope dashboard", async () => {
  const { app } = await monter(REEL);
  for (const { route, url } of ROUTES) {
    const r = await app.inject({ method: "GET", url });
    assert.equal(r.statusCode, 200, route);
    const corps = r.json();
    assert.equal(corps.dataset, "real", route);
    assert.deepEqual(controler(route, corps, [], [SENTINELLE, TITRE, CLE, "ZZSENT"]), [], route);
    assert.ok(!r.body.includes(CLE) && !r.body.includes(TITRE), route);
    for (const nombre of TOUS_LES_COMPTES) assert.ok(!contientNombre(r.body, nombre), `${route} ${nombre}`);
    for (const cle of cles(corps)) assert.ok(!CLES_DE_COMPTE.test(cle), `${route} key ${cle}`);
  }
  await app.close();
});

test("real dataset, counts not allowed: the answers of the panels are the reduced form, with no point and no total", async () => {
  const { app } = await monter(REEL);
  for (const code of CODES_PANNEAUX) {
    const equipe = code === "blocked-share" ? `team=${ID_A}&` : "";
    const r = await app.inject({ method: "GET", url: `/api/panels/${code}?${equipe}${PLAGE}` });
    const corps = r.json() as Record<string, unknown>;
    assert.equal(r.statusCode, 200, code);
    assert.deepEqual(corps.limits, ["reduced_form"], code);
    assert.ok(!("points" in corps) && !("total" in corps), code);
  }
  await app.close();
});

test("real dataset: the generic view route is closed, 404 NOT_FOUND, whatever the view asked", async () => {
  const { app } = await monter(REEL, true);
  for (const vue of CONTRAT.views) {
    const r = await app.inject({ method: "GET", url: `/api/views/${vue.name}` });
    assert.equal(r.statusCode, 404, vue.name);
    assert.deepEqual(r.json(), { error: "NOT_FOUND" }, vue.name);
  }
  await app.close();
});

test("synthetic dataset: each route serves a distinctive count and a count key, the key and title sentinels still never come out", async () => {
  const { app } = await monter(SYNTHETIQUE);
  for (const { route, url } of ROUTES) {
    const r = await app.inject({ method: "GET", url });
    assert.equal(r.statusCode, 200, route);
    const corps = r.json();
    assert.deepEqual(controler(route, corps, [], [SENTINELLE, TITRE, CLE, "ZZSENT"]), [], route);
    assert.ok(!r.body.includes(CLE) && !r.body.includes(TITRE), route);
    // The control is not vacuous, route by route: the complete mode carries a distinctive count and a key of the list.
    assert.ok(TOUS_LES_COMPTES.some((n) => contientNombre(r.body, n)), `${route} carries no distinctive count`);
    assert.ok(cles(corps).some((cle) => CLES_DE_COMPTE.test(cle)), `${route} carries no count key`);
  }
  await app.close();
});
