// Task 19.8 (R-20261031-22 Q52, R-20261031-24 Q55): the dashboard enters the cut after a collision of team identifiers, and the mode of the
// computed body and the reduced form of the sheet routes are mandatory, refusal by default (never a fall back to the complete form).
// Fake access and storage, no database; invented figures.
import assert from "node:assert/strict";
import { test } from "node:test";

import { identifiantEquipe } from "@mothra/contract/equipe";

import { demarrer, preparer } from "../src/demarrage.ts";
import type { OptionsDemarrage } from "../src/demarrage.ts";
import { creerCalculCorps } from "../src/fiches/corps.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import type { OptionsFiches } from "../src/routes/fiches.ts";
import type { OptionsTableaux } from "../src/routes/tableaux.ts";
import type { ModeDonnees } from "../src/service.ts";
import { AccesFictif, CHEMIN_CONTRAT, contrat, envMinimal } from "./aide.ts";
import { DepotMemoire, corpsSynthetique } from "./depot-memoire.ts";

const REEL: ModeDonnees = { jeu: "real", comptesAutorises: false };
const SYNTHETIQUE: ModeDonnees = { jeu: "synthetic", comptesAutorises: false };

function monterTableau(desactivees?: () => boolean) {
  const tableaux = {
    calculerTableau: async () => {
      throw new Error("the dashboard must not be computed while the routes are cut");
    },
    mode: REEL,
    ...(desactivees === undefined ? {} : { desactivees }),
  } as unknown as OptionsTableaux;
  const { app } = construireServeur({ contrat, acces: new AccesFictif([]), reglageSeuil: null, journal: false, tableaux });
  return app;
}

test("19.8 A: after a collision of team identifiers the dashboard answers the 404 of the application, an encoded path included", async () => {
  const app = monterTableau(() => true);
  for (const url of ["/api/dashboards/lead_cycle", "/api/dashboards/lead_%63ycle", "/api/%64ashboards/lead_cycle", "/api/dashboards/%6cead_cycle"]) {
    const r = await app.inject({ method: "GET", url });
    assert.equal(r.statusCode, 404, url);
    assert.deepEqual(r.json(), { error: "NOT_FOUND" }, url);
  }
  const vue = await app.inject({ method: "GET", url: "/api/views/v_team_status" });
  assert.equal(vue.statusCode, 200, "the rest of the server is served");
  await app.close();
});

test("19.8 A: the dashboard is served while the switch reads false or is absent", async () => {
  for (const desactivees of [() => false, undefined]) {
    const app = monterTableau(desactivees);
    const r = await app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
    // The computation of the double throws: reaching it (500) proves the cut did not answer.
    assert.equal(r.statusCode, 500);
    await app.close();
  }
});

const ACCES = new AccesFictif([]);
const BASE_CALCUL = { acces: ACCES, contrat, seuil: 5, depot: new DepotMemoire(), identifiantEquipe };

test("19.8 B: the computed body without a mode is refused at its creation, never served in the complete form", () => {
  assert.throws(() => creerCalculCorps(BASE_CALCUL as unknown as Parameters<typeof creerCalculCorps>[0]), /mode/);
  assert.throws(() => creerCalculCorps({ ...BASE_CALCUL, mode: undefined } as unknown as Parameters<typeof creerCalculCorps>[0]), /mode/);
  assert.doesNotThrow(() => creerCalculCorps({ ...BASE_CALCUL, mode: SYNTHETIQUE }));
});

test("19.8 B: the sheet routes without an explicit reduced value are refused at the registration, never registered with the complete schema", () => {
  const sans = { depot: new DepotMemoire(), calculerCorps: async () => corpsSynthetique(), motifsNoms: [] } as unknown as OptionsFiches;
  assert.throws(() => construireServeur({ contrat, acces: ACCES, reglageSeuil: null, journal: false, fiches: sans }), /reduite/);
  assert.throws(
    () => construireServeur({ contrat, acces: ACCES, reglageSeuil: null, journal: false, fiches: { ...sans, reduite: undefined, aujourdhui: () => "2026-11-12" } as unknown as OptionsFiches }),
    /reduite/,
  );
  for (const reduite of [true, false]) {
    assert.doesNotThrow(() => construireServeur({ contrat, acces: ACCES, reglageSeuil: null, journal: false, fiches: { ...sans, reduite, aujourdhui: () => "2026-11-12" } }));
  }
});

