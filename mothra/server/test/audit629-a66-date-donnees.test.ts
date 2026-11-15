// Audit #629, A-66 (R-20261112-30, server variant): the data date of a sheet is bounded at creation (not after the UTC day, in the current UTC
// quarter), a draft whose quarter is no longer the current one is served without a body (DATA_DATE_STALE), and the rows a view gives are
// checked against the window of the data date (midnight race at a quarter change). Fake storage and access, invented figures, no database.
import assert from "node:assert/strict";
import { mock, test } from "node:test";

import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";
import { SchemaFicheSansCorps } from "@mothra/contract";
import type { Contrat, Vue } from "@mothra/contract";

import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { creerCalculCorps } from "../src/fiches/corps.ts";
import { creerCalculPanneaux } from "../src/fiches/panneaux.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import { AccesFictif, SENTINELLE, contrat, journalCapture } from "./aide.ts";
import { DepotMemoire, corpsSynthetique } from "./depot-memoire.ts";

const AUTEUR = { "x-mothra-user": "agile-lead-1" };
const RELECTEUR = { "x-mothra-user": "agile-lead-2" };
const DEMANDE = { chart: "lead_cycle_h5", scope: "team-a", dataDate: "2026-10-01" };
const CODE_HORS_PLAGE = { error: "DATA_DATE_OUT_OF_RANGE" };
const CODE_PERIMEE = { error: "DATA_DATE_STALE" };

function monter(jour: () => string, depot = new DepotMemoire()) {
  const appels: unknown[] = [];
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: false,
    fiches: {
      depot,
      calculerCorps: async (contexte) => {
        appels.push(contexte);
        return corpsSynthetique();
      },
      motifsNoms: [],
      reduite: false,
      aujourdhui: jour,
    },
  });
  return { app, depot, appels };
}

const creer = (app: ReturnType<typeof monter>["app"], dataDate: string) =>
  app.inject({ method: "POST", url: "/api/sheets", headers: AUTEUR, payload: { ...DEMANDE, dataDate } });

// ---- 1. Creation: not after the UTC day, in the current UTC quarter -------------------------------------------------------------------------

test("creation: a data date in the future or in a past quarter is refused with a code and nothing else, nothing is stored", async () => {
  const { app, depot } = monter(() => "2026-11-12");
  for (const refusee of ["2026-11-13", "2027-01-01", "2028-02-29", "2026-09-30", "2025-11-12"]) {
    const r = await creer(app, refusee);
    assert.equal(r.statusCode, 422, refusee);
    assert.deepEqual(r.json(), CODE_HORS_PLAGE, refusee);
    assert.ok(!r.body.includes(refusee) && !r.body.includes("2026-11-12"), "no date is echoed");
  }
  assert.equal(depot.fiches.size, 0);
  for (const acceptee of ["2026-10-01", "2026-11-12", "2026-11-01"]) {
    assert.equal((await creer(app, acceptee)).statusCode, 200, acceptee);
  }
  await app.close();
});

test("creation: the first day of a quarter, today included, is accepted; the last day of the quarter before is refused", async () => {
  const { app } = monter(() => "2026-01-01");
  assert.equal((await creer(app, "2026-01-01")).statusCode, 200);
  const r = await creer(app, "2025-12-31");
  assert.equal(r.statusCode, 422);
  assert.deepEqual(r.json(), CODE_HORS_PLAGE);
  await app.close();
});

test("creation, time zone: 1 January 00:30 in Paris is 31 December in UTC, so a data date of 1 January is in the future (injected day)", async () => {
  const { app, depot } = monter(() => "2025-12-31");
  const r = await creer(app, "2026-01-01");
  assert.equal(r.statusCode, 422);
  assert.deepEqual(r.json(), CODE_HORS_PLAGE);
  assert.equal(depot.fiches.size, 0);
  assert.equal((await creer(app, "2025-12-31")).statusCode, 200);
  await app.close();
});

test("creation, time zone: the default clock is the UTC day, read at the request (1 January 00:30 in Paris = 2025-12-31T23:30Z)", async (t) => {
  t.after(() => mock.timers.reset());
  mock.timers.enable({ apis: ["Date"], now: Date.parse("2025-12-31T23:30:00Z") });
  const depot = new DepotMemoire();
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: false,
    fiches: { depot, calculerCorps: async () => corpsSynthetique(), motifsNoms: [], reduite: false },
  });
  const r = await creer(app, "2026-01-01");
  assert.equal(r.statusCode, 422);
  assert.deepEqual(r.json(), CODE_HORS_PLAGE);
  assert.equal(depot.fiches.size, 0);
  assert.equal((await creer(app, "2025-12-31")).statusCode, 200);
  await app.close();
});

