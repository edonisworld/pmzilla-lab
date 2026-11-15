// Audit #629, A-04: the way from a draft to its publication exists in the interface. A reviewer finds the drafts (a list by state), opens the
// life cycle screen of a sheet (the `Fiche` component, mounted on `#/fiche/<id>`), reviews it, and its author publishes it; the whole way is
// made of links and buttons, reachable by the keyboard. The server is a fake `fetch` with the rules of the sheet routes (author, reviewer, state);
// every sheet answer comes from `corpsDepuisVues` of the contract (test/fiches-h5.ts). No network, no database, no real data.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";

import { tableauLeadCycle, servirTableau } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import { Application, ecranDuHash } from "../src/Application.ts";
import { adresseConviction, adresseFiche, ficheDuHash, ADRESSE_FICHES } from "../src/api/adresse.ts";
import { ETATS_EN_COURS, optionsListeFiches } from "../src/api/cycleFiche.ts";
import type { SourceCycleFiche } from "../src/api/cycleFiche.ts";
import type { EtatFiche, ReponseFiche } from "../src/api/fiche.ts";
import { optionsFiche } from "../src/api/ficheLecture.ts";
import { creerFicheHttp, EN_TETE_UTILISATEUR, lireFicheHttp, listerFichesHttp, publierFicheHttp, relireFicheHttp, sourceCycleFicheHttp } from "../src/api/http.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import { ErreurApi } from "../src/api/vue.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { NavigationLaterale } from "../src/composants/NavigationLaterale.ts";
import { CLES_CONVICTION } from "../src/convictions.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { PageFiche } from "../src/pages/PageFiche.ts";
import { PageFiches } from "../src/pages/PageFiches.ts";
import { ficheH1, EQUIPE_SYNTHETIQUE, IDENTIFIANT_OPAQUE } from "./fiches-h1.ts";
import { ficheH5 } from "./fiches-h5.ts";
import { rendre, texte } from "./rendu.ts";
import { sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

function nouveauClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
}

// ---- a fake server with the rules of the sheet routes -----------------------------------------------------------------------------

interface FicheDuServeur {
  id: string;
  chart: "lead_cycle_h5" | "lead_cycle_h1";
  scope: string;
  dataDate: string;
  state: EtatFiche;
  createdBy: string;
}

const json = (corps: unknown, statut = 200): Response => new Response(JSON.stringify(corps), { status: statut, headers: { "content-type": "application/json" } });

class ServeurFictif {
  fiches = new Map<string, FicheDuServeur>();
  appels: Array<{ methode: string; url: string; utilisateur: string | undefined; typeContenu: string | undefined }> = [];

  ajouter(fiche: Partial<FicheDuServeur> & { id: string }): void {
    this.fiches.set(fiche.id, {
      chart: "lead_cycle_h5",
      scope: scopeFiche({ kind: "team", team: IDENTIFIANT_OPAQUE }),
      dataDate: "2026-10-05",
      state: "draft",
      createdBy: "agile-lead-1",
      ...fiche,
    });
  }

  corps(f: FicheDuServeur): ReponseFiche {
    const base = f.chart === "lead_cycle_h5" ? ficheH5("refuted", { etat: f.state }) : ficheH1("not_settled", { etat: f.state });
    return { ...base, id: f.id } as ReponseFiche;
  }

