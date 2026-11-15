// Task 19.7 (Q54 bis): the front reads the real routes when the server is present. Every test injects the fetch: no network. The client
// only carries (method, address, body, header), turns a refusal into a code of the catalogue, and passes on both forms of the answer.
import assert from "node:assert/strict";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";

import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";
import type { ReponseLeadCycle } from "@mothra/contract";
import { reduceToStatistics } from "@mothra/contract";

import { RefusFiche } from "../src/api/fiche.ts";
import { choisirSource, completerFicheHttp, creerFicheHttp, EN_TETE_UTILISATEUR, lireFicheHttp, lireLeadCycleHttp, serveurPresent, sourceHttp } from "../src/api/http.ts";
import { ErreurApi } from "../src/api/vue.ts";
import { Banniere } from "../src/composants/Banniere.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { Application } from "../src/Application.ts";
import { CLE_IDENTIFIANT, ecrireIdentifiant, identifiantValide, lireIdentifiant } from "../src/api/identifiant.ts";
import { PageChargement } from "../src/pages/PageChargement.ts";
import { VueDemarrage } from "../src/pages/PageDemarrage.ts";
import { ContenuTableau, ouvrirBrouillon } from "../src/pages/PageTableau.ts";
import { SOURCE_SIMULEE } from "../src/simule/leadCycle.ts";
import { choixRadio, rendre } from "./rendu.ts";

const en = catalogues.en;
const S = 7919; // sentinel count

interface Appel {
  url: string;
  methode: string | undefined;
  entetes: Record<string, string>;
  corps: unknown;
}

// A fetch that answers the given responses in turn and records what it was asked.
function faux(...reponses: Array<Response | Error>): { appeler: typeof fetch; appels: Appel[] } {
  const appels: Appel[] = [];
  const appeler = (async (url: string, options: RequestInit = {}) => {
    appels.push({
      url,
      methode: options.method,
      entetes: (options.headers ?? {}) as Record<string, string>,
      corps: typeof options.body === "string" ? JSON.parse(options.body) : undefined,
    });
    const suivante = reponses.shift() ?? new Error("no answer left");
    if (suivante instanceof Error) throw suivante;
    return suivante;
  }) as unknown as typeof fetch;
  return { appeler, appels };
}

const json = (corps: unknown, statut = 200): Response =>
  new Response(JSON.stringify(corps), { status: statut, headers: { "content-type": "application/json" } });

const point = { quarter: "2026-Q3", lead: { state: "value" as const, value: 15 }, cycle: { state: "value" as const, value: 10 }, items: { state: "value" as const, value: S } };
const complete: ReponseLeadCycle = {
  threshold: 5,
  dataDate: "2026-10-05",
  dataset: "synthetic",
  product: [],
  teams: [{ team: "Team A", teamId: identifiantEquipe("Team A"), points: [point] }],
};
const reduite = reduceToStatistics({ ...complete, dataset: "real" });
const DATE = "2026-10-05";
const PORTEE = scopeFiche({ kind: "team", team: identifiantEquipe("Team A") });
const UTILISATEUR = () => "agile-lead-1";

function afficher(reponse: ReponseLeadCycle | typeof reduite, fiche: Parameters<typeof ContenuTableau>[0]["fiche"] = { genre: "aucune" }): string {
  return rendre(
    h(ContenuTableau, { reponse, portee: "Team A", surPortee: () => undefined, fiche, surFaire: () => undefined, surCreer: () => undefined, simulee: false }),
    "en",
  ).replaceAll("&#x27;", "'");
}

test("the dashboard is read by GET on the real route, by a relative path, and both forms of the answer are passed on as received", async () => {
  const pleine = faux(json(complete));
  assert.deepEqual(await lireLeadCycleHttp(pleine.appeler), complete);
  assert.equal(pleine.appels.length, 1);
  assert.equal(pleine.appels[0].url, "/api/dashboards/lead_cycle");
  assert.equal(pleine.appels[0].methode, "GET");
  assert.equal(pleine.appels[0].corps, undefined);
  const reduit = faux(json(reduite));
  assert.deepEqual(await lireLeadCycleHttp(reduit.appeler), reduite);
});