test("19.8 B: only the explicit value picks the form: reduite true omits the count field of a complete body, reduite false keeps it", async () => {
  for (const [reduite, attendu] of [[true, false], [false, true]] as const) {
    const depot = new DepotMemoire();
    const { app } = construireServeur({
      contrat,
      acces: ACCES,
      reglageSeuil: null,
      journal: false,
      // The body carries the count field (`coverage`) either way; the reduced shape adds its state and limit code.
      fiches: {
        depot,
        calculerCorps: async () => {
          const base = corpsSynthetique();
          return reduite ? ({ ...base, method: { ...base.method, coverageState: "coverage_sufficient", limits: [...base.method.limits, "reduced_form"] } } as typeof base) : base;
        },
        motifsNoms: [],
        reduite,
        aujourdhui: () => "2026-11-12", // A-66: the data date of the sheet (October 2026) lies in the day's quarter, whatever the real clock
      },
    });
    const id = await depot.creer({ chart: "lead_cycle_h5", scope: "team-a", dataDate: "2026-10-01", createdBy: "agile-lead-1" });
    const r = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
    assert.equal(r.statusCode, 200);
    assert.equal((r.json() as { method: Record<string, unknown> }).method.coverage !== undefined, attendu, `reduite ${String(reduite)}`);
    await app.close();
  }
});

test("19.8 B: a mode whose dataset is neither real nor synthetic, or whose constant is not a boolean, is refused", () => {
  const faux = [
    { jeu: "other", comptesAutorises: false },
    { jeu: "real", comptesAutorises: "no" },
    { jeu: "real" },
    null,
  ];
  for (const mode of faux) {
    assert.throws(() => creerCalculCorps({ ...BASE_CALCUL, mode } as unknown as Parameters<typeof creerCalculCorps>[0]), /mode/);
  }
  assert.doesNotThrow(() => creerCalculCorps({ ...BASE_CALCUL, mode: REEL }));
});

function ligneEquipe(equipe: string) {
  return { team: equipe, period: "pooled_year", quarter_start: null, throughput: null, items_lt: null, items_ct: null, items_old: null, items_without_commitment: null };
}

const OPTIONS: OptionsDemarrage = {
  cheminContrat: CHEMIN_CONTRAT,
  creerAcces: () => new AccesFictif([ligneEquipe("team-a"), ligneEquipe("team-b"), ligneEquipe("team-a")]),
  creerStockage: () => Object.assign(new DepotMemoire(), { roleCourant: async () => "x", fermer: async () => {} }),
  lireMarqueur: async () => true,
  journal: false,
  avertir: () => {},
};

test("19.8 A: at the start, a collision of identifiers cuts the dashboard route too (404 NOT_FOUND), the rest served", async () => {
  const serveur = await demarrer(envMinimal(), { ...OPTIONS, identifiantEquipe: () => "one-id-for-all" });
  assert.equal(serveur.etat.fichesDesactivees, true);
  const r = await serveur.app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(r.statusCode, 404);
  assert.deepEqual(r.json(), { error: "NOT_FOUND" });
  assert.equal((await serveur.app.inject({ method: "GET", url: "/api/views/v_team_status" })).statusCode, 200);
  await serveur.app.close();
});

test("19.8 A: the switch is read at each request: the dashboard is served, then cut once the state turns true after the preparation", async () => {
  const serveur = preparer(envMinimal(), OPTIONS);
  const avant = await serveur.app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.notEqual(avant.statusCode, 404);
  serveur.etat.fichesDesactivees = true;
  const apres = await serveur.app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  assert.equal(apres.statusCode, 404);
  assert.deepEqual(apres.json(), { error: "NOT_FOUND" });
  await serveur.app.close();
});
