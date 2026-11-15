// A-68 (audit #629, H-04 and L3-11): the collision check of team identifiers covers every served view that has a team column, not only
// the lead time view; a collision found in `v_team_flow_inout` switches the sheet, table and panel routes off (404 NOT_FOUND), it never
// reaches the panel builder, which would raise and answer 500. Synthetic team names; the hash is replaced by a declared double that forces
// the collision. No database.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { Vue } from "@mothra/contract";

import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { demarrer } from "../src/demarrage.ts";
import type { OptionsDemarrage } from "../src/demarrage.ts";
import { PHRASE_COLLISION_EQUIPES, nomsDEquipes } from "../src/fiches/equipes.ts";
import { CHEMIN_CONTRAT, contrat, envMinimal } from "./aide.ts";
import { DepotMemoire } from "./depot-memoire.ts";

// Declared double of the hash: the two teams of the flow view give one identifier, the lead time view holds one team only.
const IDENTIFIANT_COMMUN = "same-id";
const doubleDuHachage = (nom: string): string => (nom.startsWith("team-") ? IDENTIFIANT_COMMUN : nom);

function ligneFlux(equipe: string, debut: string, groupe: "story" | "defect"): LigneBase {
  return { team: equipe, quarter_start: debut, type_group: groupe, created: 50, done: 40 };
}

// Rows by view: a collision only in v_team_flow_inout (the lead time view has one team).
class AccesParVue implements AccesVues {
  appels: string[] = [];
  flux: LigneBase[];
  constructor(flux: LigneBase[]) {
    this.flux = flux;
  }
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    this.appels.push(vue.name);
    if (vue.name === "v_team_flow_inout") return this.flux;
    if (vue.name === "v_team_lead_time_throughput") {
      return [{ team: "team-a", period: "pooled_year", quarter_start: null, throughput: null, items_lt: null, items_ct: null, items_old: null, items_without_commitment: null }];
    }
    return [];
  }
}

const FLUX_EN_COLLISION = [ligneFlux("team-a", "2026-01-01", "story"), ligneFlux("team-b", "2026-01-01", "story")];
const FLUX_SANS_COLLISION = [ligneFlux("team-a", "2026-01-01", "story"), ligneFlux("other", "2026-01-01", "story")];

function options(acces: AccesVues, avertissements: string[]): OptionsDemarrage {
  return {
    cheminContrat: CHEMIN_CONTRAT,
    creerAcces: () => acces,
    creerStockage: () => Object.assign(new DepotMemoire(), { roleCourant: async () => "x", fermer: async () => {} }),
    lireMarqueur: async () => true,
    journal: false,
    avertir: (m) => avertissements.push(m),
    identifiantEquipe: doubleDuHachage,
    aujourdhui: () => "2026-11-19",
  };
}

test("L3-11 : une collision visible dans v_team_flow_inout seulement coupe les routes des fiches, une fois, sans nom", async () => {
  const avertissements: string[] = [];
  const serveur = await demarrer(envMinimal(), options(new AccesParVue(FLUX_EN_COLLISION), avertissements));
  assert.equal(serveur.etat.fichesDesactivees, true);
  assert.deepEqual(avertissements.filter((m) => m === PHRASE_COLLISION_EQUIPES), [PHRASE_COLLISION_EQUIPES]);
  await serveur.app.close();
});

test("H-04 : après cette collision, la route d'un panneau d'équipe répond 404 NOT_FOUND, jamais 500", async () => {
  const serveur = await demarrer(envMinimal(), options(new AccesParVue(FLUX_EN_COLLISION), []));
  const r = await serveur.app.inject({ method: "GET", url: `/api/panels/stories-inout?team=${IDENTIFIANT_COMMUN}&from=2026-Q1&to=2026-Q3` });
  assert.notEqual(r.statusCode, 500);
  assert.equal(r.statusCode, 404);
  assert.deepEqual(r.json(), { error: "NOT_FOUND" });
  await serveur.app.close();
});

test("A-68 : sans collision, les routes restent servies et aucun avertissement n'est émis", async () => {
  const avertissements: string[] = [];
  const serveur = await demarrer(envMinimal(), options(new AccesParVue(FLUX_SANS_COLLISION), avertissements));
  assert.equal(serveur.etat.fichesDesactivees, false);
  assert.deepEqual(avertissements.filter((m) => m === PHRASE_COLLISION_EQUIPES), []);
  await serveur.app.close();
});

test("A-68 : le contrôle lit chaque vue du contrat qui a une colonne team (liste tirée du contrat, non recopiée)", async () => {
  const attendues = contrat.views.filter((v) => v.plainColumns.includes("team")).map((v) => v.name).sort();
  assert.ok(attendues.includes("v_team_flow_inout") && attendues.length > 1, "the contract has several by-team views");
  const acces = new AccesParVue(FLUX_SANS_COLLISION);
  const noms = await nomsDEquipes(acces, contrat, 5);
  // The lead time view also reads its weekly companion (service layer): the test asks only that every by-team view was read.
  for (const nom of attendues) {
    assert.ok(acces.appels.includes(nom), `the by-team view ${nom} is read by the check`);
  }
  assert.deepEqual([...noms].sort(), ["other", "team-a"]);
});

test("A-68 : une collision apparue après le démarrage (contrôle passé) : la route du panneau répond 404 NOT_FOUND, jamais 500", async () => {
  const acces = new AccesParVue(FLUX_SANS_COLLISION);
  const serveur = await demarrer(envMinimal(), options(acces, []));
  assert.equal(serveur.etat.fichesDesactivees, false);
  acces.flux = FLUX_EN_COLLISION;
  const r = await serveur.app.inject({ method: "GET", url: `/api/panels/stories-inout?team=${IDENTIFIANT_COMMUN}&from=2026-Q1&to=2026-Q3` });
  assert.notEqual(r.statusCode, 500);
  assert.equal(r.statusCode, 404);
  assert.deepEqual(r.json(), { error: "NOT_FOUND" });
  await serveur.app.close();
});

test("A-68 : les libellés (produit) et (sans équipe) ne sont pas des équipes du contrôle", async () => {
  const flux = [...FLUX_SANS_COLLISION, ligneFlux("(produit)", "2026-01-01", "story"), ligneFlux("(sans équipe)", "2026-01-01", "story")];
  const noms = await nomsDEquipes(new AccesParVue(flux), contrat, 5);
  assert.deepEqual([...noms].sort(), ["other", "team-a"]);
});