test("the two forms of the answer are rendered: the complete one with its Items column, the reduced one without", async () => {
  const lue = await lireLeadCycleHttp(faux(json(complete)).appeler);
  assert.ok(afficher(lue).includes(en["tableau.column.items"]));
  const lueReduite = await lireLeadCycleHttp(faux(json(reduite)).appeler);
  const html = afficher(lueReduite);
  assert.ok(!html.includes(en["tableau.column.items"]));
  assert.doesNotMatch(html, /7919/);
  // On real data hypothesis 5 is not offered (Q48): it is shown disabled with its reason (D18, R-20261101-40, lot 3d), never enabled; hypothesis 1 is.
  const formulaire = afficher(lueReduite, { genre: "formulaire" });
  assert.deepEqual(choixRadio(formulaire).filter((c) => !c.desactive).map((c) => c.valeur), ["lead_cycle_h1"]);
  assert.ok(formulaire.includes(en["tableau.form.h5RealUnavailable"]));
  assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(formulaire)?.[0] ?? "").includes(en["conviction.nav.lead_cycle_h1"]));
  // R-20261101-40 (Q156): the simulated-data notice is the banner of the shell now; the panel shows none and its key left the catalogues.
  assert.ok(!html.includes("Simulated data"));
});

test("a refusal of the dashboard route is raised with its code, an unknown code or a network failure as the internal error", async () => {
  const code = async (reponse: Response | Error): Promise<string> => {
    try {
      await lireLeadCycleHttp(faux(reponse).appeler);
    } catch (echec) {
      assert.ok(echec instanceof ErreurApi);
      return echec.code;
    }
    return "AUCUNE";
  };
  assert.equal(await code(json({ error: "DATABASE_UNAVAILABLE" }, 503)), "DATABASE_UNAVAILABLE");
  assert.equal(await code(json({ error: "INTERNAL" }, 500)), "INTERNAL");
  assert.equal(await code(json({ error: "SOMETHING_NEW" }, 500)), "INTERNAL");
  assert.equal(await code(new Response("<html>nope</html>", { status: 404 })), "INTERNAL");
  assert.equal(await code(new Error("network down")), "INTERNAL");
  assert.equal(await code(json({ not: "an answer" })), "INTERNAL");
});

test("the creation of a sheet is a POST on the real route with the declared body and the header of the caller", async () => {
  const { appeler, appels } = faux(json({ id: "sheet-1", state: "draft" }));
  const creer = creerFicheHttp(UTILISATEUR, appeler);
  const brouillon = await creer({ chart: "lead_cycle_h1", scope: PORTEE, dataDate: DATE, managementQuestion: "predictability", effect: { text: "An effect.", lang: "en" } });
  assert.deepEqual(brouillon, { id: "sheet-1", state: "draft" });
  assert.equal(appels[0].url, "/api/sheets");
  assert.equal(appels[0].methode, "POST");
  assert.equal(appels[0].entetes[EN_TETE_UTILISATEUR], "agile-lead-1");
  assert.equal(appels[0].entetes["content-type"], "application/json");
  assert.deepEqual(appels[0].corps, { chart: "lead_cycle_h1", scope: PORTEE, dataDate: DATE, managementQuestion: "predictability", effect: { text: "An effect.", lang: "en" } });
  // A request without the optional fields carries none of them; without an identifier no header is sent.
  const sans = faux(json({ id: "sheet-2", state: "draft" }));
  await creerFicheHttp(() => undefined, sans.appeler)({ chart: "lead_cycle_h1", scope: PORTEE, dataDate: DATE });
  assert.deepEqual(sans.appels[0].corps, { chart: "lead_cycle_h1", scope: PORTEE, dataDate: DATE });
  assert.equal(EN_TETE_UTILISATEUR in sans.appels[0].entetes, false);
});

test("a draft made through the real source is shown without the notice of simulated data", async () => {
  const { appeler } = faux(json({ id: "sheet-3", state: "draft" }));
  const source = sourceHttp(UTILISATEUR, appeler);
  assert.equal(source.simulee, false);
  const etat = await ouvrirBrouillon(source.creer, "Team A", DATE, "lead_cycle_h1");
  assert.deepEqual(etat, { genre: "brouillon", id: "sheet-3" });
});

test("the refusals of the creation are shown by their code through the catalogue, never as the text of the server", async () => {
  for (const code of ["UNKNOWN_USER", "DATABASE_UNAVAILABLE", "NOT_FOUND", "THRESHOLDS_NOT_SET", "INVALID_REQUEST"]) {
    const { appeler } = faux(json({ error: code, message: "RAW SERVER TEXT" }, 400));
    const etat = await ouvrirBrouillon(creerFicheHttp(UTILISATEUR, appeler), "Team A", DATE, "lead_cycle_h1");
    assert.deepEqual(etat, { genre: "erreur", code });
    const html = afficher(reduite, etat);
    assert.ok(html.includes(en[`error.${code}` as keyof typeof en]), code);
    assert.doesNotMatch(html, /RAW SERVER TEXT|UNKNOWN_USER|DATABASE_UNAVAILABLE|NOT_FOUND|THRESHOLDS_NOT_SET|INVALID_REQUEST/);
  }
  // A code the front does not translate, and a failure of the network, are the internal error.
  for (const reponse of [json({ error: "SOMETHING_NEW" }, 500), new Error("network down")]) {
    const etat = await ouvrirBrouillon(creerFicheHttp(UTILISATEUR, faux(reponse).appeler), "Team A", DATE, "lead_cycle_h1");
    assert.deepEqual(etat, { genre: "erreur", code: "INTERNAL" });
  }
});

