// Reproductions de l'audit #629 (chasse Kraken), lot L3, au commit a98a3ffb : les cinq tests de L3-04 (seuils sans bornes), copiés à l'identique.
// Mêmes cadres que fiches.test.ts : stockage factice, aucune base. Valeurs fictives seulement.
import assert from "node:assert/strict";
import { test } from "node:test";

import { construireServeur } from "../src/routes/serveur.ts";
import { AccesFictif, contrat } from "./aide.ts";
import { DepotMemoire, corpsSynthetique } from "./depot-memoire.ts";

const AUTEUR = { "x-mothra-user": "agile-lead-1" };

function monter() {
  const depot = new DepotMemoire();
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: false,
    fiches: { depot, calculerCorps: async () => corpsSynthetique(), motifsNoms: [], reduite: false, aujourdhui: () => "2026-11-12" },
  });
  return { app, depot };
}

const SEUIL_VALIDE = { code: "h5_band", value: 0.2, setOn: "2026-10-30" };

// ---- constat 4 : seuils sans rôle ni bornes -------------------------------------------------------------------------------------------

async function ecrireSeuil(app: ReturnType<typeof monter>["app"], corps: Record<string, unknown>) {
  const r = await app.inject({ method: "POST", url: "/api/thresholds", headers: AUTEUR, payload: corps });
  return r.statusCode;
}

const refuse = (statut: number): boolean => statut >= 400 && statut < 500;

test("L3-04 : un code de seuil hors de la liste fermée est refusé", async () => {
  // audit-kraken/lots/L3.md, constat 4 : codes fermés
  const { app, depot } = monter();
  assert.ok(refuse(await ecrireSeuil(app, { ...SEUIL_VALIDE, code: "code_invente" })));
  assert.equal(depot.historique.length, 0);
  await app.close();
});

test("L3-04 : les bornes des seuils sont contrôlées (négatif, démesuré, taille d'échantillon à 0)", async () => {
  // audit-kraken/lots/L3.md, constat 4 : une taille d'échantillon minimale à 0 retire le garde-fou
  const { app, depot } = monter();
  const mauvais: Array<[string, number]> = [
    ["h5_band", -1],
    ["h5_band", 1_000_000],
    ["h5_floor", -0.5],
    ["sample_median_min_items", 0],
    ["sample_p85_min_items", 0],
  ];
  for (const [code, value] of mauvais) {
    assert.ok(refuse(await ecrireSeuil(app, { code, value, setOn: "2026-10-30" })), `${code} = ${value}`);
  }
  assert.equal(depot.historique.length, 0);
  await app.close();
});

test("L3-04 : une date de fixation dans le futur est refusée", async () => {
  // audit-kraken/lots/L3.md, constat 4 : une date future fige la valeur
  const { app, depot } = monter();
  assert.ok(refuse(await ecrireSeuil(app, { ...SEUIL_VALIDE, setOn: "2999-12-31" })));
  assert.equal(depot.historique.length, 0);
  await app.close();
});

test("L3-04 : un couple de seuils bas >= haut est refusé à l'écriture", async () => {
  // audit-kraken/lots/L3.md, constat 4 : le couple incohérent rend ensuite un 500 sur toutes les fiches du graphique
  const { app, depot } = monter();
  assert.equal(await ecrireSeuil(app, { code: "h1_lower", value: 1.5, setOn: "2026-10-30" }), 200);
  assert.equal(await ecrireSeuil(app, { code: "h1_upper", value: 3, setOn: "2026-10-30" }), 200);
  for (const incoherent of [3, 5]) {
    assert.ok(refuse(await ecrireSeuil(app, { code: "h1_lower", value: incoherent, setOn: "2026-10-31" })), `h1_lower = ${incoherent}`);
  }
  assert.equal(depot.historique.length, 2);
  await app.close();
});

test("L3-04 : avec un historique déjà incohérent, l'écriture d'un autre code passe ; celle d'un code du couple est refusée", async () => {
  // Revue Opus du groupe S2, point b : le refus ne vise que le couple qui touche le code écrit.
  const { app, depot } = monter();
  depot.historique.push({ code: "h1_lower", value: 5, setOn: "2026-10-01", setBy: "agile-lead-1" }, { code: "h1_upper", value: 2, setOn: "2026-10-01", setBy: "agile-lead-1" });
  assert.equal(await ecrireSeuil(app, SEUIL_VALIDE), 200);
  assert.equal(depot.historique.length, 3);
  assert.ok(refuse(await ecrireSeuil(app, { code: "h1_upper", value: 2.5, setOn: "2026-10-30" })));
  assert.equal(depot.historique.length, 3);
  await app.close();
});

