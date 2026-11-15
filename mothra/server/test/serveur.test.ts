// Tasks 6.2, 6.4, 6.5 and the logs of 6.6: the one route of slice 0, the closed list before any connection, the response schema per
// route, the six masking points with the parity cases, the codes without detail, logs without body or value. Fake access, no database.
import assert from "node:assert/strict";
import { test } from "node:test";

import { chargerCasParite } from "@mothra/contract";
import Fastify from "fastify";
import Type from "typebox";

import { BaseIndisponible } from "../src/db/acces.ts";
import { construireServeur, exigerSchemaDeReponse, nettoyer } from "../src/routes/serveur.ts";
import { AccesFictif, CHEMIN_CAS_PARITE, SENTINELLE, SECRET_SENTINELLE, contrat, journalCapture, ligneStatut } from "./aide.ts";

// R-20261104-69 Q1: the existing checks below read the route with the setting on (the column `team` served); the setting off has its own
// test further down. Not a weakening: the assertions are unchanged, the route's default (off) is tested separately.
function serveur(acces: AccesFictif, reglageSeuil: number | null = null, journal?: ReturnType<typeof journalCapture>) {
  return construireServeur({
    contrat,
    acces,
    reglageSeuil,
    afficherNoms: true,
    journal: journal === undefined ? false : { level: "info", stream: journal.stream },
  });
}

async function lire(acces: AccesFictif, url: string, reglageSeuil: number | null = null) {
  const { app } = serveur(acces, reglageSeuil);
  const reponse = await app.inject({ method: "GET", url });
  await app.close();
  return { statut: reponse.statusCode, corps: reponse.json() as Record<string, unknown>, brut: reponse.body };
}

// ---- 6.2: the route and the closed list

test("the skeleton route serves the status by team view with structured count cells, one of them masked at 5", async () => {
  const acces = new AccesFictif([ligneStatut("Team A", 12), ligneStatut("Team B", 2)]);
  const { statut, corps } = await lire(acces, "/api/views/v_team_status");
  assert.equal(statut, 200);
  assert.equal(corps.view, "v_team_status");
  assert.equal(corps.threshold, 5);
  assert.deepEqual(corps.sources, ["flow"]);
  assert.deepEqual(corps.columns, ["team", "type", "status_category", "status", "tickets"]);
  const rows = corps.rows as Array<Record<string, unknown>>;
  assert.deepEqual(rows[0].tickets, { state: "value", value: 12 });
  assert.deepEqual(rows[1].tickets, { state: "masked", threshold: 5 });
  assert.equal(rows[0].team, "Team A");
  assert.deepEqual(acces.appels, ["v_team_status"]);
});

test("every name of the parity cases that the contract refuses answers UNKNOWN_VIEW 404 and records no connection", async () => {
  const cas = chargerCasParite(CHEMIN_CAS_PARITE);
  const refusees = cas.views.filter((c) => !c.accepted);
  assert.ok(refusees.length >= 8);
  for (const c of refusees) {
    const acces = new AccesFictif([ligneStatut("Team A", 12)]);
    const { statut, corps } = await lire(acces, `/api/views/${encodeURIComponent(c.view)}`);
    assert.equal(statut, 404, c.name);
    assert.deepEqual(corps, { error: "UNKNOWN_VIEW" }, c.name);
    assert.deepEqual(acces.appels, [], c.name);
  }
});

test("an empty name, a table, a qualified name, another case and an injection text are refused before any connection", async () => {
  for (const nom of ["", "issues", "flow.issues", "flow.v_team_status", "V_TEAM_STATUS", "v_team_status;--", "v_teams", "v_quality_by_team"]) {
    const acces = new AccesFictif([ligneStatut("Team A", 12)]);
    const { statut, corps } = await lire(acces, `/api/views/${encodeURIComponent(nom)}`);
    assert.equal(statut, 404, JSON.stringify(nom));
    assert.deepEqual(corps, { error: "UNKNOWN_VIEW" });
    assert.deepEqual(acces.appels, []);
  }
});