test("a refused text keeps the field and the reason, the count and the maximum with too_long only, and nothing else of the body", async () => {
  const refus = async (corps: unknown): Promise<RefusFiche> => {
    try {
      await creerFicheHttp(UTILISATEUR, faux(json(corps, 422)).appeler)({ chart: "lead_cycle_h1", scope: PORTEE, dataDate: DATE });
    } catch (echec) {
      assert.ok(echec instanceof RefusFiche);
      return echec;
    }
    throw new Error("no refusal");
  };
  const email = await refus({ error: "TEXT_REFUSED", field: "effect", reason: "email", value: "a@b.c" });
  assert.equal(email.code, "TEXT_REFUSED");
  assert.deepEqual(email.texte, { field: "effect", reason: "email" });
  const long = await refus({ error: "TEXT_REFUSED", field: "cause", reason: "too_long", count: 501, max: 500 });
  assert.deepEqual(long.texte, { field: "cause", reason: "too_long", count: 501, max: 500 });
  const etat = await ouvrirBrouillon(creerFicheHttp(UTILISATEUR, faux(json({ error: "TEXT_REFUSED", field: "effect", reason: "email" }, 422)).appeler), "Team A", DATE, "lead_cycle_h1");
  assert.deepEqual(etat, { genre: "texte_refuse", refus: { field: "effect", reason: "email" } });
  // A malformed refusal of a text is not a refusal of a text.
  const mal = await refus({ error: "TEXT_REFUSED", field: "other", reason: "email" });
  assert.equal(mal.code, "INTERNAL");
  assert.equal(mal.texte, undefined);
});

test("a sheet is read by GET and completed by PATCH, the identifier encoded in the address", async () => {
  const lecture = faux(json({ id: "a/b", state: "draft" }));
  const fiche = await lireFicheHttp("a/b", lecture.appeler);
  assert.equal(fiche.id, "a/b");
  assert.equal(lecture.appels[0].url, "/api/sheets/a%2Fb");
  assert.equal(lecture.appels[0].methode, "GET");

  const absente = faux(json({ error: "UNKNOWN_SHEET" }, 404));
  await assert.rejects(lireFicheHttp("x", absente.appeler), (echec: unknown) => echec instanceof ErreurApi && echec.code === "UNKNOWN_SHEET");
  const refusee = faux(json({ error: "SOMETHING_NEW" }, 500));
  await assert.rejects(lireFicheHttp("x", refusee.appeler), (echec: unknown) => echec instanceof ErreurApi && echec.code === "INTERNAL");

  const patch = faux(json({ id: "sheet-1", state: "draft" }));
  const modification = { managementQuestion: "predictability" as const, cause: { text: "A cause.", lang: "en" as const } };
  assert.deepEqual(await completerFicheHttp("sheet-1", modification, UTILISATEUR, patch.appeler), { ok: true });
  assert.equal(patch.appels[0].url, "/api/sheets/sheet-1");
  assert.equal(patch.appels[0].methode, "PATCH");
  assert.equal(patch.appels[0].entetes[EN_TETE_UTILISATEUR], "agile-lead-1");
  assert.deepEqual(patch.appels[0].corps, modification);
});

test("the refusals of the completion are returned by their code, with the detail of a refused text", async () => {
  const resultat = (reponse: Response | Error) => completerFicheHttp("sheet-1", { managementQuestion: "predictability" }, UTILISATEUR, faux(reponse).appeler);
  assert.deepEqual(await resultat(json({ error: "NOT_AUTHOR" }, 403)), { ok: false, code: "NOT_AUTHOR" });
  assert.deepEqual(await resultat(json({ error: "VERSION_FROZEN" }, 409)), { ok: false, code: "VERSION_FROZEN" });
  assert.deepEqual(await resultat(json({ error: "NOT_DRAFT" }, 409)), { ok: false, code: "NOT_DRAFT" });
  assert.deepEqual(await resultat(json({ error: "UNKNOWN_SHEET" }, 404)), { ok: false, code: "UNKNOWN_SHEET" });
  assert.deepEqual(await resultat(json({ error: "INVALID_REQUEST" }, 400)), { ok: false, code: "INVALID_REQUEST" });
  assert.deepEqual(await resultat(new Error("network down")), { ok: false, code: "INTERNAL" });
  assert.deepEqual(await resultat(json({ error: "TEXT_REFUSED", field: "effect", reason: "ticket_key" }, 422)), {
    ok: false,
    code: "TEXT_REFUSED",
    texte: { field: "effect", reason: "ticket_key" },
  });
});