// ---- 2. A draft whose quarter is no longer the current one: no live body --------------------------------------------------------------------

test("a stale draft is read without a body, with the code only; nothing is computed", async () => {
  let jour = "2026-11-12";
  const { app, depot, appels } = monter(() => jour);
  const id = await depot.creer({ ...DEMANDE, dataDate: "2026-10-01", managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, createdBy: "agile-lead-1" });
  assert.equal((await app.inject({ method: "GET", url: `/api/sheets/${id}` })).statusCode, 200);
  assert.equal(appels.length, 1, "the current quarter: the body is computed");
  jour = "2027-01-04";
  const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(r.statusCode, 200);
  assert.deepEqual(r.json(), { id, state: "draft", managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, bodyState: "DATA_DATE_STALE" });
  assert.equal(appels.length, 1, "no body computed for the stale draft");
  const champsDuContrat = Object.keys((SchemaFicheSansCorps as unknown as { properties: object }).properties);
  assert.deepEqual(Object.keys(r.json() as object).sort(), [...champsDuContrat].sort(), "the answer has the fields of the contract and no other");
  await app.close();
});

test("quarter change around midnight UTC: a draft of 31 December is read with its body at 23:30 UTC, without it at 00:30 UTC (injected days)", async () => {
  let jour = "2026-12-31";
  const { app, depot, appels } = monter(() => jour);
  const id = await depot.creer({ ...DEMANDE, dataDate: "2026-12-31", managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, createdBy: "agile-lead-1" });
  const avant = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(avant.statusCode, 200);
  assert.equal((avant.json() as { bodyState?: string }).bodyState, undefined);
  assert.equal(appels.length, 1);
  jour = "2027-01-01";
  const apres = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(apres.statusCode, 200);
  assert.equal((apres.json() as { bodyState?: string }).bodyState, "DATA_DATE_STALE");
  assert.equal(appels.length, 1, "no body computed after midnight UTC");
  await app.close();
});

test("a stale draft: a change is refused DATA_DATE_STALE and stores nothing; the review and the publication are refused too, nothing is frozen", async () => {
  let jour = "2026-11-12";
  const { app, depot, appels } = monter(() => jour);
  const id = await depot.creer({ ...DEMANDE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, createdBy: "agile-lead-1" });
  jour = "2027-01-04";
  const modifiee = await app.inject({ method: "PATCH", url: `/api/sheets/${id}`, headers: AUTEUR, payload: { effect: { text: "New.", lang: "en" } } });
  assert.equal(modifiee.statusCode, 409);
  assert.deepEqual(modifiee.json(), CODE_PERIMEE);
  assert.equal((await depot.lire(id))?.effect?.text, "E.", "refused before anything is written");
  const relue = await app.inject({ method: "POST", url: `/api/sheets/${id}/review`, headers: RELECTEUR });
  assert.equal(relue.statusCode, 409);
  assert.deepEqual(relue.json(), CODE_PERIMEE);
  assert.equal((await depot.lire(id))?.state, "draft", "refused before anything is written");
  // A sheet reviewed before the quarter changed: its publication is refused.
  await depot.relire(id, "agile-lead-2");
  const publiee = await app.inject({ method: "POST", url: `/api/sheets/${id}/publish`, headers: AUTEUR });
  assert.equal(publiee.statusCode, 409);
  assert.deepEqual(publiee.json(), CODE_PERIMEE);
  assert.equal((await depot.lire(id))?.state, "reviewed");
  assert.equal((await depot.lire(id))?.published, undefined, "nothing frozen");
  assert.equal(appels.length, 0, "no body computed for review, change, reading or publication");
  await app.close();
});