test("an unknown path under /api/ answers NOT_FOUND (only an unknown view name is UNKNOWN_VIEW) and records no connection", async () => {
  for (const url of ["/api/autre", "/api/unknown", "/api/views/x/y", "/api/views", "/api"]) {
    const acces = new AccesFictif([]);
    const { statut, corps } = await lire(acces, url);
    assert.equal(statut, 404, url);
    assert.deepEqual(corps, { error: "NOT_FOUND" }, url);
    assert.deepEqual(acces.appels, [], url);
  }
});

test("the API route is registered once, as GET /api/views/:view; the bundle routes follow", () => {
  const { routes } = serveur(new AccesFictif());
  assert.deepEqual(routes, [
    { method: "GET", url: "/api/views/:view" },
    { method: "GET", url: "/" },
    { method: "GET", url: "/*" },
  ]);
});

// ---- 6.4: a response schema per route

test("a field the service layer returns beyond the declared ones is not in the answer (sentinel field absent)", async () => {
  const app = Fastify({ logger: false });
  exigerSchemaDeReponse(app);
  const schema = nettoyer({
    response: { 200: Type.Object({ declare: Type.String() }, { additionalProperties: false }) },
  });
  app.get("/essai", { schema }, async () => ({ declare: "ok", supplementaire: SENTINELLE }));
  const reponse = await app.inject({ method: "GET", url: "/essai" });
  assert.equal(reponse.statusCode, 200);
  assert.deepEqual(reponse.json(), { declare: "ok" });
  assert.ok(!reponse.body.includes(SENTINELLE));
  await app.close();
});

test("an extra field in a row of the real route is not in the answer", async () => {
  const acces = new AccesFictif([ligneStatut("Team A", 12, { champ_inconnu: SENTINELLE, key: "ABC-123" })]);
  const { statut, brut } = await lire(acces, "/api/views/v_team_status");
  assert.equal(statut, 200);
  assert.ok(!brut.includes(SENTINELLE));
  assert.ok(!brut.includes("ABC-123"));
  assert.ok(!brut.includes("champ_inconnu"));
});

test("a route registered without a response schema fails, naming the route", async () => {
  const app = Fastify({ logger: false });
  exigerSchemaDeReponse(app);
  await assert.rejects(async () => {
    app.get("/sans-schema", async () => ({}));
    await app.ready();
  }, /route sans schéma de réponse : GET \/sans-schema/);
});

test("a route with a schema but no 200 answer also fails", async () => {
  const app = Fastify({ logger: false });
  exigerSchemaDeReponse(app);
  const schema = nettoyer({ response: { 404: Type.Object({ error: Type.String() }) } });
  await assert.rejects(async () => {
    app.get("/sans-200", { schema }, async () => ({}));
    await app.ready();
  }, /\/sans-200/);
});

// ---- 6.5: the six masking points with the parity cases

test("the parity cells played through the route give the expected cells (points 2, 3 and 4)", async () => {
  const cas = chargerCasParite(CHEMIN_CAS_PARITE);
  for (const c of cas.cells) {
    const vue = contrat.views.find((v) => v.name === c.view);
    if (vue === undefined) {
      continue;
    }
    const acces = new AccesFictif([ligneStatut("Team A", 12, { [c.column]: c.value })]);
    const { statut, corps } = await lire(acces, `/api/views/${c.view}`, c.threshold);
    assert.equal(statut, 200, c.name);
    const ligne = (corps.rows as Array<Record<string, unknown>>)[0];
    assert.deepEqual(ligne[c.column], c.expected, c.name);
  }
});

test("a team with 12 tickets is a value cell and a team with 2 a masked cell with threshold 5", async () => {
  const { corps } = await lire(new AccesFictif([ligneStatut("A", 12), ligneStatut("B", 2)]), "/api/views/v_team_status");
  const rows = corps.rows as Array<Record<string, unknown>>;
  assert.deepEqual(rows[0].tickets, { state: "value", value: 12 });
  assert.deepEqual(rows[1].tickets, { state: "masked", threshold: 5 });
});