test("the real source is chosen when the server answers, the simulated one when it is absent", async () => {
  // The server answers the dashboard route: an answer, or a refusal with a code of its own.
  assert.equal(await serveurPresent(faux(json(complete)).appeler), true);
  assert.equal(await serveurPresent(faux(json({ error: "DATABASE_UNAVAILABLE" }, 503)).appeler), true);
  // No server: a network failure, or the page of a development server that does not know the route.
  assert.equal(await serveurPresent(faux(new Error("network down")).appeler), false);
  assert.equal(await serveurPresent(faux(new Response("<!doctype html>", { status: 200 })).appeler), false);
  assert.equal(await serveurPresent(faux(new Response("Not found", { status: 404 })).appeler), false);

  // The mode is a parameter: the real source whatever the mode, the simulated one only in development.
  for (const developpement of [true, false]) {
    const reelle = await choisirSource(SOURCE_SIMULEE, UTILISATEUR, developpement, faux(json(complete)).appeler);
    assert.equal(reelle?.simulee, false);
    assert.notEqual(reelle, SOURCE_SIMULEE);
  }
  const simulee = await choisirSource(SOURCE_SIMULEE, UTILISATEUR, true, faux(new Error("network down")).appeler);
  assert.equal(simulee, SOURCE_SIMULEE);
  assert.equal(simulee.simulee, true);
});

test("in production a missing server gives no source, so the screen shows the failure; a retry probes again", async () => {
  assert.equal(await choisirSource(SOURCE_SIMULEE, UTILISATEUR, false, faux(new Error("network down")).appeler), undefined);
  assert.equal(await choisirSource(SOURCE_SIMULEE, UTILISATEUR, false, faux(new Response("<!doctype html>", { status: 200 })).appeler), undefined);
  // The same fetch, down then up: the second probe, started by the button, finds the server.
  const { appeler, appels } = faux(new Error("network down"), json(complete));
  assert.equal(await choisirSource(SOURCE_SIMULEE, UTILISATEUR, false, appeler), undefined);
  const apres = await choisirSource(SOURCE_SIMULEE, UTILISATEUR, false, appeler);
  assert.equal(apres?.simulee, false);
  assert.equal(appels.length, 2);
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const echec = rendre(h(VueDemarrage, { etat: { genre: "echec" }, reessayer: () => undefined }), langue);
    assert.match(echec, /role="alert"/);
    assert.ok(echec.includes(c["page.serverUnreachable"]), langue);
    assert.match(echec, new RegExp(`<button[^>]*>${c["page.retry"]}</button>`));
    assert.ok(rendre(h(VueDemarrage, { etat: { genre: "sonde" }, reessayer: () => undefined }), langue).includes(c["page.loading"]), langue);
  }
});

// A storage double, injected: nothing touches a browser.
function stockage(initial?: string, refuse = false) {
  const valeurs = new Map<string, string>(initial === undefined ? [] : [[CLE_IDENTIFIANT, initial]]);
  return {
    valeurs,
    getItem: (cle: string) => {
      if (refuse) throw new Error("blocked");
      return valeurs.get(cle) ?? null;
    },
    setItem: (cle: string, valeur: string) => {
      if (refuse) throw new Error("blocked");
      valeurs.set(cle, valeur);
    },
    removeItem: (cle: string) => {
      if (refuse) throw new Error("blocked");
      valeurs.delete(cle);
    },
  };
}

test("the identifier is checked against the format of D29 before it is stored, under the key mothra-user", () => {
  assert.equal(CLE_IDENTIFIANT, "mothra-user");
  for (const bon of ["agile-lead-1", "a", "0x", "role_po", "a".repeat(64)]) assert.equal(identifiantValide(bon), true, bon);
  for (const mauvais of ["", "Agile", "-lead", "_a", "Jean Dupont", "a@b.c", "a".repeat(65), "é"]) assert.equal(identifiantValide(mauvais), false, mauvais);
  const s = stockage();
  assert.equal(ecrireIdentifiant("Jean Dupont", s), "invalid");
  assert.equal(s.valeurs.size, 0, "a value that fails the format is never stored");
  assert.equal(ecrireIdentifiant(" agile-lead-1 ", s), "saved");
  assert.equal(s.valeurs.get("mothra-user"), "agile-lead-1");
  assert.equal(lireIdentifiant(s), "agile-lead-1");
  assert.equal(ecrireIdentifiant("", s), "saved");
  assert.equal(lireIdentifiant(s), undefined);
});