test("R-20261107-29 décision 5 : une valeur non numérique est refusée en 400, sans conversion de type (null, \"5\", true, [\"5\"])", async () => {
  const { app, depot } = monter();
  for (const value of [null, "5", true, ["5"], "0.2", [], {}]) {
    assert.equal(await ecrireSeuil(app, { code: "h5_band", value, setOn: "2026-10-30" }), 400, JSON.stringify(value));
  }
  assert.equal(depot.historique.length, 0);
  assert.equal(await ecrireSeuil(app, SEUIL_VALIDE), 200, "un nombre reste accepté");
  assert.equal(depot.historique.length, 1);
  await app.close();
});

test("R-20261107-29 décision 7 : les couples H5 (bande <= double bande, plancher bas <= plancher) sont contrôlés à l'écriture", async () => {
  const { app, depot } = monter();
  assert.equal(await ecrireSeuil(app, { code: "h5_double_band", value: 0.4, setOn: "2026-10-30" }), 200);
  assert.equal(await ecrireSeuil(app, { code: "h5_band", value: 0.2, setOn: "2026-10-30" }), 200);
  assert.equal(await ecrireSeuil(app, { code: "h5_band", value: 0.5, setOn: "2026-10-31" }), 400, "bande au-dessus de la double bande");
  assert.equal(await ecrireSeuil(app, { code: "h5_double_band", value: 0.1, setOn: "2026-10-31" }), 400, "double bande sous la bande");
  assert.equal(await ecrireSeuil(app, { code: "h5_band", value: 0.4, setOn: "2026-10-31" }), 200, "l'égalité est permise");
  assert.equal(await ecrireSeuil(app, { code: "h5_floor", value: 0.8, setOn: "2026-10-30" }), 200);
  assert.equal(await ecrireSeuil(app, { code: "h5_low_floor", value: 0.6, setOn: "2026-10-30" }), 200);
  assert.equal(await ecrireSeuil(app, { code: "h5_low_floor", value: 0.9, setOn: "2026-10-31" }), 400, "plancher bas au-dessus du plancher");
  assert.equal(await ecrireSeuil(app, { code: "h5_floor", value: 0.5, setOn: "2026-10-31" }), 400, "plancher sous le plancher bas");
  assert.equal(await ecrireSeuil(app, { code: "h5_low_floor", value: 0.8, setOn: "2026-10-31" }), 200, "l'égalité est permise");
  assert.equal(depot.historique.length, 6);
  await app.close();
});

test("R-20261107-29 décision 7 : avec un couple H5 déjà incohérent, l'écriture d'un autre code passe ; celle d'un code du couple est refusée", async () => {
  const { app, depot } = monter();
  depot.historique.push({ code: "h5_band", value: 0.9, setOn: "2026-10-01", setBy: "agile-lead-1" }, { code: "h5_double_band", value: 0.4, setOn: "2026-10-01", setBy: "agile-lead-1" });
  assert.equal(await ecrireSeuil(app, { code: "h5_run_rises", value: 2, setOn: "2026-10-30" }), 200);
  assert.equal(depot.historique.length, 3);
  assert.equal(await ecrireSeuil(app, { code: "h5_double_band", value: 0.45, setOn: "2026-10-30" }), 400);
  assert.equal(depot.historique.length, 3);
  await app.close();
});

test("L3-04 : la date du jour est injectable (options.aujourdhui) : la borne future suit la date fixée", async () => {
  // Revue Opus du groupe S2, point d : la date fixée par le test, le défaut UTC inchangé.
  const depot = new DepotMemoire();
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: false,
    fiches: { depot, calculerCorps: async () => corpsSynthetique(), motifsNoms: [], reduite: false, aujourdhui: () => "2026-11-01" },
  });
  assert.equal(await ecrireSeuil(app, { ...SEUIL_VALIDE, setOn: "2026-11-01" }), 200);
  assert.ok(refuse(await ecrireSeuil(app, { ...SEUIL_VALIDE, setOn: "2026-11-02" })));
  assert.equal(depot.historique.length, 1);
  await app.close();
});
