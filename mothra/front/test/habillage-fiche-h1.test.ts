// Lot 3b of mothra-demo-habillage, phase A (tasks 6.0, 6.2, 6.3): the sheet status, the competing explanations, the hypothesis 1 sheet page and
// the demonstration screen (the published sheet on real data, in its reduced form), in the fallback of design D4 (R-20261101-34: no bar and no
// composition chart, the verdict, the ratios and the thresholds as text). Every sheet answer comes from `corpsDepuisVues` on synthetic view rows,
// reduced by `reduceToStatistics` for real data (D15, test/fiches-h1.ts); the free inputs of a component are written here. The bars, the
// composition chart and their tests (task 6.1) come with phase B, once lot 1b is on main.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";

import { servirTableau, tableauLeadCycle } from "@mothra/contract";
import type { ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { Application } from "../src/Application.ts";
import { adresseConviction, convictionDuHash } from "../src/api/adresse.ts";
import type { ExplicationFiche, ReponseFiche } from "../src/api/fiche.ts";
import { CLE_DERNIERE_FICHE } from "../src/api/derniereFiche.ts";
import { optionsFiche } from "../src/api/ficheLecture.ts";
import { lireFicheHttp } from "../src/api/http.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import { ExplicationsConcurrentes } from "../src/composants/ExplicationsConcurrentes.ts";
import { FicheConviction, libelleEquipe } from "../src/composants/FicheConviction.ts";
import { StatutFiche } from "../src/composants/StatutFiche.ts";
import { GabaritFiche } from "../src/gabarits/GabaritFiche.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { ErreurApi } from "../src/api/vue.ts";
import { PageConviction } from "../src/pages/PageConviction.ts";
import { ContenuVue } from "../src/pages/PageSquelette.ts";
import { SANS_FILTRES } from "../src/api/filtres.ts";
import { optionsPanneau } from "../src/api/panneaux.ts";
import { panneauxAffiches, SectionPanneaux } from "../src/composants/PanneauxProduit.ts";
import { SOURCE_PANNEAUX_SIMULEE } from "../src/simule/panneaux.ts";
import { ficheH5 } from "./fiches-h5.ts";
import { CAS_H1, EQUIPE_SYNTHETIQUE, ficheH1, IDENTIFIANT_OPAQUE } from "./fiches-h1.ts";
import type { CasH1 } from "./fiches-h1.ts";
import { rendre, texte } from "./rendu.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

function fiche(f: ReponseFiche, props: Partial<Parameters<typeof FicheConviction>[0]> = {}, langue: Langue = "en"): string {
  return propre(rendre(h(FicheConviction, { fiche: f, ...props }), langue));
}

// The display state each case must give, and the verdict of the service it comes from (the fixture is checked, not trusted).
const ATTENDU: Record<CasH1, { verdict: string; etat: string }> = {
  confirmed: { verdict: "confirmed", etat: "confirmed" },
  refuted: { verdict: "refuted", etat: "refuted" },
  not_settled: { verdict: "not_settled", etat: "not_settled" },
  insufficient_sample: { verdict: "insufficient_sample", etat: "insufficient_sample" },
  masked: { verdict: "insufficient_sample", etat: "masked" },
  not_comparable: { verdict: "refuted", etat: "refuted" },
};

// ---- the answers come from the contract (D15) ------------------------------------------------------------------------------------

test("the sheet answers of the tests come from the contract: one per case, the verdict is the service's, the real form carries no count", () => {
  for (const cas of CAS_H1) {
    const synthetique = ficheH1(cas);
    assert.equal(synthetique.verdict, ATTENDU[cas].verdict, cas);
    assert.equal(synthetique.method.hypothesis, "h1_first_half");
    assert.equal(synthetique.dataset, "synthetic");
    const reelle = ficheH1(cas, { jeu: "real" });
    assert.equal(reelle.dataset, "real");
    assert.ok(reelle.method.limits.includes("reduced_form"), cas);
    assert.equal(JSON.stringify(reelle).includes('"items"'), false, cas);
    assert.equal(JSON.stringify(reelle).includes("7919"), false, cas);
  }
  assert.equal(ficheH1("confirmed", { jeu: "real" }).method.coverage, undefined);
  // The rows whose ratios would confirm: the contract itself gives "not settled" to a team sheet (the ban of D20, unplanned work not measurable
  // for a team, D33). The case "confirmed" sets the verdict on those rows to exercise the display state; this is the only hand-set field.
  const duContrat = ficheH1("confirmed", { verdictDuContrat: true });
  assert.equal(duContrat.verdict, "not_settled");
  assert.ok(duContrat.verdictReasons.some((r) => r.explanation === "unplanned_work"));
  assert.deepEqual({ ...duContrat, verdict: "confirmed", verdictReasons: [], verdictFindings: ["h1_above_upper"] }, ficheH1("confirmed"));
});

// ---- the sheet status (task 6.0, 6.2) ---------------------------------------------------------------------------------------------

test("the status shows the draft, the reviewed and the published sheet with its date, version and frozen statement, and no action", () => {
  for (const langue of ["en", "fr"] as const) {
    const catalogue = catalogues[langue];
    const brouillon = propre(rendre(h(StatutFiche, { etat: "draft" }), langue));
    assert.match(brouillon, /data-etat-fiche="draft"/);
    assert.ok(texte(brouillon).includes(catalogue["fiche.state.draft"]));
    assert.doesNotMatch(texte(brouillon), new RegExp(catalogue["fiche.frozen"].slice(0, 12)));
    const relue = propre(rendre(h(StatutFiche, { etat: "reviewed", publieLe: "2026-11-02", version: 2 }), langue));
    assert.match(relue, /data-etat-fiche="reviewed"/);
    assert.ok(texte(relue).includes(catalogue["fiche.state.reviewed"]));
    assert.doesNotMatch(relue, /statut-fige/, "a reviewed sheet is not frozen and shows no date");
    const publiee = propre(rendre(h(StatutFiche, { etat: "published", publieLe: "2026-11-02", version: 2 }), langue));
    assert.match(publiee, /data-etat-fiche="published"/);
    // Q3 (a), R-20261101-126: one pill with a lock, the state word not repeated, the date in its long form.
    assert.match(publiee, /class="statut-fiche statut-publiee"/);
    assert.match(publiee, /<svg[^>]*data-icone="lock"[^>]*aria-hidden="true"/);
    assert.doesNotMatch(publiee, /\p{Extended_Pictographic}/u, "the lock is a vector icon, not an emoji (R-20261101-127)");
    assert.equal((publiee.match(/<span class="statut-etat"/g) ?? []).length, 0);
    // Capitalised since the design review (R-20261104-42): the line itself starts with the state word, so the check counts the word, once at most.
    assert.ok(texte(publiee).toLowerCase().split(catalogue["fiche.state.published"].toLowerCase()).length - 1 <= 1, "the state word is not repeated beside the line");
    assert.doesNotMatch(publiee, /<button|<a |<input/);
  }
  const anglais = texte(propre(rendre(h(StatutFiche, { etat: "published", publieLe: "2026-11-02", version: 2 }), "en")));
  assert.equal(anglais, "Published on November 2, 2026 · version 2 · frozen");
  assert.equal(anglais, en["fiche.status.publishedLine"].replace("{date}", "November 2, 2026").replace("{number}", "2"));
  const francais = texte(propre(rendre(h(StatutFiche, { etat: "published", publieLe: "2026-11-02", version: 2 }), "fr")));
  assert.equal(francais, "Publiée le 2 novembre 2026 · version 2 · figée");
  // A published answer without its date or version falls back on the word of the state and the frozen statement.
  const sansDate = texte(propre(rendre(h(StatutFiche, { etat: "published" }), "en")));
  assert.ok(sansDate.includes(en["fiche.state.published"]) && sansDate.includes(en["fiche.frozen"]));
});

// ---- the competing explanations (task 6.0, 6.2) -----------------------------------------------------------------------------------

const EXPLICATIONS_LIBRES = [
  { name: "unplanned_work", state: "ruled_out" },
  { name: "capacity", state: "not_ruled_out", reason: "no_adopted_threshold" },
  { name: "dependencies", state: "not_measurable", reason: "no_data" },
] as ExplicationFiche[];

function blocExplications(explications: readonly ExplicationFiche[], signalMontre: boolean, motifsSignal: readonly string[], langue: Langue = "en"): string {
  return propre(rendre(h(ExplicationsConcurrentes, { explications, signalMontre, motifsSignal }), langue));
}

test("each explanation state is drawn with and without a reason, and the signal as shown, not raised or masked, in both languages", () => {
  for (const langue of ["en", "fr"] as const) {
    const catalogue = catalogues[langue];
    const html = blocExplications(EXPLICATIONS_LIBRES, false, [], langue);
    for (const e of EXPLICATIONS_LIBRES) {
      assert.match(html, new RegExp(`data-explication="${e.name}" data-etat-explication="${e.state}"`));
      assert.ok(texte(html).includes(catalogue[`fiche.explanation.${e.name}`]), `${e.name} ${langue}`);
      assert.ok(texte(html).includes(catalogue[`fiche.explanationState.${e.state}`]), `${e.state} ${langue}`);
      if (e.reason !== undefined) assert.ok(texte(html).includes(catalogue[`fiche.reason.${e.reason}`]), `${e.reason} ${langue}`);
    }
    assert.equal((texte(html).match(new RegExp(catalogue["fiche.reason.no_data"], "g")) ?? []).length, 1, "a state without a reason shows none");
    assert.ok(texte(html).includes(catalogue["fiche.explanations.title"]));
    assert.match(html, /data-signal="not_raised"/);
    assert.ok(texte(html).includes(catalogue["fiche.signal.notRaised"]));
    assert.match(blocExplications(EXPLICATIONS_LIBRES, true, [], langue), /data-signal="shown"/);
    assert.ok(texte(blocExplications(EXPLICATIONS_LIBRES, true, [], langue)).includes(catalogue["fiche.attachmentSignal"]));
    const masque = blocExplications(EXPLICATIONS_LIBRES, false, ["tasks_without_team_share_masked"], langue);
    assert.match(masque, /data-signal="masked"/);
    assert.ok(texte(masque).includes(catalogue["fiche.reason.tasks_without_team_share_masked"]));
  }
});

test("an unknown name, state or reason has a fallback sentence, never the raw code, and no measure is shown", () => {
  const inconnues = [{ name: "mystery", state: "strange", reason: "odd" }] as unknown as ExplicationFiche[];
  const html = blocExplications(inconnues, false, []);
  assert.ok(texte(html).includes(en["fiche.explanation.unknown"]));
  assert.ok(texte(html).includes(en["fiche.reason.unknown"]));
  assert.doesNotMatch(texte(html), /mystery|strange|odd/);
  const avecMesure = [{ name: "unplanned_work", state: "not_ruled_out", measure: { state: "value", value: 31 } }] as ExplicationFiche[];
  assert.doesNotMatch(texte(blocExplications(avecMesure, false, [])), /31|%/, "only states and reasons, never a measure");
});

// ---- the template: the added slots change nothing for a page that does not use them (Q240, R-20261101-121) -------------------------

test("the sheet template draws the status and the explanations in their place, and draws what it drew before when they are not given", () => {
  const avant = rendre(h(GabaritFiche, { enonce: "conviction.statement.lead_cycle_h1", preuve: h("p", null, "P"), encarts: h("p", null, "E"), pied: h("p", null, "F") }), "en");
  assert.doesNotMatch(avant, /bloc-explications|fiche-ligne-badge/);
  const complet = rendre(
    h(GabaritFiche, {
      enonce: "conviction.statement.lead_cycle_h1",
      badge: h("span", null, "B"),
      statut: h("span", null, "S"),
      contexte: "C",
      preuve: h("p", null, "P"),
      encarts: h("p", null, "E"),
      explications: h("p", null, "X"),
      pied: h("p", null, "F"),
    }),
    "en",
  );
  const places = ["<h1", ">B<", ">S<", "fiche-contexte", ">P<", ">E<", ">X<", "<footer"].map((m) => complet.indexOf(m));
  assert.ok(places.every((p) => p >= 0));
  assert.deepEqual([...places].sort((a, b) => a - b), places);
  const sansBadge = rendre(h(GabaritFiche, { enonce: "conviction.statement.lead_cycle_h1", statut: h("span", null, "S") }), "en");
  assert.match(sansBadge, /fiche-ligne-badge/);
});

// ---- the order of the page, the badge, the display state (task 6.2) ----------------------------------------------------------------

test("the page keeps the order: statement, badge and status, evidence, the three insets, the competing explanations, the footer", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const html = fiche(ficheH1("confirmed", { jeu }));
    const marques = ["<h1", 'class="badge', 'class="statut-fiche', "carte carte-preuve", 'data-encart="question"', 'data-encart="effet"', 'data-encart="cause"', "explications-concurrentes", "<footer"];
    const places = marques.map((m) => html.indexOf(m));
    assert.ok(places.every((p) => p >= 0), `${jeu} : ${marques[places.findIndex((p) => p < 0)]}`);
    assert.deepEqual([...places].sort((a, b) => a - b), places, jeu);
    assert.ok(texte(html).includes(en["conviction.statement.lead_cycle_h1"]));
  }
});