  fetch: typeof fetch = async (entree, options = {}) => {
    const url = String(entree);
    const entetes = (options.headers ?? {}) as Record<string, string>;
    const methode = options.method ?? "GET";
    this.appels.push({ methode, url, utilisateur: entetes[EN_TETE_UTILISATEUR], typeContenu: entetes["content-type"] });
    if (methode === "POST" && url === "/api/sheets") {
      const utilisateurCreation = entetes[EN_TETE_UTILISATEUR];
      if (utilisateurCreation === undefined) return json({ error: "INVALID_REQUEST" }, 400);
      const demande = JSON.parse(String(options.body)) as { chart: FicheDuServeur["chart"]; scope: string; dataDate: string };
      const id = String(this.fiches.size + 1);
      this.ajouter({ id, chart: demande.chart, scope: demande.scope, dataDate: demande.dataDate, createdBy: utilisateurCreation });
      return json({ id, state: "draft" });
    }
    const liste = /^\/api\/sheets\?state=(draft|reviewed|published)$/.exec(url);
    if (methode === "GET" && liste !== null) {
      const sheets = [...this.fiches.values()]
        .filter((f) => f.state === liste[1])
        .sort((a, b) => Number(b.id) - Number(a.id))
        .map((f) => ({ id: f.id, chart: f.chart, scope: f.scope, dataDate: f.dataDate, state: f.state }));
      return json({ sheets });
    }
    if (methode === "GET" && /^\/api\/sheets\?/.test(url)) return json({ error: "INVALID_REQUEST" }, 400);
    const une = /^\/api\/sheets\/([0-9]+)(\/review|\/publish)?$/.exec(url);
    const fiche = une === null ? undefined : this.fiches.get(une[1]);
    if (une === null) return json({ error: "NOT_FOUND" }, 404);
    if (fiche === undefined) return json({ error: "UNKNOWN_SHEET" }, 404);
    if (methode === "GET") return json(this.corps(fiche));
    const utilisateur = entetes[EN_TETE_UTILISATEUR];
    if (utilisateur === undefined) return json({ error: "INVALID_REQUEST" }, 400);
    if (fiche.state === "published") return json({ error: "VERSION_FROZEN" }, 409);
    if (une[2] === "/review") {
      if (fiche.state !== "draft") return json({ error: "NOT_DRAFT" }, 409);
      if (fiche.createdBy === utilisateur) return json({ error: "SELF_REVIEW_REFUSED" }, 403);
      fiche.state = "reviewed";
      return json(this.corps(fiche));
    }
    if (fiche.createdBy !== utilisateur) return json({ error: "NOT_AUTHOR" }, 403);
    if (fiche.state !== "reviewed") return json({ error: "NOT_REVIEWED" }, 409);
    fiche.state = "published";
    return json(this.corps(fiche));
  };
}

function source(serveur: ServeurFictif, utilisateur: string | undefined): SourceCycleFiche {
  return sourceCycleFicheHttp(() => utilisateur, serveur.fetch);
}

// The page of the list, its two queries being in the cache (what the server answered).
async function pageFiches(cycle: SourceCycleFiche, langue: Langue = "en"): Promise<string> {
  const client = nouveauClient();
  for (const etat of ETATS_EN_COURS) await client.prefetchQuery(optionsListeFiches(cycle.lister, etat));
  return propre(rendre(h(QueryClientProvider, { client }, h(PageFiches, { cycle })), langue));
}

// The life cycle screen of a sheet, its answer being in the cache.
async function pageFiche(serveur: ServeurFictif, cycle: SourceCycleFiche, id: string, langue: Langue = "en"): Promise<string> {
  const client = nouveauClient();
  const lire = (identifiant: string) => lireFicheHttp(identifiant, serveur.fetch);
  await client.prefetchQuery(optionsFiche(lire, id));
  return propre(rendre(h(QueryClientProvider, { client }, h(PageFiche, { id, lire, cycle })), langue));
}

// ---- the addresses ----------------------------------------------------------------------------------------------------------------

test("the address of a sheet is #/fiche/<id> and the list is #/fiches; anything else is neither", () => {
  assert.equal(ADRESSE_FICHES, "#/fiches");
  assert.equal(adresseFiche("12"), "#/fiche/12");
  assert.equal(ficheDuHash("#/fiche/12"), "12");
  assert.equal(ficheDuHash("#/fiche/12?x=1"), "12");
  for (const mauvaise of ["#/fiche/", "#/fiche", "#/fiches", "#/fiche/a/b", "#/fiche/../x", "#/fiche/%2e%2e", "#/fiche/a b", "#/conviction/lead_cycle_h1/12", "#/fiche/" + "a".repeat(65)]) {
    assert.equal(ficheDuHash(mauvaise), undefined, mauvaise);
  }
  assert.equal(ecranDuHash("#/fiches"), "fiches");
  assert.equal(ecranDuHash("#/fiche/12"), "fiche");
  assert.equal(ecranDuHash("#/fiche/../x"), "squelette");
  assert.equal(ecranDuHash("#/tableau"), "tableau");
  assert.equal(ecranDuHash("#/conviction/lead_cycle_h1"), "conviction");
});

// ---- the client of the routes ------------------------------------------------------------------------------------------------------