test("a published sheet stays served from its frozen content, whatever the quarter", async () => {
  let jour = "2026-11-12";
  const { app, depot } = monter(() => jour);
  const id = await depot.creer({ ...DEMANDE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, createdBy: "agile-lead-1" });
  assert.equal((await app.inject({ method: "POST", url: `/api/sheets/${id}/review`, headers: RELECTEUR })).statusCode, 200);
  assert.equal((await app.inject({ method: "POST", url: `/api/sheets/${id}/publish`, headers: AUTEUR })).statusCode, 200);
  jour = "2027-05-01";
  const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(r.statusCode, 200);
  const corps = r.json() as { state: string; bodyState?: string; verdict?: string };
  assert.equal(corps.state, "published");
  assert.equal(corps.bodyState, undefined);
  assert.ok(corps.verdict !== undefined);
  await app.close();
});

// ---- 3. The rows read are those of the window of the data date ------------------------------------------------------------------------------

const DEBUTS_2025 = ["2025-04-01", "2025-07-01", "2025-10-01"]; // the three closed quarters of a data date in the first quarter of 2026 (R-20261114-49)
// The window the views give once 1 April 2026 has begun: one quarter later than the window of a data date in the first quarter of 2026.
const DEBUTS_2026 = ["2025-07-01", "2025-10-01", "2026-01-01"];
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe("team-a") });
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

class AccesParVue implements AccesVues {
  readonly debuts: string[];
  constructor(debuts: string[]) {
    this.debuts = debuts;
  }
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    const juge = this.debuts[2];
    switch (vue.name) {
      case "v_team_lead_time_throughput":
        return [
          ...this.debuts.map((debut) => ({
            team: "team-a",
            period: "quarter",
            quarter_start: debut,
            throughput: 30,
            items_lt: 30,
            items_ct: 30,
            items_old: 5,
            items_without_commitment: 0,
            lead_median_days: 15,
            lead_p85_days: 30,
            cycle_median_days: 10,
            cycle_p85_days: 20,
            lead_median_days_excl_old: 15,
            lead_p85_days_excl_old: 30,
            cycle_median_days_excl_old: 10,
            cycle_p85_days_excl_old: 20,
            ticket_key: SENTINELLE,
          })),
        ];
      case "v_task_without_team_share":
        return this.debuts.map((d) => ({ quarter_start: d, tasks_done: 30, tasks_without_team: 6, share_percent: 20 }));
      case "v_unplanned_share":
        return this.debuts.map((d) => ({ quarter_start: d, unplanned: 10, unplanned_n: 80, share_percent: 12.5 }));
      case "v_team_ready_queue":
        return [{ team: "team-a", quarter_start: juge, ready: 12 }];
      case "v_team_blocked_share":
        return [{ team: "team-a", quarter_start: juge, blocked_n: 30, blocked: 9, share_percent: 30 }];
      default:
        return [];
    }
  }
}

async function monterAvecVues(debuts: string[], jour: string, journal: false | { level: string; stream: { write(message: string): void } } = false) {
  const depot = new DepotMemoire();
  for (const [code, value] of SEUILS) await depot.ajouterSeuil({ code, value, setOn: "2026-02-01", setBy: "author-1" });
  const acces = new AccesParVue(debuts);
  const calcul = creerCalculCorps({ acces, contrat, seuil: 5, depot, identifiantEquipe, mode: { jeu: "synthetic", comptesAutorises: false } });
  const { app } = construireServeur({
    contrat,
    acces,
    reglageSeuil: null,
    journal,
    fiches: { depot, calculerCorps: calcul.calculerCorps, verifierCreation: calcul.verifierCreation, motifsNoms: [], reduite: false, aujourdhui: () => jour },
  });
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: "2026-03-15", managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, createdBy: "agile-lead-1" });
  return { app, depot, id };
}

test("the rows of the window of the data date are served (control: views read before midnight)", async () => {
  const { app, id } = await monterAvecVues(DEBUTS_2025, "2026-03-31");
  const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(r.statusCode, 200);
  assert.equal((r.json() as { bodyState?: string }).bodyState, undefined);
  await app.close();
});

test("midnight race: today is 31 March 23:59:59 UTC, the views already give the window of the next quarter: refused DATA_DATE_STALE, nothing frozen", async () => {
  const { app, depot, id } = await monterAvecVues(DEBUTS_2026, "2026-03-31");
  const lue = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(lue.statusCode, 409);
  assert.deepEqual(lue.json(), CODE_PERIMEE);
  assert.ok(!lue.body.includes("2026-"), "no date, no row in the refusal");
  await depot.relire(id, "agile-lead-2");
  const publiee = await app.inject({ method: "POST", url: `/api/sheets/${id}/publish`, headers: AUTEUR });
  assert.equal(publiee.statusCode, 409);
  assert.deepEqual(publiee.json(), CODE_PERIMEE);
  assert.equal((await depot.lire(id))?.published, undefined);
  await app.close();
});