test("each case shows the badge and the outline of its display state, in both languages", () => {
  for (const cas of CAS_H1) {
    for (const langue of ["en", "fr"] as const) {
      const html = fiche(ficheH1(cas), {}, langue);
      assert.match(html, new RegExp(`class="badge[^"]*" data-etat="${ATTENDU[cas].etat}"`), `${cas} ${langue}`);
      assert.match(html, new RegExp(`carte-preuve" data-etat="${ATTENDU[cas].etat}"`), `${cas} ${langue}`);
      assert.ok(texte(html).includes(catalogues[langue][`conviction.badge.${ATTENDU[cas].etat}`]), `${cas} ${langue}`);
    }
  }
});

test("an insufficient sample and a masked sheet show their sentence alone: no key figure, no ratio, no threshold", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const insuffisante = fiche(ficheH1("insufficient_sample", { jeu }));
    assert.ok(texte(insuffisante).includes(en["conviction.finding.insufficient_sample"]));
    const masquee = fiche(ficheH1("masked", { jeu }));
    assert.ok(texte(masquee).includes(en["conviction.finding.masked"]));
    for (const html of [insuffisante, masquee]) {
      assert.doesNotMatch(html, /data-chiffre|data-rapport|data-repere|chiffres/, jeu);
      assert.doesNotMatch(texte(html), /lower threshold|upper threshold|days of waiting/, jeu);
    }
  }
});

test("the full form shows the waiting and the work of the pooled year; where the two medians cannot be compared it says so, never a corrected number", () => {
  const html = fiche(ficheH1("confirmed"));
  assert.match(html, /data-chiffre="wait"[\s\S]*?<span[^>]*data-state="value">30 d<\/span>/);
  assert.match(html, /data-chiffre="work"[\s\S]*?<span[^>]*data-state="value">10 d<\/span>/);
  assert.ok(texte(html).includes(en["conviction.figure.wait"].replace("{period}", en["tableau.quarter.pooledYear"])));
  assert.ok(texte(html).includes(en["conviction.footer.waitDefinition"]));
  const incomparable = fiche(ficheH1("not_comparable"));
  assert.match(incomparable, /data-chiffre="wait"[\s\S]*?data-state="not_comparable"/);
  assert.ok(texte(incomparable).includes(en["conviction.notComparable"]));
  assert.doesNotMatch(incomparable, /-2 d/);
});

// ---- the insets, the effect and the cause in their own language (task 6.2) ----------------------------------------------------------