test("a lower option never lowers the threshold; a higher option does not raise it (the option is ignored)", async () => {
  const bas = await lire(new AccesFictif([ligneStatut("A", 3)]), "/api/views/v_team_status?threshold=1");
  assert.equal(bas.corps.threshold, 5);
  assert.deepEqual((bas.corps.rows as Array<Record<string, unknown>>)[0].tickets, { state: "masked", threshold: 5 });
  const haut = await lire(new AccesFictif([ligneStatut("A", 8)]), "/api/views/v_team_status?threshold=10");
  assert.equal(haut.corps.threshold, 5);
  assert.deepEqual((haut.corps.rows as Array<Record<string, unknown>>)[0].tickets, { state: "value", value: 8 });
});

test("a text in the threshold option is ignored; the setting can raise but never lower", async () => {
  const texte = await lire(new AccesFictif([ligneStatut("A", 8)]), "/api/views/v_team_status?threshold=abc");
  assert.equal(texte.corps.threshold, 5);
  const reglage = await lire(new AccesFictif([ligneStatut("A", 8)]), "/api/views/v_team_status?threshold=6", 9);
  assert.equal(reglage.corps.threshold, 9);
  const bas = await lire(new AccesFictif([ligneStatut("A", 8)]), "/api/views/v_team_status", 2);
  assert.equal(bas.corps.threshold, 5);
});

test("a PostgreSQL bigint count read as a digit string, and a NULL, become cells", async () => {
  const { corps } = await lire(new AccesFictif([ligneStatut("A", "17"), ligneStatut("B", null), ligneStatut("C", "4")]), "/api/views/v_team_status");
  const rows = corps.rows as Array<Record<string, unknown>>;
  assert.deepEqual(rows[0].tickets, { state: "value", value: 17 });
  assert.deepEqual(rows[1].tickets, { state: "masked", threshold: 5 });
  assert.deepEqual(rows[2].tickets, { state: "masked", threshold: 5 });
});

test("a masked cell has no value property and no field from which the value derives", async () => {
  const { corps, brut } = await lire(new AccesFictif([ligneStatut("A", 3)]), "/api/views/v_team_status");
  const cellule = (corps.rows as Array<Record<string, unknown>>)[0].tickets as Record<string, unknown>;
  assert.deepEqual(Object.keys(cellule).sort(), ["state", "threshold"]);
  assert.ok(!brut.includes("masqué"));
});

test("a non-count column holding a small number is returned as it is, not masked", async () => {
  const { corps } = await lire(new AccesFictif([ligneStatut("A", 12, { status: 3 })]), "/api/views/v_team_status");
  assert.equal((corps.rows as Array<Record<string, unknown>>)[0].status, 3);
});

test("a view with no row answers an empty list", async () => {
  const { statut, corps } = await lire(new AccesFictif([]), "/api/views/v_team_status");
  assert.equal(statut, 200);
  assert.deepEqual(corps.rows, []);
});

test("a database failure answers DATABASE_UNAVAILABLE 503 with no detail", async () => {
  const acces = new AccesFictif([], new Error(`connect ECONNREFUSED password=${SECRET_SENTINELLE} ${SENTINELLE}`));
  const { statut, corps, brut } = await lire(acces, "/api/views/v_team_status");
  assert.equal(statut, 503);
  assert.deepEqual(corps, { error: "DATABASE_UNAVAILABLE" });
  assert.ok(!brut.includes("ECONNREFUSED") && !brut.includes(SENTINELLE) && !brut.includes(SECRET_SENTINELLE));
});

test("the driver's own failure type answers the same way", async () => {
  const { statut, corps } = await lire(new AccesFictif([], new BaseIndisponible()), "/api/views/v_team_status");
  assert.equal(statut, 503);
  assert.deepEqual(corps, { error: "DATABASE_UNAVAILABLE" });
});

