// Task 18.4: the sheet routes at the start. Registered only on the synthetic dataset (until task 19.5) and with a complete storage access;
// switched off, the rest served, when two team names give one identifier (R-20261030-61). Synthetic team names; the hash function of the
// contract is replaced by a declared double that forces the collision. No database.
import assert from "node:assert/strict";
import { test } from "node:test";

import { demarrer, preparer } from "../src/demarrage.ts";
import type { OptionsDemarrage } from "../src/demarrage.ts";
import { PHRASE_COLLISION_EQUIPES, collisionsDIdentifiants, nomsDEquipes } from "../src/fiches/equipes.ts";
import { AccesFictif, CHEMIN_CONTRAT, contrat, envMinimal } from "./aide.ts";
import { DepotMemoire } from "./depot-memoire.ts";

function stockageComplet() {
  return Object.assign(new DepotMemoire(), { roleCourant: async () => "x", fermer: async () => {} });
}

function ligneEquipe(equipe: string) {
  return { team: equipe, period: "pooled_year", quarter_start: null, throughput: null, items_lt: null, items_ct: null, items_old: null, items_without_commitment: null };
}

const OPTIONS: OptionsDemarrage = {
  cheminContrat: CHEMIN_CONTRAT,
  creerAcces: () => new AccesFictif([ligneEquipe("team-a"), ligneEquipe("team-b"), ligneEquipe("team-a")]),
  creerStockage: () => stockageComplet(),
  lireMarqueur: async () => true,
  journal: false,
  avertir: () => {},
};

const aPourRoute = (routes: Array<{ method: string; url: string }>, url: string): boolean => routes.some((r) => r.url === url);

test("on the synthetic dataset with a complete storage, the sheet routes are registered", () => {
  const serveur = preparer(envMinimal(), OPTIONS);
  assert.equal(serveur.fichesEnregistrees, true);
  assert.ok(aPourRoute(serveur.routes, "/api/sheets"));
  assert.ok(aPourRoute(serveur.routes, "/api/thresholds"));
});

// Task 19.5 removes the guard "sheet routes on the synthetic dataset only" of task 18.4 (R-20261030-58, Q9, "removal by 19.5"): the test
// that fixed the guard is replaced by this one, which fixes the new rule. The reduction itself is tested in forme-reduite.test.ts.
test("on the real dataset the sheet routes and the dashboard route are registered too (the reduction is the service's, task 19.5)", async () => {
  const env = envMinimal({ MOTHRA_DATASET: "real" });
  const serveur = preparer(env, OPTIONS);
  assert.equal(serveur.fichesEnregistrees, true);
  assert.ok(aPourRoute(serveur.routes, "/api/sheets"));
  assert.ok(aPourRoute(serveur.routes, "/api/thresholds"));
  assert.ok(aPourRoute(serveur.routes, "/api/dashboards/lead_cycle"));
  const r = await serveur.app.inject({ method: "GET", url: "/api/thresholds" });
  assert.equal(r.statusCode, 200);
  await serveur.app.close();
});

// Q49 of R-20261031-19: the table of counts has no reduced form, so on real data it answers the existing 404 NOT_FOUND; on synthetic it serves.
test("/api/views/:view answers 404 NOT_FOUND on real data and serves on the synthetic dataset", async () => {
  const reel = preparer(envMinimal({ MOTHRA_DATASET: "real" }), OPTIONS);
  const r = await reel.app.inject({ method: "GET", url: "/api/views/v_team_status" });
  assert.equal(r.statusCode, 404);
  assert.deepEqual(r.json(), { error: "NOT_FOUND" });
  await reel.app.close();
  const synthetique = preparer(envMinimal(), OPTIONS);
  assert.equal((await synthetique.app.inject({ method: "GET", url: "/api/views/v_team_status" })).statusCode, 200);
  await synthetique.app.close();
});

test("a storage access that lacks the sheet methods (a start-up double) registers no sheet route", () => {
  const serveur = preparer(envMinimal(), { ...OPTIONS, creerStockage: () => ({ roleCourant: async () => "x", fermer: async () => {} }) });
  assert.equal(serveur.fichesEnregistrees, false);
});

test("collisions: two different names with one identifier are reported by identifier, never by name; the same name twice is none", () => {
  const meme = (nom: string): string => (nom.startsWith("team") ? "same-id" : nom);
  assert.deepEqual(collisionsDIdentifiants(["team-a", "team-b", "other"], meme), ["same-id"]);
  assert.deepEqual(collisionsDIdentifiants(["team-a", "team-a", "other"], meme), []);
  assert.deepEqual(collisionsDIdentifiants([], meme), []);
});

test("the team names come from the team column of the lead time view, once each", async () => {
  const noms = await nomsDEquipes(new AccesFictif([ligneEquipe("team-b"), ligneEquipe("team-a"), ligneEquipe("team-b")]), contrat, 5);
  assert.deepEqual([...noms].sort(), ["team-a", "team-b"]);
});

test("no collision: the sheet routes stay served after the start", async () => {
  const avertissements: string[] = [];
  const serveur = await demarrer(envMinimal(), { ...OPTIONS, identifiantEquipe: (nom) => `id-${nom}`, avertir: (m) => avertissements.push(m) });
  assert.equal(serveur.etat.fichesDesactivees, false);
  const r = await serveur.app.inject({ method: "GET", url: "/api/thresholds" });
  assert.equal(r.statusCode, 200);
  assert.deepEqual(avertissements.filter((m) => m === PHRASE_COLLISION_EQUIPES), []);
  await serveur.app.close();
});

test("a collision of identifiers (forced by a declared double of the hash) switches the sheet routes off, says so once, serves the rest", async () => {
  const avertissements: string[] = [];
  const serveur = await demarrer(envMinimal(), { ...OPTIONS, identifiantEquipe: () => "one-id-for-all", avertir: (m) => avertissements.push(m) });
  assert.equal(serveur.etat.fichesDesactivees, true);
  assert.deepEqual(avertissements.filter((m) => m === PHRASE_COLLISION_EQUIPES), [PHRASE_COLLISION_EQUIPES]);
  assert.ok(!PHRASE_COLLISION_EQUIPES.includes("team-a") && !PHRASE_COLLISION_EQUIPES.includes("one-id"), "the sentence names no team and no identifier");
  const fiches = await serveur.app.inject({ method: "GET", url: "/api/thresholds" });
  assert.equal(fiches.statusCode, 404);
  assert.deepEqual(fiches.json(), { error: "NOT_FOUND" });
  const vue = await serveur.app.inject({ method: "GET", url: "/api/views/v_team_status" });
  assert.equal(vue.statusCode, 200);
  await serveur.app.close();
});