test("the insets are the real fields of the sheet: the question, and the effect and the cause in their own language", () => {
  const f = ficheH1("confirmed");
  const html = fiche({ ...f, effect: { text: "Effet inventé.", lang: "fr" }, cause: { text: "Invented cause.", lang: "en" } });
  assert.ok(texte(html).includes(en["conviction.inset.managementQuestion"]) && texte(html).includes(en["fiche.question.predictability"]));
  assert.match(html, /<span lang="fr">Effet inventé\.<\/span>/);
  assert.match(html, /<span>Invented cause\.<\/span>/, "same language as the screen: no lang attribute");
  const francais = fiche({ ...f, effect: { text: "Effet inventé.", lang: "fr" }, cause: { text: "Invented cause.", lang: "en" } }, {}, "fr");
  assert.match(francais, /<span>Effet inventé\.<\/span>/);
  assert.match(francais, /<span lang="en">Invented cause\.<\/span>/);
  const vide = fiche(ficheH1("confirmed", { etat: "draft", texte: false }));
  assert.equal((texte(vide).match(new RegExp(en["fiche.text.missing"], "g")) ?? []).length, 2);
  const sansQuestion = fiche({ ...f, managementQuestion: undefined });
  assert.ok(texte(sansQuestion).includes(en["fiche.form.question.none"]));
});

test("the competing explanations of the sheet read the same on the full and the reduced form, with states and reasons only", () => {
  const complete = fiche(ficheH1("confirmed"));
  const reduite = fiche(ficheH1("confirmed", { jeu: "real" }));
  // The mention of the current links goes with the dependencies when the answer carries the measure (écart #16): the rest is the same.
  const bloc = (html: string): string => (/<section class="explications-concurrentes">[\s\S]*?<\/section>/.exec(html)?.[0] ?? "").replace(/<span class="fiche-mentions">[\s\S]*?<\/span>/g, "");
  assert.ok(bloc(complete).length > 0);
  assert.equal(bloc(complete), bloc(reduite));
  assert.doesNotMatch(texte(bloc(complete)), /%/);
});

// ---- no verdict to type, no action of the workflow (task 6.2) -----------------------------------------------------------------------

test("the page holds no field to type, no form and no action of the life cycle", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    for (const etat of ["draft", "reviewed", "published"] as const) {
      const html = fiche(ficheH1("confirmed", { jeu, etat }), { methodeOuverte: true });
      assert.doesNotMatch(html, /<input|<textarea|<select|<form/, `${jeu} ${etat}`);
      for (const cle of ["fiche.action.review", "fiche.action.complete"]) assert.ok(!texte(html).includes(en[cle]), `${cle} ${jeu} ${etat}`);
      // The one button is the toggle of the method face: nothing publishes, reviews or completes from this page.
      assert.equal((html.match(/<button/g) ?? []).length, 1, `${jeu} ${etat}`);
    }
  }
});

// ---- one team, named once, by its opaque identifier (R-20261101-27 point c, R-20261101-121 Q238) -------------------------------------

test("the context line names the team once, by its opaque identifier, in one function; the witness name of the dashboard never appears", async () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  assert.equal(libelleEquipe(f.method), IDENTIFIANT_OPAQUE);
  assert.equal(libelleEquipe({ ...f.method, scope: { level: "product", id: "product" } }), undefined);
  assert.equal(libelleEquipe({ ...f.method, scope: { level: "team", id: EQUIPE_SYNTHETIQUE } }), undefined, "a name is not a scope: it is never shown");
  // A scope `team.<lower-case name>` is of the contract's reader's shape, but it is not an opaque identifier: it is never shown, in any
  // language, and the line falls back on the level of the scope.
  for (const nom of ["equipetemoin", "equipe-temoin_zeta", "0123456789abcde", "0123456789abcdef0", "0123456789ABCDEF"]) {
    const sansIdentifiant = { ...f, method: { ...f.method, scope: { level: "team" as const, id: `team.${nom}` } } };
    assert.equal(libelleEquipe(sansIdentifiant.method), undefined, nom);
    for (const langue of ["en", "fr"] as const) {
      const rendu = fiche(sansIdentifiant, { methodeOuverte: false }, langue);
      assert.ok(!rendu.includes(nom), `${nom} ${langue}`);
      assert.ok(texte(rendu).includes(catalogues[langue]["fiche.scope.team"]), `${nom} ${langue}`);
    }
  }
  const html = fiche(f);
  assert.equal(texte(html).split(IDENTIFIANT_OPAQUE).length - 1, 1, "the identifier is shown once");
  assert.doesNotMatch(html, new RegExp(EQUIPE_SYNTHETIQUE, "i"));
  assert.doesNotMatch(html, /<select|<option/, "no team selector");
  const debut = f.method.period.quarters[0];
  const fin = f.method.period.quarters[f.method.period.quarters.length - 1];
  const attendu = en["conviction.context"]
    .replace("{from}", `Q${debut.quarter} ${debut.year}`)
    .replace("{to}", `Q${fin.quarter} ${fin.year}`)
    .replace("{date}", "Oct 5, 2026");
  // Q2 (a), R-20261101-126: "Team {team}", the identifier coming from `libelleEquipe` only.
  assert.ok(texte(html).includes(attendu.replace("{scope}", en["conviction.scope.team"].replace("{team}", IDENTIFIANT_OPAQUE))), attendu);
  assert.ok(texte(fiche(f, {}, "fr")).includes(fr["conviction.scope.team"].replace("{team}", IDENTIFIANT_OPAQUE)));
  // R-20261104-62 Q1 (a), R-20261104-33, N2 (a). Setting off: the dashboard answer in memory is the one the service layer serves, with no `team`
  // in its series; the page shows the identifier only, as strictly as before, and the witness name appears nowhere.
  const page = await application(f);
  assert.doesNotMatch(page, new RegExp(EQUIPE_SYNTHETIQUE, "i"));
  assert.ok(page.includes(IDENTIFIANT_OPAQUE));
  assert.equal(texte(page).split(IDENTIFIANT_OPAQUE).length - 1, 1, "the identifier is shown once");
  // Setting on: the dashboard answer in memory carries the witness name for the identifier; the page shows it once, and the identifier no more.
  const avecNom = await application(f, {}, "en", true);
  assert.equal(texte(avecNom).split(EQUIPE_SYNTHETIQUE).length - 1, 1, "the name is shown once");
  assert.ok(!texte(avecNom).includes(IDENTIFIANT_OPAQUE), "the identifier is not shown beside the name");
  assert.ok(texte(avecNom).includes(en["conviction.scope.team"].replace("{team}", EQUIPE_SYNTHETIQUE)));
  // The function alone: the name from the answer in memory by identifier; no answer, or an identifier it does not hold: the identifier.
  const tableauNomme = reponseTableau("synthetic", true);
  assert.equal(libelleEquipe(f.method, tableauNomme), EQUIPE_SYNTHETIQUE);
  assert.equal(libelleEquipe(f.method, reponseTableau("synthetic")), IDENTIFIANT_OPAQUE);
  assert.equal(libelleEquipe(f.method, { teams: [{ team: "Autre Equipe Zeta", teamId: "0123456789abcdef" }] }), IDENTIFIANT_OPAQUE);
  assert.equal(libelleEquipe(f.method, { teams: [{ team: "", teamId: IDENTIFIANT_OPAQUE }] }), IDENTIFIANT_OPAQUE, "an empty name is never a label");
  // The sources of the page, of the component and of the shell never read the teams of the dashboard answer: `.teams` is forbidden outside
  // `libelleEquipe` (its own file), and `teamId` is admitted only inside a call to it.
  for (const fichier of ["src/pages/PageConviction.ts", "src/composants/FicheConviction.ts", "src/Application.ts", "src/composants/BarreFiltres.ts"]) {
    const source = readFileSync(`${FRONT}${fichier}`, "utf8");
    assert.doesNotMatch(source, /\.teams\b/, fichier);
    assert.doesNotMatch(source.replace(/libelleEquipe\([^)]*\)/g, ""), /\bteamId\b/, fichier);
  }
  assert.match(readFileSync(`${FRONT}src/composants/libelleEquipe.ts`, "utf8"), /\.teams\b/);
});

// A sheet opened with no dashboard answer in memory shows the opaque identifier, never an empty label nor an error (N2 (a), R-20261104-62).
test("a sheet opened with no dashboard answer in memory shows the opaque identifier", () => {
  const f = ficheH1("confirmed", { jeu: "synthetic" });
  const html = fiche(f);
  assert.equal(texte(html).split(IDENTIFIANT_OPAQUE).length - 1, 1);
  assert.ok(texte(html).includes(en["conviction.scope.team"].replace("{team}", IDENTIFIANT_OPAQUE)));
  assert.doesNotMatch(html, /class="page-erreur"|role="alert"/);
});