test("a failure of the service layer answers INTERNAL 500 with no detail", async () => {
  const { statut, corps, brut } = await lire(new AccesFictif([ligneStatut("A", { sentinelle: SENTINELLE } as unknown as number)]), "/api/views/v_team_status");
  assert.equal(statut, 500);
  assert.deepEqual(corps, { error: "INTERNAL" });
  assert.ok(!brut.includes(SENTINELLE));
});

// ---- review fixes: framework errors, repeated option, served views, schema per view

test("a badly encoded URL answers UNKNOWN_VIEW, never the framework's own body", async () => {
  for (const url of ["/api/views/%zz", "/api/views/%E0%A4%A", "/api/views/v_team_status%"]) {
    const acces = new AccesFictif([ligneStatut("Team A", 12)]);
    const { statut, corps, brut } = await lire(acces, url);
    assert.equal(statut, 404, url);
    assert.deepEqual(corps, { error: "UNKNOWN_VIEW" }, url);
    assert.equal(brut, '{"error":"UNKNOWN_VIEW"}', url);
    assert.deepEqual(acces.appels, [], url);
  }
});

test("a parameter that is too long answers UNKNOWN_VIEW, never the framework's own body", async () => {
  const acces = new AccesFictif([ligneStatut("Team A", 12)]);
  const { statut, corps, brut } = await lire(acces, `/api/views/${"a".repeat(500)}`);
  assert.equal(statut, 404);
  assert.deepEqual(corps, { error: "UNKNOWN_VIEW" });
  assert.equal(brut, '{"error":"UNKNOWN_VIEW"}');
  assert.deepEqual(acces.appels, []);
});

test("a repeated threshold option is ignored: no 500, the threshold stays the effective one", async () => {
  for (const url of [
    "/api/views/v_team_status?threshold=1&threshold=9",
    "/api/views/v_team_status?threshold=10&threshold=abc",
    "/api/views/v_team_status?threshold[a]=10",
  ]) {
    const { statut, corps } = await lire(new AccesFictif([ligneStatut("A", 8)]), url);
    assert.equal(statut, 200, url);
    assert.equal(corps.threshold, 5, url);
    assert.deepEqual((corps.rows as Array<Record<string, unknown>>)[0].tickets, { state: "value", value: 8 }, url);
  }
});

// R-20261030-49: masking is refused for a view the rules do not declare, so the second flow view is a declared one of the real contract
// (the ready queue: team, quarter_start, ready); the quality view is never read through masking (it is never served).
const AUTRE = "v_team_ready_queue";
const LIGNE_AUTRE = { team: "x", quarter_start: "2026-01-01", ready: 12 };
const VUE_QUALITE = { name: "v_qualite", schema: "quality", roleKind: "quality", countColumns: ["m"], plainColumns: ["b"] };
const CONTRAT_LARGE = { views: [...contrat.views, VUE_QUALITE] };

async function lireAvec(options: { vuesServies?: readonly string[] }, acces: AccesFictif, url: string) {
  const { app } = construireServeur({ contrat: CONTRAT_LARGE, acces, reglageSeuil: null, journal: false, afficherNoms: true, ...options });
  const reponse = await app.inject({ method: "GET", url });
  await app.close();
  return { statut: reponse.statusCode, corps: reponse.json() as Record<string, unknown> };
}

test("a view of the contract outside the served list answers UNKNOWN_VIEW and records no connection", async () => {
  for (const nom of [AUTRE, "v_qualite"]) {
    const acces = new AccesFictif([LIGNE_AUTRE]);
    const { statut, corps } = await lireAvec({}, acces, `/api/views/${nom}`);
    assert.equal(statut, 404, nom);
    assert.deepEqual(corps, { error: "UNKNOWN_VIEW" }, nom);
    assert.deepEqual(acces.appels, [], nom);
  }
});

