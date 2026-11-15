// Audit #629, A-78 (L3-07, R-20261107-26 decision 8, R-20261107-29 point 6 (b)): the threshold option of a request is removed; ?threshold is ignored on every view.
// Fake access, no database. Fictitious values only.
import assert from "node:assert/strict";
import { test } from "node:test";

import { construireServeur } from "../src/routes/serveur.ts";
import { AccesFictif, contrat, ligneStatut } from "./aide.ts";

const AUTRE = "v_team_ready_queue";
const LIGNE_AUTRE = { team: "x", quarter_start: "2026-01-01", ready: 12 };

async function lire(acces: AccesFictif, url: string) {
  const { app } = construireServeur({ contrat, acces, reglageSeuil: null, afficherNoms: true, journal: false, vuesServies: ["v_team_status", AUTRE] });
  const reponse = await app.inject({ method: "GET", url });
  await app.close();
  return { statut: reponse.statusCode, corps: reponse.json() as Record<string, unknown> };
}

test("A-78 : l'option ?threshold est ignorée sur une vue qui a des relations entre cellules", async () => {
  const { statut, corps } = await lire(new AccesFictif([LIGNE_AUTRE]), `/api/views/${AUTRE}?threshold=20`);
  assert.equal(statut, 200);
  assert.equal(corps.threshold, 5);
  assert.deepEqual((corps.rows as Array<Record<string, unknown>>)[0].ready, { state: "value", value: 12 });
});

test("A-78 : l'option ?threshold est aussi ignorée sur la vue sans relation (v_team_status)", async () => {
  const { statut, corps } = await lire(new AccesFictif([ligneStatut("A", 8)]), "/api/views/v_team_status?threshold=10");
  assert.equal(statut, 200);
  assert.equal(corps.threshold, 5);
  assert.deepEqual((corps.rows as Array<Record<string, unknown>>)[0].tickets, { state: "value", value: 8 });
});
