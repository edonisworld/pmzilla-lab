// R-20261031-61 (Q113, rule 2 of the testing practice): the answers of the server used by the front tests come out of the contract's
// functions, applied to synthetic rows of the views. This file checks the helper itself (reponses-contrat.ts) and the move of the "dataset,
// then reduction" gesture into the contract: the front and the server call the same `servirTableau`, there is no copy of it.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { reduitEnMode, servirTableau } from "@mothra/contract";
import type { ReponseLeadCycle } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";

import { DEBUTS, EQUIPES, MODE_REEL, MODE_SYNTHETIQUE, reponseComplete, reponseServie } from "./reponses-contrat.ts";

const RACINE = new URL("../../", import.meta.url).pathname;

test("the helper serves three generic teams, three closed quarters and a pooled-year point each, product line empty", () => {
  const reponse = reponseComplete();
  // R-20261104-36 N1 (a), task 45.1: the service layer, setting off, leaves `team` out; the identifiers stay (one per generic team).
  const ids = reponse.teams.map((t) => t.teamId);
  assert.deepEqual([...ids].sort(), EQUIPES.map((nom) => identifiantEquipe(nom)).sort());
  assert.deepEqual(ids, [...ids].sort(), "names off: the series come in the order of the identifiers (Q238)");
  assert.ok(reponse.teams.every((t) => !("team" in t)), "no team name in the series");
  assert.deepEqual(reponse.product, []);
  assert.equal(reponse.dataset, "synthetic");
  assert.equal(reponse.threshold, 5);
  assert.equal(DEBUTS.length, 3);
  for (const equipe of reponse.teams) {
    assert.deepEqual(equipe.points.map((p) => p.quarter), ["2026-Q1", "2026-Q2", "2026-Q3", "pooled_year"]);
  }
});

test("the helper holds a masked cell and an insufficient sample, produced by the masking and by tableauLeadCycle", () => {
  const equipes = reponseComplete().teams;
  const parNom = (nom: string) => {
    const serie = equipes.find((t) => t.teamId === identifiantEquipe(nom));
    assert.ok(serie !== undefined, nom);
    return serie;
  };
  const [a, b, c] = [parNom("team-a"), parNom("team-b"), parNom("team-c")];
  assert.ok(a.points.every((p) => p.lead.state === "value" && p.cycle.state === "value" && p.items.state === "value"));
  // team-b: the quarter under the floor is masked, and so is its pooled year (the series rule of the contract)
  assert.equal(b.points[0].lead.state, "masked");
  assert.equal(b.points[0].items.state, "masked");
  assert.equal(b.points[3].lead.state, "masked");
  // team-c: eight items are shown but under the reliability size: an insufficient sample, with its count shown
  assert.equal(c.points[1].lead.state, "insufficient_sample");
  assert.equal(c.points[1].cycle.state, "insufficient_sample");
  assert.deepEqual(c.points[1].items, { state: "value", value: 8 });
});

test("a masked cell of the served answer holds no value: nothing of the masked count is kept", () => {
  const masquee = reponseComplete().teams[1].points[0];
  assert.deepEqual(masquee.items, { state: "masked", threshold: 5 });
  assert.doesNotMatch(JSON.stringify(masquee), /"value"/);
});

test("on real data the contract's servirTableau gives the reduced form: dataset code, medians and states kept, no count", () => {
  assert.equal(reduitEnMode(MODE_REEL), true);
  assert.equal(reduitEnMode(MODE_SYNTHETIQUE), false);
  const complete = reponseComplete();
  const reduite = reponseServie(MODE_REEL);
  assert.equal(reduite.dataset, "real");
  assert.equal(reduite.teams.length, complete.teams.length);
  const equipes: ReadonlyArray<{ points: ReadonlyArray<{ quarter: string; lead: unknown; cycle: unknown }> }> = reduite.teams;
  equipes.forEach((equipe, i) => {
    assert.deepEqual(equipe.points.map((p) => [p.quarter, p.lead, p.cycle]), complete.teams[i].points.map((p) => [p.quarter, p.lead, p.cycle]));
    for (const point of equipe.points) assert.equal("items" in point, false);
  });
  assert.doesNotMatch(JSON.stringify(reduite), /"items"/);
});

test("the day the counts are allowed on real data, the answer is complete again, with the dataset code", () => {
  const autorise = { jeu: "real" as const, comptesAutorises: true };
  assert.equal(reduitEnMode(autorise), false);
  const complete: ReponseLeadCycle = reponseComplete();
  assert.deepEqual(reponseServie(autorise), { ...complete, dataset: "real" });
});

test("servirTableau, reduitEnMode, servirCorps and servirPanneau are defined in the contract only: the server re-exports them, no copy", () => {
  const contrat = readFileSync(`${RACINE}contract/src/reduction.ts`, "utf8");
  for (const nom of ["reduitEnMode", "servirCorps", "servirTableau", "servirPanneau"]) {
    assert.match(contrat, new RegExp(`export function ${nom}\\(`), nom);
    assert.doesNotMatch(readFileSync(`${RACINE}server/src/service.ts`, "utf8"), new RegExp(`function ${nom}\\b`), nom);
  }
  assert.equal(typeof servirTableau, "function");
});