test("a flow view named in the served list is served, a quality view never is, even when listed", async () => {
  const servi = new AccesFictif([LIGNE_AUTRE]);
  const ok = await lireAvec({ vuesServies: ["v_team_status", AUTRE, "v_qualite"] }, servi, `/api/views/${AUTRE}`);
  assert.equal(ok.statut, 200);
  assert.deepEqual(servi.appels, [AUTRE]);
  const refuse = new AccesFictif([{ b: "x", m: 12 }]);
  const non = await lireAvec({ vuesServies: ["v_team_status", AUTRE, "v_qualite"] }, refuse, "/api/views/v_qualite");
  assert.equal(non.statut, 404);
  assert.deepEqual(refuse.appels, []);
});

test("the response schema is per view: a row holds the columns of its own view and nothing of another one", async () => {
  const acces = new AccesFictif([{ ...LIGNE_AUTRE, type: SENTINELLE, tickets: 99, champ_hors_vue: SENTINELLE }]);
  const { corps } = await lireAvec({ vuesServies: ["v_team_status", AUTRE] }, acces, `/api/views/${AUTRE}`);
  assert.deepEqual(corps.columns, ["team", "quarter_start", "ready"]);
  assert.deepEqual(corps.rows, [{ team: "x", kind: "team", quarter_start: "2026-01-01", ready: { state: "value", value: 12 } }]);
  assert.ok(!JSON.stringify(corps).includes(SENTINELLE));
});

// R-20261104-69 Q1: the generic route leaves the column `team` out unless the setting is on (same point of service as the dashboard).
test("setting off or absent: no served row nor column holds `team`; setting on: it is served", async () => {
  for (const [nom, options] of [["absent", {}], ["false", { afficherNoms: false }], ["true", { afficherNoms: true }]] as const) {
    const acces = new AccesFictif([ligneStatut("Team A", 12), ligneStatut("Team B", 2)]);
    const { app } = construireServeur({ contrat, acces, reglageSeuil: null, journal: false, ...options });
    const reponse = await app.inject({ method: "GET", url: "/api/views/v_team_status" });
    await app.close();
    assert.equal(reponse.statusCode, 200, nom);
    const corps = reponse.json() as { columns: string[]; rows: Array<Record<string, unknown>> };
    assert.equal(corps.rows.length, 2, nom);
    if (nom === "true") {
      assert.ok(corps.columns.includes("team"), nom);
      assert.deepEqual(corps.rows.map((r) => r.team), ["Team A", "Team B"], nom);
    } else {
      assert.ok(!corps.columns.includes("team"), nom);
      assert.ok(corps.rows.every((r) => !("team" in r)), nom);
      assert.ok(!reponse.body.includes("Team A"), nom);
    }
  }
});

// ---- 6.6: logs

test("the log of a request holds no sentinel, no cell value, no secret, no body and no URL text", async () => {
  const journal = journalCapture();
  const acces = new AccesFictif([ligneStatut(SENTINELLE, 12), ligneStatut("Team B", 2)]);
  const { app } = serveur(acces, null, journal);
  await app.inject({ method: "GET", url: "/api/views/v_team_status" });
  await app.inject({ method: "GET", url: `/api/views/${SENTINELLE}` });
  await app.inject({ method: "GET", url: "/api/views/v_team_status?threshold=1" });
  const basPanne = new AccesFictif([], new Error(`${SENTINELLE} ${SECRET_SENTINELLE}`));
  const second = serveur(basPanne, null, journal);
  await second.app.inject({ method: "GET", url: "/api/views/v_team_status" });
  const surcharge = serveur(new AccesFictif([ligneStatut("A", { x: SENTINELLE } as unknown as number)]), null, journal);
  await surcharge.app.inject({ method: "GET", url: "/api/views/v_team_status" });
  await app.close();
  await second.app.close();
  await surcharge.app.close();
  const texte = journal.texte();
  assert.ok(texte.length > 0, "the failures are logged as codes");
  for (const interdit of [SENTINELLE, SECRET_SENTINELLE, "Team B", "ECONNREFUSED", '"value":12', "v_team_status"]) {
    assert.ok(!texte.includes(interdit), `the log must not hold: ${interdit === SENTINELLE ? "sentinel" : interdit.length}`);
  }
});