test("the list is read by state, GET /api/sheets?state=…, and a sheet of a kind the front does not know is left out", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1" });
  serveur.ajouter({ id: "2", chart: "lead_cycle_h1" });
  const liste = await listerFichesHttp("draft", serveur.fetch);
  assert.deepEqual(liste.map((f) => f.id), ["2", "1"]);
  assert.deepEqual(serveur.appels.map((a) => `${a.methode} ${a.url}`), ["GET /api/sheets?state=draft"]);
  const inconnue: typeof fetch = async () => json({ sheets: [{ id: "3", chart: "a_chart_from_the_future", scope: "team.a", dataDate: "2026-10-05", state: "draft" }, { id: "4", chart: "lead_cycle_h5", scope: "team.a", dataDate: "2026-10-05", state: "draft" }] });
  assert.deepEqual((await listerFichesHttp("draft", inconnue)).map((f) => f.id), ["4"]);
});

test("a refused or malformed list is a code of the catalogue, never the body", async () => {
  const refus: typeof fetch = async () => json({ error: "DATABASE_UNAVAILABLE" }, 503);
  await assert.rejects(listerFichesHttp("draft", refus), (e: unknown) => e instanceof ErreurApi && e.code === "DATABASE_UNAVAILABLE");
  const informe: typeof fetch = async () => json({ rows: [] });
  await assert.rejects(listerFichesHttp("draft", informe), (e: unknown) => e instanceof ErreurApi && e.code === "INTERNAL");
  const panne: typeof fetch = async () => {
    throw new Error("network");
  };
  await assert.rejects(listerFichesHttp("reviewed", panne), (e: unknown) => e instanceof ErreurApi && e.code === "INTERNAL");
});

test("a review and a publication are POSTs to the route of the sheet with the caller's identifier, and send no content type (the body is empty)", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1" });
  assert.deepEqual(await relireFicheHttp("1", () => "agile-lead-2", serveur.fetch), { ok: true });
  assert.deepEqual(await publierFicheHttp("1", () => "agile-lead-1", serveur.fetch), { ok: true });
  assert.deepEqual(serveur.appels.map((a) => `${a.methode} ${a.url} ${String(a.utilisateur)}`), ["POST /api/sheets/1/review agile-lead-2", "POST /api/sheets/1/publish agile-lead-1"]);
  assert.ok(serveur.appels.every((a) => a.typeContenu === undefined), "an empty body with a JSON content type is refused by the framework");
});

test("a refusal of the review or of the publication is its code: self review, not the author, not reviewed, unknown user, no identifier", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1" });
  assert.deepEqual(await relireFicheHttp("1", () => "agile-lead-1", serveur.fetch), { ok: false, code: "SELF_REVIEW_REFUSED" });
  assert.deepEqual(await publierFicheHttp("1", () => "agile-lead-1", serveur.fetch), { ok: false, code: "NOT_REVIEWED" });
  assert.deepEqual(await relireFicheHttp("1", () => undefined, serveur.fetch), { ok: false, code: "INVALID_REQUEST" });
  assert.equal(serveur.appels[2].utilisateur, undefined, "no identifier, no header");
  assert.deepEqual(await relireFicheHttp("99", () => "agile-lead-2", serveur.fetch), { ok: false, code: "UNKNOWN_SHEET" });
  const panne: typeof fetch = async () => {
    throw new Error("network");
  };
  assert.deepEqual(await publierFicheHttp("1", () => "agile-lead-1", panne), { ok: false, code: "INTERNAL" });
  const etrange: typeof fetch = async () => json({ error: "A_CODE_FROM_THE_FUTURE" }, 418);
  assert.deepEqual(await relireFicheHttp("1", () => "agile-lead-2", etrange), { ok: false, code: "INTERNAL" });
});

// ---- the list ---------------------------------------------------------------------------------------------------------------------