test("midnight race at the review: the views give the window of the next quarter: refused DATA_DATE_STALE, the draft stays a draft", async () => {
  const { app, depot, id } = await monterAvecVues(DEBUTS_2026, "2026-03-31");
  const relue = await app.inject({ method: "POST", url: `/api/sheets/${id}/review`, headers: RELECTEUR });
  assert.equal(relue.statusCode, 409);
  assert.deepEqual(relue.json(), CODE_PERIMEE);
  assert.equal((await depot.lire(id))?.state, "draft", "the body is read before the review is written");
  await app.close();
});

test("the log of the refusals holds the code and no date: 422 at creation, 409 at the review of a stale draft (own log line), 409 at the review (window race)", async () => {
  const journal = journalCapture();
  const jour = "2026-11-12";
  const depot = new DepotMemoire();
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: { level: "info", stream: journal.stream },
    fiches: { depot, calculerCorps: async () => corpsSynthetique(), motifsNoms: [], reduite: false, aujourdhui: () => jour },
  });
  assert.equal((await creer(app, "2026-11-13")).statusCode, 422);
  const perimee = await depot.creer({ ...DEMANDE, dataDate: "2026-07-01", managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, createdBy: "agile-lead-1" });
  assert.equal((await app.inject({ method: "POST", url: `/api/sheets/${perimee}/review`, headers: RELECTEUR })).statusCode, 409);
  assert.ok(journal.texte().includes('"code":"DATA_DATE_STALE"'), "the 409 of the review of a stale draft is logged with its code, before the window race");
  await app.close();
  const course = await monterAvecVues(DEBUTS_2026, "2026-03-31", { level: "info", stream: journal.stream });
  assert.equal((await course.app.inject({ method: "POST", url: `/api/sheets/${course.id}/review`, headers: RELECTEUR })).statusCode, 409);
  await course.app.close();
  const texte = journal.texte();
  assert.ok(texte.includes('"code":"DATA_DATE_OUT_OF_RANGE"'), "the 422 of the creation is logged with its code");
  assert.ok(texte.includes('"code":"DATA_DATE_STALE"'), "the 409 of the window race is logged with its code");
  assert.ok(!/\d{4}-\d{2}-\d{2}/.test(texte), "no date in the log");
});

// The panels: the same check against the day of the route.
const VUE_FLUX: Vue = { name: "v_team_flow_inout", schema: "flow", roleKind: "flow", countColumns: ["created", "done"], plainColumns: ["team", "quarter_start", "type_group"] };
const CONTRAT_PANNEAUX: Contrat = { ...contrat, views: [...contrat.views, VUE_FLUX] };

function monterPanneaux(debuts: string[]) {
  const acces: AccesVues = {
    async lireVue(vue: Vue) {
      return vue.name === "v_team_blocked_share"
        ? debuts.map((d, i) => ({ team: "team-a", quarter_start: d, blocked_n: 40, blocked: 12 + i, share_percent: 30 + i }))
        : [];
    },
  };
  const calcul = creerCalculPanneaux({ acces, contrat: CONTRAT_PANNEAUX, seuil: 5, identifiantEquipe });
  const { app } = construireServeur({
    contrat: CONTRAT_PANNEAUX,
    acces,
    reglageSeuil: null,
    journal: false,
    panneaux: { ...calcul, mode: { jeu: "synthetic", comptesAutorises: false }, aujourdhui: () => "2026-03-31" },
  });
  return app;
}

test("panels: rows of the window of the day are served, rows of the next window are refused DATA_DATE_STALE", async () => {
  const url = `/api/panels/blocked-share?team=${identifiantEquipe("team-a")}&from=2025-Q2&to=2025-Q4`;
  const bon = monterPanneaux(DEBUTS_2025);
  assert.equal((await bon.inject({ method: "GET", url })).statusCode, 200);
  await bon.close();
  const decale = monterPanneaux(DEBUTS_2026);
  const r = await decale.inject({ method: "GET", url });
  assert.equal(r.statusCode, 409);
  assert.deepEqual(r.json(), CODE_PERIMEE);
  await decale.close();
});