// The same, through the application and the address of the sheet: only the sheet answer is in the query cache, no dashboard answer (R4 of the
// review of 2026-11-04, delta front scenario "opened by its address").
test("a sheet opened by its address with no dashboard answer in memory shows the opaque identifier", async () => {
  const f = ficheH1("confirmed", { jeu: "synthetic" });
  const lireFiche = async () => f;
  const lireTableau = async () => reponseTableau("synthetic", true);
  const client = nouveauClient();
  await client.prefetchQuery(optionsFiche(lireFiche, f.id));
  const source = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  const html = propre(
    rendre(
      h(QueryClientProvider, { client }, h(Application, { tableau: source, lireFiche, ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h1", id: f.id } })),
      "en",
    ),
  );
  assert.equal(texte(html).split(IDENTIFIANT_OPAQUE).length - 1, 1, "the identifier is shown once");
  assert.ok(texte(html).includes(en["conviction.scope.team"].replace("{team}", IDENTIFIANT_OPAQUE)));
  assert.ok(!html.includes(EQUIPE_SYNTHETIQUE), "no name");
  assert.doesNotMatch(html, /class="page-erreur"|role="alert"/);
});

// ---- the dashboard answer of the tests, the application, the address --------------------------------------------------------------

// The answer as the service layer serves it (`servirTableau`): with the setting off (`avecNom` false, the default) the series carry no `team`;
// with it on they carry the witness name (R-20261104-36 N1 (a), R-20261104-62).
function reponseTableau(jeu: "synthetic" | "real", avecNom = false): ReponseLeadCycle | ReponseLeadCycleReduite {
  const val = (v: number) => ({ state: "value" as const, value: v });
  const ligne = (debut: string | null) => ({
    team: EQUIPE_SYNTHETIQUE,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    items_lt: val(30),
    items_ct: val(30),
    lead_median_days: val(40),
    cycle_median_days: val(10),
  });
  const debuts = ["2026-01-01", "2026-04-01", "2026-07-01"];      // the three closed quarters (R-20261114-49)
  const vue = { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows: [...debuts.map(ligne), ligne(null)], sources: ["flow"] };
  const base = tableauLeadCycle(vue as never, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe);
  return servirTableau(base, { jeu, comptesAutorises: false, afficherNoms: avecNom });
}

function nouveauClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
}

type PropsApplication = Partial<Parameters<typeof Application>[0]>;

// The application on the conviction screen of the given sheet, the dashboard answer and the sheet answer being in the query cache.
async function application(f: ReponseFiche, props: PropsApplication = {}, langue: Langue = "en", avecNom = false): Promise<string> {
  const reponse = reponseTableau(f.dataset === "real" ? "real" : "synthetic", avecNom);
  const lireTableau = async () => reponse;
  const lireFiche = async () => f;
  const client = nouveauClient();
  await client.prefetchQuery(optionsLeadCycle(lireTableau));
  await client.prefetchQuery(optionsFiche(lireFiche, f.id));
  const source = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  return propre(
    rendre(
      h(
        QueryClientProvider,
        { client },
        h(Application, {
          tableau: source,
          lireFiche,
          // R-20261103-25 (1) : plus de liste injectée ; l'application prend son défaut, la liste du contrat filtrée par le jeu.
          ecranInitial: "conviction",
          convictionInitiale: { genre: "lead_cycle_h1", id: f.id },
          langueInitiale: langue,
          ...props,
        }),
      ),
      langue,
    ),
  );
}

test("the demonstration screen: the published sheet on real data in its reduced form, opened by its address, under one real-data banner", async () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const html = await application(f);
  assert.equal((html.match(/class="banniere"/g) ?? []).length, 1);
  assert.match(html, /data-jeu="real"/);
  assert.doesNotMatch(html, /data-jeu="synthetic"/);
  assert.ok(texte(html).includes(texte(en["banner.realReduced"])));
  assert.match(html, /<h1[^>]*>“Most of the lead time is spent waiting, not working\.”<\/h1>/);
  assert.ok(texte(html).includes(en["fiche.status.publishedLine"].replace("{date}", "November 2, 2026").replace("{number}", String(f.method.version))));
  // Q6 (a): the reminder that the verdict is computed stands beside the badge.
  assert.ok(texte(html).includes(en["fiche.verdict.computed"]));
  assert.ok(html.indexOf('class="badge') < html.indexOf('class="verdict-calcule"') && html.indexOf('class="verdict-calcule"') < html.indexOf('class="statut-fiche'));
  // Q7 (a): no link to the detail by quarter on the reduced form.
  assert.doesNotMatch(html, /See the detail by quarter/);
  assert.match(html, /class="badge[^"]*" data-etat="confirmed"/);
  // The page is the sheet of the address: the draft memory is not asked for.
  assert.equal((html.match(/class="gabarit-fiche"/g) ?? []).length, 1);
});

test("the reduced sheet shows the median and P85 ratios and the two thresholds as ratios, and the two medians of the pooled year as key figures", () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const html = fiche(f);
  // The ratios carry the "×" of the catalogue (the same as the thresholds), not a bare number (écart #8).
  const rapportEn = (valeur: string): string => en["conviction.bar.ratio"].replace("{ratio, number}", valeur);
  assert.ok(html.includes(`data-state="value">${rapportEn("4")}</span>`));
  assert.match(html, /data-rapport="median"[\s\S]*?<dd><span[^>]*data-state="value">Lead time over cycle time: 4×<\/span>/);
  assert.match(html, /data-rapport="p85"[\s\S]*?<dd><span[^>]*data-state="value">Lead time over cycle time: 4×<\/span>/);
  assert.ok(texte(html).includes(en["fiche.measure.median_ratio"]) && texte(html).includes(en["fiche.measure.p85_ratio"]));
  assert.ok(texte(html).includes(en["conviction.marker.refutation"].replace("{ratio, number}", "1.5")));
  assert.ok(texte(html).includes(en["conviction.marker.confirmation"].replace("{ratio, number}", "3")));
  assert.match(html, /data-chiffre="lead_median"[\s\S]*?data-state="value">40 d<\/span>/);
  assert.match(html, /data-chiffre="cycle_median"[\s\S]*?data-state="value">10 d<\/span>/);
  // The labels are the measures' own; the period is said once, by the line "Pooled year" (écart #6).
  assert.match(html, /data-chiffre="lead_median"[\s\S]*?<p class="chiffre-libelle">Median lead time<\/p>/);
  assert.match(html, /data-chiffre="cycle_median"[\s\S]*?<p class="chiffre-libelle">Median cycle time<\/p>/);
  assert.equal((texte(html).match(new RegExp(en["tableau.quarter.pooledYear"], "g")) ?? []).length, 1);
  assert.doesNotMatch(texte(html), /Median lead time, pooled year|Median cycle time, pooled year/);
  assert.ok(texte(html).includes(en["fiche.mention.cycle_time_includes_ready_queue"]), "the cycle time mention is next to the figures");
  // The ratios and the thresholds come from the answer: the refuted case shows its own.
  const refutee = fiche(ficheH1("refuted", { jeu: "real" }));
  assert.match(refutee, /data-rapport="median"[\s\S]*?data-state="value">Lead time over cycle time: 1\.2×<\/span>/);
  const francais = fiche(f, {}, "fr");
  assert.ok(texte(francais).includes(fr["conviction.marker.confirmation"].replace("{ratio, number}", "3")));
});

// R-20261102-71 (1): the markers are read from `waitShares.markers` (field `ratio`); without `waitShares`, no marker (fallback of D4).
test("without waitShares the sheet shows no threshold marker, and the other figures stay", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const { waitShares, ...sans } = ficheH1("confirmed", { jeu });
    assert.ok(waitShares !== undefined, `the helper serves waitShares (${jeu})`);
    const html = fiche(sans as ReponseFiche);
    assert.doesNotMatch(html, /data-repere=|class="reperes"/, jeu);
    assert.doesNotMatch(texte(html), new RegExp(en["conviction.marker.refutation"].replace("{ratio, number}", "1.5").replace(/[.*+?^()[\]\\|]/g, "\\$&")), jeu);
    assert.match(html, /data-rapport="median"/, jeu);
  }
});