test("the list shows the drafts to review and the reviewed sheets to publish, each a link to its screen, with its kind, its team and its date", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1", state: "draft" });
  serveur.ajouter({ id: "2", state: "reviewed", chart: "lead_cycle_h1" });
  serveur.ajouter({ id: "3", state: "published" });
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const html = await pageFiches(source(serveur, "agile-lead-2"), langue);
    assert.match(html, /<section class="page" aria-labelledby="page-titre"><h2 id="page-titre">/, langue);
    assert.ok(texte(html).includes(c["fiche.list.title"]) && texte(html).includes(c["fiche.list.section.draft"]) && texte(html).includes(c["fiche.list.section.reviewed"]), langue);
    const lien = (id: string): string => new RegExp(`<a class="lien" href="#/fiche/${id}">([^<]*)</a>`).exec(html)?.[1] ?? "";
    assert.ok(lien("1").includes(c[CLES_CONVICTION.lead_cycle_h5.nav as keyof typeof en]), `kind ${langue}`);
    assert.ok(lien("1").includes(IDENTIFIANT_OPAQUE), `team ${langue}`);
    assert.ok(lien("2").includes(c[CLES_CONVICTION.lead_cycle_h1.nav as keyof typeof en]), `kind h1 ${langue}`);
    assert.notEqual(lien("1"), "");
    assert.doesNotMatch(html, /href="#\/fiche\/3"/, "a published sheet is not in progress");
    assert.doesNotMatch(html, new RegExp(EQUIPE_SYNTHETIQUE, "i"), "the opaque identifier, never the name");
    // The draft is in the first section, the reviewed one in the second.
    const brouillons = /data-etat-liste="draft"[\s\S]*?<\/section>/.exec(html)?.[0] ?? "";
    const relues = /data-etat-liste="reviewed"[\s\S]*?<\/section>/.exec(html)?.[0] ?? "";
    assert.match(brouillons, /#\/fiche\/1"/);
    assert.match(relues, /#\/fiche\/2"/);
  }
});

test("an empty state is a sentence of the catalogue, a failing state is a translated alert, a state still loading is a status", async () => {
  const vide = new ServeurFictif();
  const html = await pageFiches(source(vide, undefined));
  assert.ok(texte(html).includes(en["fiche.list.empty.draft"]) && texte(html).includes(en["fiche.list.empty.reviewed"]));
  assert.doesNotMatch(html, /<ul/);
  const panne: SourceCycleFiche = { ...source(vide, undefined), lister: async () => Promise.reject(new ErreurApi("DATABASE_UNAVAILABLE")) };
  const enPanne = await pageFiches(panne);
  assert.match(enPanne, /<p role="alert" class="page-erreur">/);
  assert.ok(texte(enPanne).includes(en["error.DATABASE_UNAVAILABLE"]));
  assert.doesNotMatch(enPanne, /DATABASE_UNAVAILABLE/);
  const charge = propre(rendre(h(QueryClientProvider, { client: nouveauClient() }, h(PageFiches, { cycle: source(vide, undefined) })), "en"));
  assert.match(charge, /<p role="status">/);
  assert.ok(texte(charge).includes(en["page.loading"]));
});

test("the list holds a heading per section under the title, links only, no tab stop of its own and no text outside the catalogue", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1" });
  const html = await pageFiches(source(serveur, undefined));
  assert.deepEqual([...html.matchAll(/<h([1-6])/g)].map((m) => Number(m[1])), [2, 3, 3]);
  assert.doesNotMatch(html, /tabindex|role="button"|<button|onclick/i);
  assert.doesNotMatch(html, /style=/);
});

// ---- the screen of one sheet --------------------------------------------------------------------------------------------------------

test("a draft shows the action to review it, a reviewed sheet the action to publish it, a published sheet none", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1", state: "draft" });
  serveur.ajouter({ id: "2", state: "reviewed" });
  serveur.ajouter({ id: "3", state: "published" });
  const cycle = source(serveur, "agile-lead-2");
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const brouillon = await pageFiche(serveur, cycle, "1", langue);
    assert.match(brouillon, new RegExp(`<button type="button" class="fiche-bouton">${c["fiche.action.review"]}</button>`), langue);
    assert.doesNotMatch(brouillon, new RegExp(`>${c["fiche.action.publish"]}<`), langue);
    const relue = await pageFiche(serveur, cycle, "2", langue);
    assert.match(relue, new RegExp(`<button type="button" class="fiche-bouton">${c["fiche.action.publish"]}</button>`), langue);
    assert.doesNotMatch(relue, new RegExp(`>${c["fiche.action.review"]}<`), langue);
    const publiee = await pageFiche(serveur, cycle, "3", langue);
    assert.doesNotMatch(publiee, new RegExp(`>(${c["fiche.action.review"]}|${c["fiche.action.publish"]})<`), langue);
    assert.match(publiee, /data-etat-fiche="published"/);
  }
});

