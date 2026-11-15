// Task 18.4: the refusals of the sheet routes that come from the computed body (threshold not fixed, chart outside the closed list) and the
// switch-off of the routes after the start check of the team identifiers. Fake storage, no database; invented figures.
import assert from "node:assert/strict";
import { test } from "node:test";

import { GraphiqueInconnu, PorteeNonServie, SeuilsNonFixes } from "@mothra/contract";

import { construireServeur } from "../src/routes/serveur.ts";
import type { OptionsFiches } from "../src/routes/fiches.ts";
import { AccesFictif, contrat } from "./aide.ts";
import { DepotMemoire, corpsSynthetique } from "./depot-memoire.ts";

const AUTEUR = { "x-mothra-user": "agile-lead-1" };
const DEMANDE = { chart: "lead_cycle_h5", scope: "team-a", dataDate: "2026-10-01" };

function monter(surcharge: Partial<OptionsFiches> = {}) {
  const depot = new DepotMemoire();
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: false,
    fiches: { depot, calculerCorps: async () => corpsSynthetique(), motifsNoms: [], reduite: false, aujourdhui: () => "2026-11-12", ...surcharge },
  });
  return { app, depot };
}

test("a chart outside the closed list is an invalid request, nothing is stored", async () => {
  const { app, depot } = monter({
    verifierCreation: async () => {
      throw new GraphiqueInconnu();
    },
  });
  const r = await app.inject({ method: "POST", url: "/api/sheets", headers: AUTEUR, payload: DEMANDE });
  assert.equal(r.statusCode, 400);
  assert.deepEqual(r.json(), { error: "INVALID_REQUEST" });
  assert.equal(depot.fiches.size, 0);
  await app.close();
});

test("a threshold not fixed refuses the creation with THRESHOLDS_NOT_SET (409), a code and nothing else", async () => {
  const { app, depot } = monter({
    verifierCreation: async () => {
      throw new SeuilsNonFixes(["h5_band"]);
    },
  });
  const r = await app.inject({ method: "POST", url: "/api/sheets", headers: AUTEUR, payload: DEMANDE });
  assert.equal(r.statusCode, 409);
  assert.deepEqual(r.json(), { error: "THRESHOLDS_NOT_SET" });
  assert.ok(!r.body.includes("h5_band"), "the missing code is not echoed");
  assert.equal(depot.fiches.size, 0);
  await app.close();
});

test("reading, review and publication of a sheet whose thresholds are not fixed answer THRESHOLDS_NOT_SET", async () => {
  const { app, depot } = monter({
    calculerCorps: async () => {
      throw new SeuilsNonFixes(["h5_floor"]);
    },
  });
  const id = await depot.creer({ ...DEMANDE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, createdBy: "agile-lead-1" });
  const lu = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(lu.statusCode, 409);
  assert.deepEqual(lu.json(), { error: "THRESHOLDS_NOT_SET" });
  const relu = await app.inject({ method: "POST", url: `/api/sheets/${id}/review`, headers: { "x-mothra-user": "agile-lead-2" } });
  assert.equal(relu.statusCode, 409);
  assert.deepEqual(relu.json(), { error: "THRESHOLDS_NOT_SET" });
  await app.close();
});

test("the body is asked for the sheet, with its chart, scope, data date and identifier", async () => {
  const vus: unknown[] = [];
  const { app, depot } = monter({
    calculerCorps: async (contexte) => {
      vus.push(contexte);
      return corpsSynthetique();
    },
  });
  const id = await depot.creer({ ...DEMANDE, createdBy: "agile-lead-1" });
  const lu = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(lu.statusCode, 200);
  assert.deepEqual(vus, [{ id, ...DEMANDE }]);
  await app.close();
});

test("switched off after the start check, the sheet and threshold routes answer the 404 of the application, the views still answer", async () => {
  const { app } = monter({ desactivees: () => true });
  for (const [method, url] of [
    ["POST", "/api/sheets"],
    ["GET", "/api/sheets/1"],
    ["GET", "/api/thresholds"],
    ["POST", "/api/thresholds"],
  ] as const) {
    const r = await app.inject({ method, url, headers: AUTEUR, payload: method === "POST" ? DEMANDE : undefined });
    assert.equal(r.statusCode, 404, `${method} ${url}`);
    assert.deepEqual(r.json(), { error: "NOT_FOUND" });
  }
  const vue = await app.inject({ method: "GET", url: "/api/views/v_team_status" });
  assert.equal(vue.statusCode, 200);
  await app.close();
});

test("a scope that is not a team one (the product level, a team name) is an invalid request, nothing is stored", async () => {
  const { app, depot } = monter({
    verifierCreation: async () => {
      throw new PorteeNonServie();
    },
  });
  const r = await app.inject({ method: "POST", url: "/api/sheets", headers: AUTEUR, payload: { ...DEMANDE, scope: "product" } });
  assert.equal(r.statusCode, 400);
  assert.deepEqual(r.json(), { error: "INVALID_REQUEST" });
  assert.equal(depot.fiches.size, 0);
  await app.close();
});

test("A2: the switch-off tests the route the router found, so an encoded path does not get round it", async () => {
  const { app } = monter({ desactivees: () => true });
  for (const url of ["/api/%73heets", "/api/sheets%2F1", "/api/%74hresholds", "/api/sheets/%31"]) {
    for (const method of ["GET", "POST"] as const) {
      const r = await app.inject({ method, url, headers: AUTEUR, payload: method === "POST" ? DEMANDE : undefined });
      assert.equal(r.statusCode, 404, `${method} ${url}`);
      assert.deepEqual(r.json(), { error: "NOT_FOUND" }, `${method} ${url}`);
    }
  }
  await app.close();
});

test("routes on by default and while the switch reads false", async () => {
  const { app } = monter({ desactivees: () => false });
  const r = await app.inject({ method: "GET", url: "/api/thresholds" });
  assert.equal(r.statusCode, 200);
  await app.close();
});