test("the reduced sheet shows no count, no waiting in days, no composition and no statistic the reduced form does not carry", () => {
  for (const cas of CAS_H1) {
    const html = fiche(ficheH1(cas, { jeu: "real" }), { methodeOuverte: true });
    assert.doesNotMatch(html, /7919|7,919|7 919/, cas);
    assert.doesNotMatch(texte(html), /days of waiting|Composition of the median lead time/, cas);
    // R-20261103-3 : en phase B (tâche 6.3, R-20261101-20 et -33), <svg et les barres sont permis ; le graphique de composition et toute
    // attente en jours restent interdits, et les deux barres (médiane et P85) doivent être présentes.
    assert.doesNotMatch(html, /data-chiffre="(wait|work)"|<canvas|class="composition|ligne-axe|cache-visuel|data-forme="ligne"/, cas);
    assert.match(html, /data-barre="median"/, cas);
    assert.match(html, /data-barre="p85"/, cas);
    assert.ok(!texte(html).includes(en["conviction.footer.waitDefinition"]), cas);
  }
});

test("the method face is one click away, closed at first, with the reduced form and the coverage state, and without the synthetic notice", () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const fermee = fiche(f);
  assert.doesNotMatch(fermee, /fiche-methode/);
  assert.match(fermee, /<button type="button" class="fiche-bouton" aria-expanded="false">Show the method<\/button>/);
  const ouverte = fiche(f, { methodeOuverte: true });
  assert.match(ouverte, /aria-expanded="true"/);
  assert.match(ouverte, /fiche-methode/);
  assert.ok(texte(ouverte).includes(en["fiche.limit.reduced_form"]));
  assert.match(ouverte, /data-etat-couverture="coverage_(sufficient|insufficient|masked)"/);
  assert.ok(texte(fiche(ficheH1("confirmed"), { methodeOuverte: true })).includes(en["fiche.method.title"]));
  assert.doesNotMatch(fiche(ficheH1("confirmed"), { methodeOuverte: true }), /fiche-jeu-synthetique/);
});

