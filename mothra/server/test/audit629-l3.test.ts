// Reproductions de l'audit #629 (chasse Kraken), lot L3, constats L3-01 à L3-03 (A-60, A-61, A-62), reprises de la branche de chasse.
// Mêmes cadres que fiches.test.ts et demarrage.test.ts : stockage factice, aucune base. Valeurs fictives seulement.
// Les reproductions de L3-04 (seuils sans bornes, A-63) appartiennent à un autre groupe du tri et ne sont pas reprises ici.
import assert from "node:assert/strict";
import { linkSync, mkdtempSync, readFileSync, rmSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { SchemaReponseSeuils } from "@mothra/contract";

import { demarrer, preparer } from "../src/demarrage.ts";
import type { OptionsDemarrage, Serveur } from "../src/demarrage.ts";
import { RefusDemarrage } from "../src/refus.ts";
import { construireServeur, hoteAccepte } from "../src/routes/serveur.ts";
import { AccesFictif, CHEMIN_CONTRAT, LISTE_EQUIPES_FICTIVE, LISTE_SENSIBLE_FICTIVE, contrat, envMinimal } from "./aide.ts";
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

// ---- constat 1 : l'en-tête Host n'est pas contrôlé ----------------------------------------------------------------------------------

test("L3-01 : un en-tête Host étranger est refusé en lecture (rebinding DNS)", async () => {
  // audit-kraken/lots/L3.md, constat 1
  const { app } = monter();
  const r = await app.inject({ method: "GET", url: "/api/thresholds", headers: { host: "evil.example:3000" } });
  assert.ok(r.statusCode >= 400 && r.statusCode < 500, `statut ${r.statusCode}`);
  await app.close();
});

test("L3-01 : une écriture venue d'une autre origine est refusée, et rien n'est stocké", async () => {
  // audit-kraken/lots/L3.md, constat 1 : Origin et Sec-Fetch-Site contrôlés sur les écritures
  const { app, depot } = monter();
  const r = await app.inject({
    method: "POST",
    url: "/api/thresholds",
    headers: { ...AUTEUR, host: "localhost:3000", origin: "http://evil.example:3000", "sec-fetch-site": "cross-site" },
    payload: SEUIL_VALIDE,
  });
  assert.ok(r.statusCode >= 400 && r.statusCode < 500, `statut ${r.statusCode}`);
  assert.equal(depot.historique.length, 0);
  await app.close();
});

// ---- constat 2 : en session, rien n'impose le jeu synthétique -------------------------------------------------------------------------

test("L3-02 : en session, un jeu de données autre que synthétique est refusé au démarrage (sortie 4)", async () => {
  // audit-kraken/lots/L3.md, constat 2 : MOTHRA_DATASET=real, port jetable valide, base sans marqueur
  const env = envMinimal({ CLAUDECODE: "1", DBTEST_PORT: "55432", PMZILLA_LAB_DB_PORT: "55432", MOTHRA_DATASET: "real" });
  const options: OptionsDemarrage = {
    cheminContrat: CHEMIN_CONTRAT,
    creerAcces: () => new AccesFictif(),
    creerStockage: () => ({ roleCourant: async () => "x", fermer: async () => {} }),
    lireMarqueur: async () => false,
    journal: false,
    avertir: () => {},
  };
  let serveur: Serveur | null = null;
  let refus: unknown = null;
  try {
    serveur = await demarrer(env, options);
  } catch (erreur) {
    refus = erreur;
  }
  await serveur?.app.close();
  assert.ok(refus instanceof RefusDemarrage, "un refus de démarrage était attendu");
  assert.equal(refus.sortie, 4);
});

// ---- constat 3 : le chemin de la liste de noms est libre en session ------------------------------------------------------------------

function essai(env: Record<string, string | undefined>, options: Partial<OptionsDemarrage> = {}): RefusDemarrage | null {
  try {
    preparer(env, { cheminContrat: CHEMIN_CONTRAT, creerAcces: () => new AccesFictif(), journal: false, avertir: () => {}, ...options });
  } catch (erreur) {
    assert.ok(erreur instanceof RefusDemarrage, "un refus de démarrage était attendu");
    return erreur;
  }
  return null;
}

test("L3-03 : en session, un chemin de liste de noms hors de test/listes/ est refusé", () => {
  // audit-kraken/lots/L3.md, constat 3 : la liste fermée ne doit pas pouvoir être remplacée par une liste de sondage
  const session = { CLAUDECODE: "1", DBTEST_PORT: "55432", PMZILLA_LAB_DB_PORT: "55432" };
  const lireListe = (chemin: string): string => (chemin === LISTE_EQUIPES_FICTIVE ? readFileSync(chemin, "utf8") : "Nom Fictif\n");
  assert.equal(essai(envMinimal(session), { lireListe }), null, "précondition : les listes fictives du dossier test/listes/ sont acceptées");
  const refus = essai(envMinimal({ ...session, MOTHRA_SENSITIVE_NAMES_FILE: "/dossier/ailleurs/noms.txt" }), { lireListe });
  assert.notEqual(refus, null, "un chemin hors de test/listes/ doit être refusé en session");
});

test("A-94 (R-20261107-27, décision 5) : en session, un chemin de l'extrait des équipes hors de test/listes/ est refusé", () => {
  const session = { CLAUDECODE: "1", DBTEST_PORT: "55432", PMZILLA_LAB_DB_PORT: "55432" };
  const lireListe = (chemin: string): string => (chemin === LISTE_EQUIPES_FICTIVE ? readFileSync(chemin, "utf8") : "Nom Fictif\n");
  assert.equal(essai(envMinimal(session), { lireListe }), null, "précondition : les listes fictives sont acceptées");
  const refus = essai(envMinimal({ ...session, MOTHRA_TEAM_NAMES_FILE: "/dossier/ailleurs/equipes.yaml" }), { lireListe });
  assert.ok(refus !== null && refus.variable === "MOTHRA_TEAM_NAMES_FILE", "un chemin hors de test/listes/ doit être refusé, la variable nommée seule");
});

test("A-94 (R-20261107-27, décision 3 a) : le schéma de réponse des seuils ne contient pas setBy", () => {
  const propriete = (SchemaReponseSeuils.properties.thresholds.items as { properties: Record<string, unknown> }).properties;
  assert.deepEqual(Object.keys(propriete).sort(), ["code", "setOn", "value"]);
  assert.ok(!("setBy" in propriete));
});

// ---- test de classe (décision de l'auteur) : toute route enregistrée refuse un Host étranger -----------------------------------------

const OPTIONS_COMPLETES: OptionsDemarrage = {
  cheminContrat: CHEMIN_CONTRAT,
  creerAcces: () => new AccesFictif([]),
  creerStockage: () => Object.assign(new DepotMemoire(), { roleCourant: async () => "x", fermer: async () => {} }),
  journal: false,
  avertir: () => {},
};

test("L3-01 (classe) : chaque route enregistrée, bundle et fichiers statiques compris, refuse un Host étranger", async () => {
  // The server log is captured: each injection must leave exactly one "request refused" line, which tells the refusal of the hook from a
  // 404 of the route itself (both answer 404 NOT_FOUND).
  const lignes: string[] = [];
  const serveur = preparer(envMinimal(), {
    ...OPTIONS_COMPLETES,
    journal: { level: "error", stream: { write: (m: string) => { lignes.push(m); } } },
  });
  const urls = serveur.routes.map((r) => `${r.method} ${r.url}`);
  // Le test doit voir toutes les familles : l'API de vues, les fiches, les seuils, le tableau, les panneaux, le bundle et ses fichiers.
  for (const attendue of ["GET /api/views/:view", "POST /api/sheets", "GET /api/thresholds", "POST /api/thresholds", "GET /", "GET /*"]) {
    assert.ok(urls.includes(attendue), `route attendue absente de la liste : ${attendue}`);
  }
  assert.ok(urls.some((u) => u.includes("/api/dashboards/")), "route du tableau absente de la liste");
  assert.ok(urls.some((u) => u.includes("/api/panels/")), "route des panneaux absente de la liste");
  for (const route of serveur.routes) {
    const url = route.url.replace(/:[A-Za-z]+/g, "x").replace("*", "fichier.js");
    for (const methode of route.method.split(",")) {
      const avant = lignes.length;
      const r = await serveur.app.inject({ method: methode as "GET", url, headers: { host: "evil.example:3000" } });
      assert.equal(r.statusCode, 404, `${methode} ${route.url} doit refuser un Host étranger (statut ${r.statusCode})`);
      assert.deepEqual(r.json(), { error: "NOT_FOUND" }, `${methode} ${route.url}`);
      assert.equal(lignes.length - avant, 1, `${methode} ${route.url} : une ligne "request refused" attendue`);
      assert.match(lignes.at(-1) ?? "", /request refused/, `${methode} ${route.url}`);
    }
  }
  // Un fichier statique et la page d'accueil, avec un Host étranger, en plus des motifs de route.
  for (const url of ["/", "/index.html", "/assets/app.js", "/sheets/12"]) {
    const avant = lignes.length;
    const r = await serveur.app.inject({ method: "GET", url, headers: { host: "evil.example" } });
    assert.equal(r.statusCode, 404, url);
    assert.equal(lignes.length - avant, 1, `${url} : une ligne "request refused" attendue`);
    assert.match(lignes.at(-1) ?? "", /request refused/, url);
  }
  // Les deux noms de la boucle locale ne sont pas refusés (précondition du test : le refus vient bien du Host).
  for (const hote of ["127.0.0.1:3000", "localhost:3000"]) {
    const r = await serveur.app.inject({ method: "GET", url: "/api/thresholds", headers: { host: hote } });
    assert.equal(r.statusCode, 200, hote);
  }
  await serveur.app.close();
});

test("L3-01 : hoteAccepte refuse les formes limites et accepte les deux noms de la boucle locale", () => {
  for (const refuse of [undefined, "[::1]:3000", "localhost.:3000", "localhost:", "localhost:3000@evil"]) {
    assert.equal(hoteAccepte(refuse), false, String(refuse));
  }
  assert.equal(hoteAccepte("localhost:3000", 4000), false, "port attendu 4000");
  for (const accepte of ["LOCALHOST:3000", "127.0.0.1"]) {
    assert.equal(hoteAccepte(accepte), true, accepte);
  }
});

// Le refus d'un fichier de test/listes/ à plusieurs liens physiques n'a pas de test ici : un lien temporaire vers le fichier fictif partagé
// rendrait intermittents les autres tests qui le lisent en parallèle (node --test). Le contrôle est relu par la revue Opus du groupe.

test("L3-01 : une écriture de même origine passe, une écriture sans en-tête d'origine passe, un Sec-Fetch-Site étranger est refusé", async () => {
  const { app, depot } = monter();
  const meme = await app.inject({
    method: "POST",
    url: "/api/thresholds",
    headers: { ...AUTEUR, host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000", "sec-fetch-site": "same-origin" },
    payload: SEUIL_VALIDE,
  });
  assert.equal(meme.statusCode, 200);
  const sans = await app.inject({ method: "POST", url: "/api/thresholds", headers: { ...AUTEUR, host: "127.0.0.1:3000" }, payload: { ...SEUIL_VALIDE, value: 0.3, setOn: "2026-10-31" } });
  assert.equal(sans.statusCode, 200);
  const site = await app.inject({
    method: "POST",
    url: "/api/thresholds",
    headers: { ...AUTEUR, host: "127.0.0.1:3000", "sec-fetch-site": "same-site" },
    payload: { ...SEUIL_VALIDE, value: 0.4, setOn: "2026-11-01" },
  });
  assert.equal(site.statusCode, 404);
  assert.equal(depot.historique.length, 2);
  await app.close();
});