test("a storage that refuses is no identifier and no failure; a stored value that is not well formed is not read", () => {
  assert.equal(lireIdentifiant(stockage("agile-lead-1", true)), undefined);
  assert.equal(ecrireIdentifiant("agile-lead-1", stockage(undefined, true)), "unavailable");
  assert.equal(ecrireIdentifiant("agile-lead-1", undefined), "unavailable");
  assert.equal(lireIdentifiant(stockage("Jean Dupont")), undefined);
});

test("the header shows the field of the identifier with its help, in each language, and nothing when no storage is injected", () => {
  const s = stockage("agile-lead-1");
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const identifiant = { lire: () => lireIdentifiant(s), ecrire: (v: string) => ecrireIdentifiant(v, s) };
    const avec = rendre(h(QueryClientProvider, { client: new QueryClient() }, h(Application, { langueInitiale: langue, identifiant })), langue).replaceAll("&#x27;", "'");
    assert.ok(avec.includes(c["app.identity.label"]), langue);
    assert.ok(avec.includes(c["app.identity.help"]), langue);
    assert.ok(avec.includes(c["app.identity.save"]), langue);
    assert.equal(avec.split("agile-lead-1").length - 1, 1, "the value appears in its field only");
    const sans = rendre(h(QueryClientProvider, { client: new QueryClient() }, h(Application, { langueInitiale: langue })), langue);
    assert.ok(!sans.includes(c["app.identity.label"]), langue);
  }
  assert.equal(catalogues.en["app.identity.help"], "Pseudonym or role, not a person's name.");
  assert.equal(catalogues.fr["app.identity.help"], "Pseudonyme ou rôle, pas de nom de personne.");
});

test("the simulated source is declared synthetic: its dashboard carries the notice of the synthetic dataset and offers both hypotheses", async () => {
  const lue = await SOURCE_SIMULEE.lire();
  assert.equal(lue.dataset, "synthetic");
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const html = (fiche: Parameters<typeof ContenuTableau>[0]["fiche"]): string =>
      rendre(h(ContenuTableau, { reponse: lue, portee: "team-a", surPortee: () => undefined, fiche, surFaire: () => undefined, surCreer: () => undefined, simulee: true }), langue).replaceAll("&#x27;", "'");
    // R-20261101-129 (Q268 (a)): the notice of the synthetic dataset is a line of the banner of the shell, no longer a note of the dashboard.
    assert.ok(!html({ genre: "aucune" }).includes(c["fiche.syntheticNotice"]), langue);
    assert.ok(rendre(h(Banniere, { jeu: "synthetic" }), langue).replaceAll("&#x27;", "'").includes(c["fiche.syntheticNotice"]), langue);
    const formulaire = html({ genre: "formulaire" });
    assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(formulaire)?.[0] ?? "").includes(c["conviction.nav.lead_cycle_h5"]), langue);
    assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(formulaire)?.[0] ?? "").includes(c["conviction.nav.lead_cycle_h1"]), langue);
  }
});

test("hypothesis 5 is offered only on the declared synthetic dataset: an answer without a dataset code does not offer it", () => {
  const sansJeu: ReponseLeadCycle = { ...complete, dataset: undefined };
  const html = rendre(
    h(ContenuTableau, { reponse: sansJeu, portee: "Team A", surPortee: () => undefined, fiche: { genre: "formulaire" }, surFaire: () => undefined, surCreer: () => undefined, simulee: false }),
    "en",
  ).replaceAll("&#x27;", "'");
  // R-20261101-40 (lot 3d): no enabled hypothesis 5 choice, as strict as before; it is shown disabled with its reason (D18).
  assert.deepEqual(choixRadio(html).filter((c) => !c.desactive).map((c) => c.valeur), ["lead_cycle_h1"]);
  assert.ok(html.includes(en["tableau.form.h5RealUnavailable"]));
  assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(html)?.[0] ?? "").includes(en["conviction.nav.lead_cycle_h1"]));
});

test("the loading state shown while the server is looked for is the catalogue's, in each language", () => {
  for (const langue of ["en", "fr"] as const) {
    const html = rendre(h(PageChargement), langue);
    assert.match(html, /role="status"/);
    assert.ok(html.includes(catalogues[langue]["page.loading"]), langue);
  }
});