test("without the bars of lot 1b the page draws no bar and no composition chart, on either form, and every case still holds its verdict text", () => {
  for (const cas of CAS_H1) {
    for (const jeu of ["synthetic", "real"] as const) {
      // R-20261103-3 : waitShares retiré de la donnée d'entrée (précédent R-20261028-96) ; assertion inchangée (repli de D4).
      const { waitShares, ...sansParts } = ficheH1(cas, { jeu });
      assert.ok(waitShares !== undefined, "the helper serves waitShares");
      const html = fiche(sansParts as ReponseFiche);
      assert.doesNotMatch(html, /<svg(?![^>]*data-icone="lock")|role="img"|barre-parts|Composition of the median lead time/, `${cas} ${jeu}`);
      assert.match(html, /class="badge/, `${cas} ${jeu}`);
    }
  }
});

// ---- the page: which sheet, the empty state, a sheet of another kind, the existing route only --------------------------------------

async function pageDe(
  conviction: { genre: GraphiqueDeFiche; id?: string },
  lire: (id: string) => Promise<ReponseFiche>,
  props: Partial<Parameters<typeof PageConviction>[0]> = {},
  prechauffer = true,
): Promise<string> {
  const client = nouveauClient();
  const id = conviction.id ?? props.fichePrecedente?.(conviction.genre);
  // The answer is put in the query cache before the render, as the entry of the bundle would have read it; `prechauffer: false` leaves the cache
  // empty, so that a reader called by the page itself is counted.
  if (id !== undefined && prechauffer) await client.prefetchQuery(optionsFiche(lire, id));
  return propre(rendre(h(QueryClientProvider, { client }, h(PageConviction, { conviction, lire, ...props })), "en"));
}

test("without an identifier and without a remembered sheet the page shows the statement, the empty state and the link to the dashboard", async () => {
  let appels = 0;
  const lire = async () => {
    appels += 1;
    return ficheH1("confirmed");
  };
  const html = await pageDe({ genre: "lead_cycle_h1" }, lire);
  assert.ok(texte(html).includes(en["conviction.statement.lead_cycle_h1"]));
  assert.ok(texte(html).includes(en["conviction.empty"]));
  assert.match(html, /<a class="lien" href="#\/tableau">Dashboard<\/a>/);
  assert.doesNotMatch(html, /class="badge|data-etat-fiche/);
  assert.equal(appels, 0);
  const sansTableau = await pageDe({ genre: "lead_cycle_h1" }, lire, { avecTableau: false });
  assert.doesNotMatch(sansTableau, /<a /);
  // A page given no reader opens no sheet either.
  const sansLecteur = propre(rendre(h(QueryClientProvider, { client: nouveauClient() }, h(PageConviction, { conviction: { genre: "lead_cycle_h1", id: "fiche-h1-1" } })), "en"));
  assert.ok(texte(sansLecteur).includes(en["conviction.empty"]));
});

test("the remembered sheet is used only when the address holds no identifier, and the address wins", async () => {
  const f = ficheH1("confirmed");
  const lue: string[] = [];
  const lire = async (id: string) => {
    lue.push(id);
    return { ...f, id };
  };
  const memoire = (): string => "fiche-memorisee";
  const sans = await pageDe({ genre: "lead_cycle_h1" }, lire, { fichePrecedente: memoire });
  assert.match(sans, /class="badge/);
  assert.deepEqual(lue, ["fiche-memorisee"]);
  lue.length = 0;
  const avec = await pageDe({ genre: "lead_cycle_h1", id: "fiche-adresse" }, lire, { fichePrecedente: memoire });
  assert.match(avec, /class="badge/);
  assert.deepEqual(lue, ["fiche-adresse"]);
});

test("a sheet of another hypothesis is not shown, and the kind of hypothesis 5 shows no bar and reads its sheet by the existing route; the application, not the page, reads nothing on the real dataset", async () => {
  const autre = { ...ficheH1("confirmed"), method: { ...ficheH1("confirmed").method, hypothesis: "h5" } } as ReponseFiche;
  const refusee = await pageDe({ genre: "lead_cycle_h1", id: autre.id }, async () => autre);
  assert.ok(texte(refusee).includes(en["conviction.empty"]));
  assert.doesNotMatch(refusee, /class="badge|data-etat-fiche|Invented effect/);
  // R-20261103-14 (Q1 (a)): this assertion, which gave hypothesis 5 the empty state and zero calls before lot 3c, now says: the kind reads its
  // sheet through the existing route (one GET, nothing written: the call counted here is the one of the test's own preload, `prechauffer`, not of
  // the page) and shows no bar and no empty state. PageConviction ignores the dataset: on the real dataset (below) it is the application that
  // filters, makes no call and gives the home. A sheet of hypothesis 1 under the address of hypothesis 5 is still refused.
  const h5Sheet = ficheH5("confirmed");
  const appels: string[] = [];
  const faux = async (url: string | URL | Request, options?: RequestInit): Promise<Response> => {
    appels.push(`${options?.method ?? "GET"} ${String(url)}`);
    return new Response(JSON.stringify(h5Sheet), { status: 200, headers: { "content-type": "application/json" } });
  };
  const h5 = await pageDe({ genre: "lead_cycle_h5", id: h5Sheet.id }, (id) => lireFicheHttp(id, faux as typeof fetch));
  assert.ok(texte(h5).includes(en["conviction.statement.lead_cycle_h5"]));
  assert.ok(!texte(h5).includes(en["conviction.empty"]));
  assert.match(h5, /class="badge/);
  assert.doesNotMatch(h5, /<svg(?![^>]*data-icone=)|barre-|data-barre|data-rapport/);
  assert.deepEqual(appels, [`GET /api/sheets/${h5Sheet.id}`]);
  const mauvaiseHypothese = await pageDe({ genre: "lead_cycle_h5", id: "fiche-h1-1" }, async () => ficheH1("confirmed"));
  assert.ok(texte(mauvaiseHypothese).includes(en["conviction.empty"]));
  assert.doesNotMatch(mauvaiseHypothese, /class="badge|data-etat-fiche/);
  // The real dataset: the kind is not served, the application gives the home and the reader is never called.
  let appelsReel = 0;
  const reponseReelle = reponseTableau("real");
  const lireTableau = async () => reponseReelle;
  const client = nouveauClient();
  await client.prefetchQuery(optionsLeadCycle(lireTableau));
  const source = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  const reel = propre(
    rendre(
      h(
        QueryClientProvider,
        { client },
        h(Application, {
          tableau: source,
          lireFiche: async () => {
            appelsReel += 1;
            return ficheH5("confirmed", { jeu: "real" });
          },
          ecranInitial: "conviction",
          convictionInitiale: { genre: "lead_cycle_h5", id: "fiche-h5-1" },
        }),
      ),
      "en",
    ),
  );
  assert.match(reel, /What the data say about our convictions/);
  assert.ok(!texte(reel).includes(en["conviction.statement.lead_cycle_h5"]));
  assert.equal(appelsReel, 0);
});

test("a refused or failed reading shows the translated message of its code, never the code", async () => {
  const refus = await pageDe({ genre: "lead_cycle_h1", id: "fiche-inconnue" }, async () => {
    throw new ErreurApi("UNKNOWN_SHEET");
  });
  // A-98 (author's decision of 2026-11-08, question 22): an unknown sheet shows the explained empty state, not an alert.
  assert.ok(texte(refus).includes(en["conviction.empty"]));
  assert.doesNotMatch(refus, /role="alert"/);
  assert.doesNotMatch(texte(refus), /UNKNOWN_SHEET/);
  const panne = await pageDe({ genre: "lead_cycle_h1", id: "fiche-x" }, async () => {
    throw new Error("réseau");
  });
  assert.ok(texte(panne).includes(en["error.INTERNAL"]));
});

test("the page calls the existing route of the sheet and no other: one GET of the sheet, nothing written", async () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const appels: string[] = [];
  const faux = async (url: string | URL | Request, options?: RequestInit): Promise<Response> => {
    appels.push(`${options?.method ?? "GET"} ${String(url)}`);
    return new Response(JSON.stringify(f), { status: 200, headers: { "content-type": "application/json" } });
  };
  const html = await pageDe({ genre: "lead_cycle_h1", id: f.id }, (id) => lireFicheHttp(id, faux as typeof fetch));
  assert.match(html, /class="badge/);
  assert.deepEqual(appels, [`GET /api/sheets/${f.id}`]);
});

// ---- the last sheet kept by the browser (D11, R-20261101-125 Q258 (a)) -------------------------------------------------------------

test("the conviction page opened without an identifier shows the last sheet kept by the browser, read through the dashboard page's one access", async () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const stockage = { getItem: (cle: string) => (cle === CLE_DERNIERE_FICHE ? JSON.stringify({ fiches: { lead_cycle_h1: f.id } }) : null), setItem: () => undefined, removeItem: () => undefined };
  const globale = globalThis as unknown as { window?: unknown };
  const avant = globale.window;
  globale.window = { location: { hash: "" }, localStorage: stockage };
  try {
    const html = await application(f, { convictionInitiale: { genre: "lead_cycle_h1" } });
    assert.match(html, /class="badge[^"]*" data-etat="confirmed"/);
    assert.match(html, /data-etat-fiche="published"/);
    assert.doesNotMatch(texte(html), new RegExp(en["conviction.empty"].slice(0, 20)));
  } finally {
    if (avant === undefined) delete globale.window;
    else globale.window = avant;
  }
  // Without anything kept, the same address gives the empty state.
  const vide = await application(f, { convictionInitiale: { genre: "lead_cycle_h1" } });
  assert.ok(texte(vide).includes(en["conviction.empty"]));
});

// ---- the address (R-20261101-121 Q239, R-20261101-63, Q189) ---------------------------------------------------------------------------

test("the address of the page is the kind and the opaque identifier, nothing else: no name, no scope, no parameter", async () => {
  assert.equal(adresseConviction("lead_cycle_h1", "fiche-h1-1"), "#/conviction/lead_cycle_h1/fiche-h1-1");
  assert.deepEqual(convictionDuHash("#/conviction/lead_cycle_h1/fiche-h1-1"), { genre: "lead_cycle_h1", id: "fiche-h1-1" });
  // A number, as the database gives them, is an identifier of the pattern; a name with a space is not.
  assert.deepEqual(convictionDuHash("#/conviction/lead_cycle_h1/42"), { genre: "lead_cycle_h1", id: "42" });
  assert.equal(convictionDuHash(`#/conviction/lead_cycle_h1/${EQUIPE_SYNTHETIQUE}`), undefined);
  const html = await application(ficheH1("confirmed", { jeu: "real" }));
  const adresses = [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
  assert.ok(adresses.every((a) => !a.includes("?") && !a.includes(EQUIPE_SYNTHETIQUE)), adresses.join(" "));
  for (const fichier of ["src/pages/PageConviction.ts", "src/composants/FicheConviction.ts"]) {
    assert.doesNotMatch(readFileSync(`${FRONT}${fichier}`, "utf8"), /location|history\./, `${fichier} writes no address`);
  }
});

// ---- the navigation (R-20261101-42, R-20261101-67) -------------------------------------------------------------------------------------

const DANS_NAV = /href="#\/conviction\/([a-z0-9_]+)"/g;

test("the hypothesis 1 entry has aria-current on its page and no state marker; the hypothesis 5 entry is visible on the synthetic dataset and absent on the real one", async () => {
  // R-20261103-14 (Q1 (a)): this assertion, which said the hypothesis 5 entry was absent on every dataset before lot 3c, now says it is visible
  // on the synthetic dataset and absent on the real one, with the shipped list; no state marker either way (R-20261101-42).
  for (const jeu of ["synthetic", "real"] as const) {
    const html = await application(ficheH1("confirmed", { jeu }));
    const nav = /<nav[\s\S]*?<\/nav>/.exec(html)?.[0] ?? "";
    assert.deepEqual([...nav.matchAll(DANS_NAV)].map((m) => m[1]), jeu === "synthetic" ? ["lead_cycle_h5", "lead_cycle_h1"] : ["lead_cycle_h1"], jeu);
    assert.match(nav, /<a href="#\/conviction\/lead_cycle_h1" class="nav-entree nav-entree-courante" aria-current="page">/);
    assert.doesNotMatch(nav, /nav-pastille|data-etat|role="img"|badge/);
    if (jeu === "synthetic") assert.match(html, /href="#\/conviction\/lead_cycle_h5"/);
    else assert.doesNotMatch(html, /href="#\/conviction\/lead_cycle_h5"/);
  }
});

test("the banner of the conviction screen follows the dataset code of the sheet answer: one banner, the code of the sheet", async () => {
  const synthetique = await application(ficheH1("confirmed"));
  assert.equal((synthetique.match(/class="banniere"/g) ?? []).length, 1);
  assert.match(synthetique, /data-jeu="synthetic"/);
  const reelle = await application(ficheH1("confirmed", { jeu: "real" }));
  assert.match(reelle, /data-jeu="real"/);
});

// ---- the catalogues (task 6.2, 6.5) -------------------------------------------------------------------------------------------------

// The keys the conviction page reads and D13 lists; each is in both catalogues.
const CLES_DE_LA_PAGE = [
  "conviction.overline",
  "conviction.statement.lead_cycle_h1",
  "conviction.context",
  "conviction.figure.wait",
  "conviction.figure.work",
  "conviction.finding.insufficient_sample",
  "conviction.finding.masked",
  "conviction.marker.refutation",
  "conviction.marker.confirmation",
  "conviction.notComparable",
  "conviction.chart.days",
  "conviction.bar.ratio",
  "conviction.scope.team",
  "conviction.explanations.intro",
  "fiche.status.publishedLine",
  "fiche.verdict.computed",
  "conviction.inset.managementQuestion",
  "conviction.inset.effect",
  "conviction.inset.cause",
  "conviction.footer.masking",
  "conviction.footer.waitDefinition",
  "conviction.footer.cycleScope",
  "conviction.empty",
  "conviction.detail",
  "tableau.quarter.pooledYear",
];

test("every key the conviction page reads is in both catalogues, and the wording of the pooled year is the author's", () => {
  for (const [langue, catalogue] of Object.entries(catalogues)) {
    for (const cle of CLES_DE_LA_PAGE) assert.ok(cle in catalogue, `texte de conviction absent : ${cle} (${langue})`);
  }
  assert.equal(en["tableau.quarter.pooledYear"], "Pooled year");
  assert.equal(fr["tableau.quarter.pooledYear"], "Année groupée");
});

test("no plain bar title and no per-state inset key is in a catalogue, nor the titles of the dropped insets", () => {
  for (const [langue, catalogue] of Object.entries(catalogues)) {
    assert.equal("conviction.bar.titlePlain" in catalogue, false, langue);
    const parEtat = Object.keys(catalogue).filter((cle) => /^conviction\.(lead_cycle_h[15]|h[15])\.[a-z_]+\.(meaning|notSaying|question)$/.test(cle));
    assert.deepEqual(parEtat, [], langue);
    for (const cle of ["conviction.meaning.title", "conviction.notSaying.title", "conviction.question.title"]) assert.equal(cle in catalogue, false, `${cle} ${langue}`);
  }
  assert.deepEqual([...GRAPHIQUES_DE_FICHE].sort(), ["lead_cycle_h1", "lead_cycle_h5"]);
});

test("the link to the detail by quarter is on the complete form only, and the footer holds the masking threshold, no line of the hypothesis served (R-20261109-08 Q2 (a)) and no threshold line (A-16 (a))", () => {
  const html = fiche(ficheH1("confirmed", { jeu: "real" }), { seuilMasquage: 5 });
  assert.doesNotMatch(html, /See the detail by quarter/, "the detail is in days: not on the reduced form (Q7 (a))");
  assert.match(fiche(ficheH1("confirmed"), { seuilMasquage: 5 }), new RegExp(`<a class="lien" href="#/tableau\\?team=${IDENTIFIANT_OPAQUE}&amp;from=2026-Q1&amp;to=2026-Q3">See the detail by quarter</a>`));
  assert.ok(texte(html).includes(en["conviction.footer.masking"].replace("{threshold}", "5")));
  const pied = /<footer[\s\S]*<\/footer>/.exec(html)?.[0] ?? "";
  assert.ok(texte(pied).includes(en["conviction.footer.masking"].replace("{threshold}", "5")), "the footer is the one that holds the masking line");
  assert.doesNotMatch(texte(pied), /Hypothesis served/);
  assert.ok(!texte(pied).includes(en["fiche.link.h1_first_half"]), "the number of the hypothesis stays on the method face");
  assert.equal("conviction.footer.hypothesis" in en, false);
  assert.doesNotMatch(html, /data-seuil=/, "the thresholds are on the method face only (A-16 (a))");
  assert.doesNotMatch(fiche(ficheH1("confirmed"), { avecTableau: false }), /See the detail by quarter/);
  assert.doesNotMatch(fiche(ficheH1("confirmed", { jeu: "real" })), /fewer than/, "no threshold known: the sentence is left out, not invented");
});

// ---- the render points of the comparison with the mockups, without a new key (écarts #5, #13, #14, #16, #19) ----------------------------

test("the key figures use the figure size token and the strong work and waiting colours of the declared pairs", () => {
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  assert.match(/\.chiffre-valeur\s*\{([^}]*)\}/.exec(css)?.[1] ?? "", /font-size:\s*var\(--font-size-figure\)/);
  assert.match(css, /\.chiffre\[data-chiffre="cycle_median"\] \.chiffre-valeur,\s*\.chiffre\[data-chiffre="work"\] \.chiffre-valeur\s*\{\s*color:\s*var\(--color-data-work-strong\)/);
  assert.match(css, /\.chiffre\[data-chiffre="wait"\] \.chiffre-valeur\s*\{\s*color:\s*var\(--color-data-wait-strong\)/);
});

test("each explanation state is a pill told apart by its class, and the attachment signal is the last row of the same grid", () => {
  const html = blocExplications(EXPLICATIONS_LIBRES, false, []);
  assert.match(html, /data-explication="unplanned_work"[^>]*><span class="explication-nom">[^<]*<\/span><span class="pastille pastille-ecartee">/);
  assert.match(html, /data-explication="capacity"[^>]*><span class="explication-nom">[^<]*<\/span><span class="pastille pastille-non-ecartee">/);
  assert.match(html, /data-explication="dependencies"[^>]*><span class="explication-nom">[^<]*<\/span><span class="pastille pastille-non-mesurable">/);
  const lignes = [...html.matchAll(/<li class="explication-ligne"/g)].length;
  assert.equal(lignes, EXPLICATIONS_LIBRES.length + 1, "the signal is a row of the grid");
  assert.ok(html.lastIndexOf('data-signal="not_raised"') > html.lastIndexOf('data-explication="dependencies"'));
  assert.ok(texte(html).includes(en["fiche.explanation.tasks_attachment"]));
  const inconnue = blocExplications([{ name: "x", state: "weird" }] as unknown as ExplicationFiche[], false, []);
  assert.match(inconnue, /pastille pastille-neutre/);
});

test("the mention of the current links goes with the dependencies when the answer carries the blocked share, and nowhere else", () => {
  const avec = blocExplications([{ name: "dependencies", state: "not_ruled_out", measure: { state: "value", value: 30 } }] as ExplicationFiche[], false, []);
  assert.ok(texte(avec).includes(en["fiche.mention.blocked_share_current_links"]));
  assert.doesNotMatch(texte(avec), /30/, "the measure itself is not shown");
  const sans = blocExplications([{ name: "dependencies", state: "not_ruled_out" }] as ExplicationFiche[], false, []);
  assert.ok(!texte(sans).includes(en["fiche.mention.blocked_share_current_links"]));
  const ailleurs = blocExplications([{ name: "capacity", state: "not_ruled_out", measure: { state: "value", value: 30 } }] as ExplicationFiche[], false, []);
  assert.ok(!texte(ailleurs).includes(en["fiche.mention.blocked_share_current_links"]));
});

test("a state ruled out is told apart from the neutral pill by an outline and a hidden mark, not by colour alone, and the heading levels run on", () => {
  const html = blocExplications(EXPLICATIONS_LIBRES, false, []);
  assert.match(html, /pastille pastille-ecartee"><span class="fiche-icone" data-icone="check" aria-hidden="true"><\/span>Ruled out</);
  assert.doesNotMatch(/pastille-non-ecartee">([^<]*<[^>]*>)?Not ruled out/.exec(html)?.[0] ?? "", /data-icone/);
  assert.doesNotMatch(/pastille-non-mesurable">[^]*?<\/span>/.exec(html)?.[0] ?? "", /data-icone/);
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  const regle = (classe: string): string => (new RegExp(`\\.${classe}\\s*\\{([^}]*)\\}`).exec(css)?.[1] ?? "").replace(/\s+/g, " ").trim();
  assert.notEqual(regle("pastille-ecartee"), regle("pastille-neutre"));
  assert.match(regle("pastille-ecartee"), /border-color:\s*var\(--color-text\)/);
  // The headings: the h1 of the statement, then the insets and the competing explanations, all h2; no h3 before the first h2 of the page.
  const page = fiche(ficheH1("confirmed"));
  assert.doesNotMatch(page, /<h3/);
  const niveaux = [...page.matchAll(/<h([1-6])/g)].map((m) => Number(m[1]));
  assert.deepEqual(niveaux, [1, 2, 2, 2, 2]);
});

test("the management question starts with a capital in the catalogue (A-14); the style rule on the first letter stays", () => {
  const html = fiche(ficheH1("confirmed"));
  assert.match(html, /<p class="encart-texte encart-question">Predictability<\/p>/);
  assert.match(readFileSync(`${FRONT}src/styles/styles.css`, "utf8"), /\.encart-question::first-letter\s*\{\s*text-transform:\s*uppercase/);
  assert.equal(en["fiche.question.predictability"], "Predictability");
});

test("the explanations have their introduction, the page has no finding sentence and no note on the P85 rule (R-20261101-126, Q4 (a), Q5 (a))", () => {
  for (const langue of ["en", "fr"] as const) {
    const html = blocExplications(EXPLICATIONS_LIBRES, false, [], langue);
    assert.ok(texte(html).includes(catalogues[langue]["conviction.explanations.intro"]), langue);
    assert.ok(html.indexOf('class="explications-titre"') < html.indexOf('class="explications-intro"') && html.indexOf('class="explications-intro"') < html.indexOf('class="explications-liste"'));
  }
  assert.equal(en["conviction.explanations.intro"], "What could explain the same effect. An explanation that is not ruled out stays open.");
  assert.equal(fr["conviction.explanations.intro"], "Ce qui pourrait expliquer le même effet. Une explication non écartée reste ouverte.");
  const cles = Object.keys(en).filter((cle) => cle.startsWith("conviction."));
  assert.deepEqual(cles.filter((cle) => /p85Rule|p85Note|caption\./.test(cle)), [], "no note on the P85 rule, no per-verdict finding sentence");
  const reduite = texte(fiche(ficheH1("confirmed", { jeu: "real" })));
  assert.doesNotMatch(reduite, /same direction as the median|exceed the upper threshold/);
});

// ---- one note per screen (R-20261101-129, Q268 (a)) --------------------------------------------------------------------------------

test("every screen holds exactly one role=note, the banner of the shell: the home, the dashboard (synthetic and real) and the conviction page", async () => {
  const notes = (html: string): number => (html.match(/role="note"/g) ?? []).length;
  for (const jeu of ["synthetic", "real"] as const) {
    const reponse = reponseTableau(jeu);
    const lireTableau = async () => reponse;
    const source = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
    for (const ecranInitial of ["squelette", "tableau"] as const) {
      const client = nouveauClient();
      await client.prefetchQuery(optionsLeadCycle(lireTableau));
      const html = propre(rendre(h(QueryClientProvider, { client }, h(Application, { tableau: source, ecranInitial })), "en"));
      assert.equal(notes(html), 1, `${ecranInitial} ${jeu}`);
      assert.match(html, new RegExp(`class="banniere" data-jeu="${jeu}"`));
      // The mention of the synthetic dataset is a line of that note, and of no other element.
      assert.equal(html.includes(en["fiche.syntheticNotice"]), jeu === "synthetic", `${ecranInitial} ${jeu}`);
      assert.doesNotMatch(html, /class="fiche-jeu-synthetique"/);
    }
    assert.equal(notes(await application(ficheH1("confirmed", { jeu }))), 1, `conviction ${jeu}`);
  }
});

test("a dashboard with a source of panels still holds one role=note: the notes of the panels are plain paragraphs, their text kept (R-20261101-129)", async () => {
  const reponse = reponseTableau("synthetic");
  const lireTableau = async () => reponse;
  const source = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  const client = nouveauClient();
  await client.prefetchQuery(optionsLeadCycle(lireTableau));
  const filtres = { team: IDENTIFIANT_OPAQUE, from: "2026-Q1", to: "2026-Q3" };
  assert.ok(panneauxAffiches(filtres).length > 0);
  for (const code of panneauxAffiches(filtres)) await client.prefetchQuery(optionsPanneau(code, filtres, SOURCE_PANNEAUX_SIMULEE.lire));
  const html = propre(
    rendre(h(QueryClientProvider, { client }, h(Application, { tableau: source, panneaux: SOURCE_PANNEAUX_SIMULEE, ecranInitial: "tableau", filtresInitiaux: filtres })), "en"),
  );
  assert.equal((html.match(/role="note"/g) ?? []).length, 1);
  // The text of the note of the panels is still there, in plain paragraphs.
  assert.match(html, /<p class="fiche-jeu-synthetique" data-jeu="synthetic">On the synthetic dataset, not on real data\.<\/p>/);
  // The product scope: the sentence that a team is needed is a plain paragraph too.
  const produit = propre(rendre(h(QueryClientProvider, { client: nouveauClient() }, h(SectionPanneaux, { lire: SOURCE_PANNEAUX_SIMULEE.lire, filtres: SANS_FILTRES })), "en"));
  assert.match(produit, /<p class="tableau-date" data-note="team-required">/);
  assert.ok(texte(produit).includes(en["tableau.panel.blocked-share.teamRequired"]));
  assert.doesNotMatch(produit, /role="note"/);
});

// ---- thresholds not set: the shell and the home stay, the dashboard says why in the catalogue's words (analysis of the e2e failure) ----

test("with the thresholds not set, the dashboard answers 409 THRESHOLDS_NOT_SET: the shell, the home and the link to the dashboard stay, and the message is the catalogue's", async () => {
  const lireTableau = async (): Promise<never> => {
    throw new ErreurApi("THRESHOLDS_NOT_SET");
  };
  const source = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  for (const ecranInitial of ["squelette", "tableau"] as const) {
    const client = nouveauClient();
    await client.prefetchQuery(optionsLeadCycle(lireTableau));
    const html = propre(rendre(h(QueryClientProvider, { client }, h(Application, { tableau: source, ecranInitial })), "en"));
    assert.match(html, /<nav[^>]*aria-label="Main navigation"/, ecranInitial);
    assert.match(html, /<a href="#\/tableau"[^>]*>Dashboard<\/a>/, ecranInitial);
    assert.doesNotMatch(html, /THRESHOLDS_NOT_SET/, ecranInitial);
  }
  // The error state of the dashboard is a translated sentence, not a code and not a table.
  const etat = propre(rendre(h(ContenuVue, { etat: { genre: "erreur", code: "THRESHOLDS_NOT_SET" } }), "en"));
  assert.ok(texte(etat).includes(en["error.THRESHOLDS_NOT_SET"]));
  assert.doesNotMatch(etat, /THRESHOLDS_NOT_SET|<table/);
  assert.ok(fr["error.THRESHOLDS_NOT_SET"] !== "" && fr["error.THRESHOLDS_NOT_SET"] !== "THRESHOLDS_NOT_SET");
});

test("the lock is a monochrome vector icon in the icon module, filled by the text colour, and the render holds no emoji, on either form (R-20261101-127)", () => {
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  assert.match(/\.fiche-icone-vecteur\s*\{([^}]*)\}/.exec(css)?.[1] ?? "", /fill:\s*currentColor/);
  assert.doesNotMatch(css, /1F512/i, "the glyph of the lock is gone from the stylesheet");
  for (const cas of CAS_H1) {
    for (const jeu of ["synthetic", "real"] as const) {
      for (const langue of ["en", "fr"] as const) {
        const html = fiche(ficheH1(cas, { jeu }), { methodeOuverte: true }, langue);
        assert.doesNotMatch(html, /\p{Extended_Pictographic}/u, `html ${cas} ${jeu} ${langue}`);
        assert.doesNotMatch(texte(html), /\p{Extended_Pictographic}/u, `texte ${cas} ${jeu} ${langue}`);
        assert.match(html, /<svg class="fiche-icone fiche-icone-vecteur" data-icone="lock" aria-hidden="true"/, `${cas} ${jeu} ${langue}`);
        assert.doesNotMatch(html, /<svg[^>]*(style=|fill=|stroke=)/, "the colour comes from the stylesheet, not from an attribute");
      }
    }
  }
  // A draft or a reviewed sheet has no lock.
  assert.doesNotMatch(fiche(ficheH1("confirmed", { etat: "draft" })), /data-icone="lock"/);
});

test("the three new labels are the author's, in both catalogues, with the author's wording", () => {
  assert.equal(en["conviction.scope.team"], "Team {team}");
  assert.equal(fr["conviction.scope.team"], "Équipe {team}");
  assert.equal(en["fiche.status.publishedLine"], "Published on {date} · version {number} · frozen");
  assert.equal(fr["fiche.status.publishedLine"], "Publiée le {date} · version {number} · figée");
});