test("the screen links back to the list and to the reading page of the sheet, whatever its kind", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1", chart: "lead_cycle_h5" });
  serveur.ajouter({ id: "2", chart: "lead_cycle_h1" });
  const cycle = source(serveur, undefined);
  const h5 = await pageFiche(serveur, cycle, "1");
  assert.match(h5, new RegExp(`<a class="lien" href="${ADRESSE_FICHES}">${en["fiche.cycle.back"]}</a>`));
  assert.match(h5, new RegExp(`<a class="lien" href="${adresseConviction("lead_cycle_h5", "1").replaceAll("/", "\\/")}">${en["fiche.cycle.read"]}</a>`));
  const h1 = await pageFiche(serveur, cycle, "2");
  assert.match(h1, new RegExp(`href="${adresseConviction("lead_cycle_h1", "2").replaceAll("/", "\\/")}"`));
});

test("a sheet that cannot be read is a translated alert; a screen without a reader opens no sheet", async () => {
  const serveur = new ServeurFictif();
  const cycle = source(serveur, undefined);
  const client = nouveauClient();
  const lire = (identifiant: string) => lireFicheHttp(identifiant, serveur.fetch);
  await client.prefetchQuery(optionsFiche(lire, "99"));
  const html = propre(rendre(h(QueryClientProvider, { client }, h(PageFiche, { id: "99", lire, cycle })), "en"));
  assert.match(html, /role="alert"/);
  assert.ok(texte(html).includes(en["error.UNKNOWN_SHEET"]));
  assert.doesNotMatch(html, /UNKNOWN_SHEET/);
});

// ---- the whole way, from the draft to the publication -------------------------------------------------------------------------------

test("the way of the audit: a draft made by its author, found under the reviewer, reviewed, then published by its author, each step on the screens", async () => {
  const serveur = new ServeurFictif();
  const reviewer = source(serveur, "agile-lead-2");
  const author = source(serveur, "agile-lead-1");

  // 0. The author makes a draft from the dashboard (the creation of the dashboard's own route), then leaves the dashboard.
  const brouillon = await creerFicheHttp(() => "agile-lead-1", serveur.fetch)({ chart: "lead_cycle_h5", scope: scopeFiche({ kind: "team", team: IDENTIFIANT_OPAQUE }), dataDate: "2026-10-05" });
  assert.deepEqual(brouillon, { id: "1", state: "draft" });

  // 1. The reviewer finds the draft in the list, a link to its screen.
  const liste = await pageFiches(reviewer);
  assert.match(/data-etat-liste="draft"[\s\S]*?<\/section>/.exec(liste)?.[0] ?? "", /href="#\/fiche\/1"/);

  // 2. The screen offers the review; the author cannot review their own sheet (the refusal is the service's, told in words).
  assert.match(await pageFiche(serveur, reviewer, "1"), /fiche-bouton">Mark as reviewed</);
  assert.deepEqual(await author.relire("1"), { ok: false, code: "SELF_REVIEW_REFUSED" });

  // 3. The reviewer reviews it; it leaves the first section and enters the second; the screen now offers the publication.
  assert.deepEqual(await reviewer.relire("1"), { ok: true });
  const apresRelecture = await pageFiches(reviewer);
  assert.doesNotMatch(/data-etat-liste="draft"[\s\S]*?<\/section>/.exec(apresRelecture)?.[0] ?? "", /href="#\/fiche\/1"/);
  assert.match(/data-etat-liste="reviewed"[\s\S]*?<\/section>/.exec(apresRelecture)?.[0] ?? "", /href="#\/fiche\/1"/);
  assert.match(await pageFiche(serveur, author, "1"), /fiche-bouton">Publish</);

  // 4. Only the author publishes it; then it is frozen and in no list.
  assert.deepEqual(await reviewer.publier("1"), { ok: false, code: "NOT_AUTHOR" });
  assert.deepEqual(await author.publier("1"), { ok: true });
  const fin = await pageFiches(reviewer);
  assert.doesNotMatch(fin, /href="#\/fiche\/1"/);
  const figee = await pageFiche(serveur, author, "1");
  assert.match(figee, /data-etat-fiche="published"/);
  assert.doesNotMatch(figee, /fiche-bouton">(Mark as reviewed|Publish)</);
  assert.equal(serveur.fiches.get("1")?.state, "published");
});

// ---- the application: the route, the navigation, the link from the reading page ------------------------------------------------------

async function application(props: Partial<Parameters<typeof Application>[0]>, serveur: ServeurFictif, utilisateur: string | undefined = "agile-lead-2"): Promise<string> {
  const val = (v: number) => ({ state: "value" as const, value: v });
  const ligne = (debut: string | null) => ({ team: EQUIPE_SYNTHETIQUE, period: debut === null ? "pooled_year" : "quarter", quarter_start: debut, items_lt: val(30), items_ct: val(30), lead_median_days: val(40), cycle_median_days: val(10) });
  const vue = { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows: ["2025-10-01", "2026-01-01", "2026-04-01", "2026-07-01", null].map(ligne), sources: ["flow"] };
  const reponse = servirTableau(tableauLeadCycle(vue as never, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe), { jeu: "synthetic", comptesAutorises: false, afficherNoms: false });
  const lireTableau = async () => reponse;
  const client = nouveauClient();
  await client.prefetchQuery(optionsLeadCycle(lireTableau));
  const cycle = source(serveur, utilisateur);
  const lireFiche = (id: string) => lireFicheHttp(id, serveur.fetch);
  for (const etat of ETATS_EN_COURS) await client.prefetchQuery(optionsListeFiches(cycle.lister, etat));
  const idFiche = props.ficheInitiale ?? props.convictionInitiale?.id;
  if (idFiche !== undefined) await client.prefetchQuery(optionsFiche(lireFiche, idFiche));
  const tableau = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  return propre(rendre(h(QueryClientProvider, { client }, h(Application, { tableau, lireFiche, cycle, ...props })), "en"));
}

test("the application mounts the list on #/fiches and the screen of a sheet on #/fiche/<id>, with the side navigation entry current on both", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1" });
  const liste = await application({ ecranInitial: "fiches" }, serveur);
  assert.ok(texte(liste).includes(en["fiche.list.title"]));
  assert.match(liste, /href="#\/fiche\/1"/);
  assert.match(liste, /<a href="#\/fiches" class="nav-entree nav-entree-courante" aria-current="page">Sheets in progress<\/a>/);
  const ecran = await application({ ecranInitial: "fiche", ficheInitiale: "1" }, serveur);
  assert.match(ecran, /fiche-bouton">Mark as reviewed</);
  assert.match(ecran, /<a href="#\/fiches" class="nav-entree nav-entree-courante" aria-current="page">/);
  // The banner of the shell follows the dataset code of the sheet, as on the conviction page.
  assert.match(ecran, /class="banniere" data-jeu="synthetic"/);
});

test("without the source of the life cycle the routes are not offered: no navigation entry, the address gives the home", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1" });
  const sans = await application({ ecranInitial: "fiches", cycle: undefined }, serveur);
  assert.doesNotMatch(sans, /href="#\/fiches"/);
  assert.doesNotMatch(sans, /href="#\/fiche\/1"/);
  assert.ok(texte(sans).includes(en["home.title"]));
});

test("the navigation entry is a link of the tools group, in both languages, current only on the two screens of the life cycle", () => {
  for (const langue of ["en", "fr"] as const) {
    const libelle = catalogues[langue]["nav.sheets"];
    const courante = rendre(h(NavigationLaterale, { accueilCourant: false, convictions: [], tableau: { courant: false }, fiches: { courant: true } }), langue);
    assert.match(courante, new RegExp(`<a href="#/fiches" class="nav-entree nav-entree-courante" aria-current="page">${libelle}</a>`), langue);
    const autre = rendre(h(NavigationLaterale, { accueilCourant: true, convictions: [], fiches: { courant: false } }), langue);
    assert.match(autre, new RegExp(`<a href="#/fiches" class="nav-entree">${libelle}</a>`), langue);
    assert.doesNotMatch(rendre(h(NavigationLaterale, { accueilCourant: true, convictions: [] }), langue), /href="#\/fiches"/);
  }
});

test("the reading page of a sheet in progress links to its life cycle screen; a published sheet, or a page without the source, has no such link", () => {
  for (const etat of ["draft", "reviewed"] as const) {
    const f = ficheH1("not_settled", { etat });
    for (const langue of ["en", "fr"] as const) {
      const html = propre(rendre(h(FicheConviction, { fiche: f, adresseCycle: adresseFiche("fiche-h1-1") }), langue));
      assert.match(html, new RegExp(`<a class="lien" href="#/fiche/fiche-h1-1">${catalogues[langue]["fiche.cycle.open"]}</a>`), `${etat} ${langue}`);
    }
    assert.doesNotMatch(propre(rendre(h(FicheConviction, { fiche: f }), "en")), /href="#\/fiche\//);
  }
  assert.doesNotMatch(propre(rendre(h(FicheConviction, { fiche: ficheH1("not_settled", { etat: "published" }) }), "en")), /href="#\/fiche\//);
});

test("the conviction page of the application offers the life cycle link for a draft, with the source, and not for a published sheet", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1", state: "draft", chart: "lead_cycle_h5" });
  serveur.ajouter({ id: "2", state: "published", chart: "lead_cycle_h5" });
  const brouillon = await application({ ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h5", id: "1" } }, serveur);
  assert.match(brouillon, /<a class="lien" href="#\/fiche\/1">/);
  const publiee = await application({ ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h5", id: "2" } }, serveur);
  assert.doesNotMatch(publiee, /href="#\/fiche\//);
  const sans = await application({ ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h5", id: "1" }, cycle: undefined }, serveur);
  assert.doesNotMatch(sans, /href="#\/fiche\//);
});

// ---- the keyboard, the catalogues, the sources ------------------------------------------------------------------------------------------

test("the way is made of native links and buttons: no tab stop forced, no button role on a link, no handler on a non-interactive element", async () => {
  const serveur = new ServeurFictif();
  serveur.ajouter({ id: "1", state: "draft" });
  serveur.ajouter({ id: "2", state: "reviewed" });
  const cycle = source(serveur, undefined);
  const pages = [await pageFiches(cycle), await pageFiche(serveur, cycle, "1"), await pageFiche(serveur, cycle, "2"), await application({ ecranInitial: "fiches" }, serveur)];
  for (const html of pages) {
    assert.doesNotMatch(html, /tabindex|role="button"|onclick|href="javascript:/i);
    // Every link has a target and a name; every button is a button of type "button" with a name.
    for (const lien of html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)) {
      assert.match(lien[1], /\bhref="#[^"]+"/, "link without a target");
      assert.notEqual(texte(lien[2]).trim() + (/<img[^>]*alt="[^"]+"/.test(lien[2]) ? "alt" : ""), "", "link without a name");
    }
    for (const bouton of html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)) {
      assert.match(bouton[1], /\btype="button"/);
      assert.notEqual(texte(bouton[2]).trim(), "");
    }
  }
  const fichiers = sources(FRONT, "src/pages", [".ts"]);
  const pagesSources = fichiers.filter((f) => f.nom === "src/pages/PageFiches.ts" || f.nom === "src/pages/PageFiche.ts");
  assert.equal(pagesSources.length, 2);
  for (const f of pagesSources) assert.doesNotMatch(f.contenu, /onClick|onKeyDown|tabIndex|role:\s*"button"/, f.nom);
});

test("every key of the life cycle screens is in both catalogues, with a text in each language, and nothing else carries the prefix", () => {
  const cles = ["nav.sheets", "fiche.list.title", "fiche.list.intro", "fiche.list.section.draft", "fiche.list.section.reviewed", "fiche.list.empty.draft", "fiche.list.empty.reviewed", "fiche.list.item", "fiche.cycle.open", "fiche.cycle.back", "fiche.cycle.read"] as const;
  for (const cle of cles) {
    assert.ok(typeof en[cle] === "string" && en[cle] !== "", `en ${cle}`);
    assert.ok(typeof fr[cle] === "string" && fr[cle] !== "", `fr ${cle}`);
    assert.notEqual(en[cle], fr[cle], cle);
  }
  assert.deepEqual(Object.keys(en).filter((c) => c.startsWith("fiche.list.")).sort(), cles.filter((c) => c.startsWith("fiche.list.")).sort());
  assert.deepEqual(Object.keys(en).filter((c) => c.startsWith("fiche.cycle.")).sort(), cles.filter((c) => c.startsWith("fiche.cycle.")).sort());
});

test("the two new pages name no verdict function and read the sheet through the existing reader and the existing cache key", () => {
  for (const nom of ["PageFiches.ts", "PageFiche.ts"]) {
    const contenu = readFileSync(`${FRONT}src/pages/${nom}`, "utf8");
    assert.doesNotMatch(contenu.replace(/^\s*\/\/.*$/gm, ""), /h1Verdict|h5Verdict|verdictFinal|compositionConviction|fetch\(/, nom);
  }
  assert.match(readFileSync(`${FRONT}src/pages/PageFiche.ts`, "utf8"), /optionsFiche/);
});
