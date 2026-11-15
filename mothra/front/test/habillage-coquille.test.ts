// Lot 3a of mothra-demo-habillage (tasks 5.0 to 5.4 and 5.7, 5.8): the components of the shell, the home and the empty state in each of
// their states, the three templates, the shell with the banner by dataset code and the side navigation, the browser memory, the home. For
// the demonstration the home and the navigation show statements and links only: no verdict, no state marker, nothing read from the browser
// memory (Q158 (b), R-20261101-42). The parts bar, the sheet status, the competing explanations and the sheet page are lot 3b; the stability
// table is lot 3c; the disabled choice is lot 3d.
// Practice R-20261031-61: every answer of the dashboard that a test hands to the application is produced by `tableauLeadCycle` of the
// contract on synthetic view rows (and by `reduceToStatistics` for the real form), never written by hand. The list of the convictions whose
// page is shipped (`CONVICTIONS_LIVREES`) is removed (R-20261103-24 Q4 (b)): the served kinds are the contract's list filtered by the dataset, and the tests that exercise the filters give their own list.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";

import { reduceToStatistics, tableauLeadCycle } from "@mothra/contract";
import type { ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { Application, convictionsServies, ecranDuHash, jeuDeDonnees } from "../src/Application.ts";
import { convictionDuHash } from "../src/api/adresse.ts";
import { CLE_DERNIERE_FICHE, ecrireDerniereFiche, lireDerniereFiche } from "../src/api/derniereFiche.ts";
import type { StockageIdentifiant } from "../src/api/identifiant.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import { BadgeVerdict, ETATS_BADGE, PRESENTATION_BADGE } from "../src/composants/BadgeVerdict.ts";
import { Banniere, CLES_BANNIERE } from "../src/composants/Banniere.ts";
import { CarteConviction } from "../src/composants/CarteConviction.ts";
import { EtatVide } from "../src/composants/EtatVide.ts";
import { NavigationLaterale } from "../src/composants/NavigationLaterale.ts";
import { CLES_CONVICTION } from "../src/convictions.ts";
import { Coquille } from "../src/gabarits/Coquille.ts";
import { GabaritFiche } from "../src/gabarits/GabaritFiche.ts";
import { GabaritIndicateurs } from "../src/gabarits/GabaritIndicateurs.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { ContenuTableau, ouvrirBrouillon } from "../src/pages/PageTableau.ts";
import { rendre, texte } from "./rendu.ts";
import { sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const LANGUES = ["en", "fr"] as const;
const DEUX_CONVICTIONS: readonly GraphiqueDeFiche[] = ["lead_cycle_h1", "lead_cycle_h5"];
// The order of the navigation and of the cards is the contract's (no order is written in a component, spec "side navigation"): the test reads it there.
const ORDRE_DU_CONTRAT: readonly GraphiqueDeFiche[] = [...GRAPHIQUES_DE_FICHE];

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

// A browser storage of the tests: it holds the one value of the memory key and counts what the code asks of it.
interface MemoireDeTest extends StockageIdentifiant {
  valeur: string | undefined;
  lectures: number;
  ecritures: number;
}

function memoire(initial?: string): MemoireDeTest {
  const m: MemoireDeTest = {
    valeur: initial,
    lectures: 0,
    ecritures: 0,
    getItem(cle: string): string | null {
      m.lectures += 1;
      return cle === CLE_DERNIERE_FICHE ? (m.valeur ?? null) : null;
    },
    setItem(cle: string, v: string): void {
      m.ecritures += 1;
      if (cle === CLE_DERNIERE_FICHE) m.valeur = v;
    },
    removeItem(cle: string): void {
      if (cle === CLE_DERNIERE_FICHE) m.valeur = undefined;
    },
  };
  return m;
}

// ---- the logo and the displayed name come from one point (task 5.0) --------------------------------------------------------------

export function horsPointUnique(fichiers: ReadonlyArray<{ nom: string; contenu: string }>): string[] {
  const trouves: string[] = [];
  for (const f of fichiers) {
    if (f.nom === "src/marque.ts") continue;
    f.contenu.split("\n").forEach((ligne, i) => {
      const code = ligne.trimStart();
      if (code.startsWith("//")) return;
      if (ligne.includes("/logos/") || ligne.includes('"app.title"')) trouves.push(`logo ou nom hors du point unique : ${f.nom}:${i + 1}`);
    });
  }
  return trouves;
}

test("the checker names the file and the line of a logo or of the displayed name written outside the single point", () => {
  assert.deepEqual(horsPointUnique([{ nom: "src/a.ts", contenu: 'const a = 1;\nconst l = "/logos/mothra-logo-clair.svg";' }]), ["logo ou nom hors du point unique : src/a.ts:2"]);
  assert.deepEqual(horsPointUnique([{ nom: "src/a.ts", contenu: 'h("p", { id: "app.title" });' }]), ["logo ou nom hors du point unique : src/a.ts:1"]);
  assert.deepEqual(horsPointUnique([{ nom: "src/marque.ts", contenu: 'export const L = "/logos/x.svg";' }]), []);
});

test("only src/marque.ts names a logo file or the catalogue key of the displayed name", () => {
  assert.deepEqual(horsPointUnique(sources(FRONT, "src", [".ts", ".tsx"])), []);
});

// ---- the texts of the convictions come from the catalogues (task 5.2) ------------------------------------------------------------

test("every conviction kind of the contract list has its statement, navigation name and theme in both catalogues", () => {
  for (const genre of GRAPHIQUES_DE_FICHE) {
    for (const [langue, catalogue] of Object.entries(catalogues)) {
      for (const cle of Object.values(CLES_CONVICTION[genre])) {
        assert.ok(cle in catalogue, `conviction sans énoncé : ${genre} (${langue}, ${cle})`);
      }
    }
  }
  assert.deepEqual(Object.keys(CLES_CONVICTION).sort(), [...GRAPHIQUES_DE_FICHE].sort());
});

test("the French badges agree with the feminine conviction, and the banners are the labels of the design", () => {
  assert.equal(catalogues.en["conviction.badge.confirmed"], "Confirmed by the data");
  assert.equal(catalogues.fr["conviction.badge.confirmed"], "Confirmée par les données");
  assert.equal(catalogues.fr["conviction.badge.masked"], "Masquée");
  assert.equal(catalogues.en["banner.synthetic"], "<b>Synthetic data.</b> These figures are not real.");
  assert.equal(catalogues.fr["banner.synthetic"], "<b>Données synthétiques.</b> Ces chiffres ne sont pas réels.");
  assert.equal(catalogues.en["banner.realReduced"], "<b>Real data, reduced form.</b> Statistics only, no counts.");
  assert.equal(catalogues.fr["banner.realReduced"], "<b>Données réelles, forme réduite.</b> Des statistiques seulement, aucun effectif.");
  assert.equal("home.otherTeam" in catalogues.en, false, "no other-team sentence for the demonstration (Q158 (b))");
});

// ---- the components in each state, in both languages (task 5.0) ------------------------------------------------------------------

test("the verdict badge draws each of its states with its label, icon and outline, in both languages, and not the states of an unpublished sheet", () => {
  // The five display states of the contract and the fallback of an unknown verdict; "in progress" and "not tested" are not drawn (D8, D17).
  assert.deepEqual([...ETATS_BADGE].sort(), ["confirmed", "insufficient_sample", "masked", "not_settled", "refuted", "unknown"]);
  for (const etat of ETATS_BADGE) {
    for (const langue of LANGUES) {
      const html = propre(rendre(h(BadgeVerdict, { etat }), langue));
      assert.match(html, new RegExp(`data-etat="${etat}"`), etat);
      assert.match(html, /data-contour="(solid|dashed|dotted|double)"/, etat);
      assert.ok(texte(html).includes(catalogues[langue][PRESENTATION_BADGE[etat].cle]), `${etat} ${langue}`);
      assert.doesNotMatch(html, /style=/);
    }
  }
});

test("refuted is drawn like confirmed, in its own violet class and with the cross icon, never in the error look", () => {
  const html = rendre(h(BadgeVerdict, { etat: "refuted" }), "en");
  assert.match(html, /badge-refutee/);
  assert.match(html, /data-icone="cross"/);
  assert.match(html, /data-contour="solid"/);
  assert.doesNotMatch(html, /page-erreur|state-error/);
  assert.match(rendre(h(BadgeVerdict, { etat: "insufficient_sample" }), "en"), /data-contour="dotted"/);
  assert.match(rendre(h(BadgeVerdict, { etat: "masked" }), "en"), /data-contour="dashed"/);
  assert.match(rendre(h(BadgeVerdict, { etat: "unknown" }), "en"), /data-contour="dotted"/);
  assert.doesNotMatch(readFileSync(`${FRONT}src/styles/styles.css`, "utf8"), /badge-en-cours|badge-non-testee/);
});

test("the banner is a note that carries the label of its dataset code, in both languages", () => {
  assert.deepEqual(CLES_BANNIERE, { synthetic: "banner.synthetic", real: "banner.realReduced" });
  for (const langue of LANGUES) {
    for (const jeu of ["synthetic", "real"] as const) {
      const html = rendre(h(Banniere, { jeu }), langue);
      assert.match(html, /role="note"/);
      assert.match(html, new RegExp(`data-jeu="${jeu}"`));
      assert.ok(texte(html).includes(texte(catalogues[langue][CLES_BANNIERE[jeu]])), `${jeu} ${langue}`);
      assert.match(html, /<strong>/);
    }
  }
});

test("the explained empty state holds its sentence and its action, or its sentence alone", () => {
  const html = rendre(h(EtatVide, { phrase: "tableau.form.teamRequired", action: { cle: "tableau.title", adresse: "#/tableau" } }), "en");
  assert.match(html, /Choose a team to make a sheet/);
  assert.match(html, /href="#\/tableau"/);
  assert.doesNotMatch(rendre(h(EtatVide, { phrase: "tableau.form.teamRequired" }), "en"), /<a /);
});

test("the conviction card holds the theme, the statement and the link, in both languages, and no verdict and no figure", () => {
  for (const genre of GRAPHIQUES_DE_FICHE) {
    for (const langue of LANGUES) {
      const html = propre(rendre(h(CarteConviction, { genre }), langue));
      assert.match(html, new RegExp(`href="#/conviction/${genre}"`));
      assert.ok(texte(html).includes(catalogues[langue][CLES_CONVICTION[genre].enonce]), `${genre} ${langue}`);
      assert.ok(texte(html).includes(catalogues[langue][CLES_CONVICTION[genre].nav]), `${genre} ${langue}`);
      assert.doesNotMatch(html, /class="badge|data-etat|<svg|%/);
    }
  }
});

test("the side navigation marks the current entry, in both languages, and carries no state marker", () => {
  const nav = h(NavigationLaterale, {
    accueilCourant: false,
    convictions: [
      { genre: "lead_cycle_h1", courante: true },
      { genre: "lead_cycle_h5", courante: false },
    ],
    tableau: { courant: false },
  });
  for (const langue of LANGUES) {
    const html = propre(rendre(nav, langue));
    assert.match(html, /<nav[^>]*aria-label="/);
    assert.equal((html.match(/aria-current="page"/g) ?? []).length, 1);
    assert.match(html, /href="#\/conviction\/lead_cycle_h1"[^>]*aria-current="page"/);
    assert.match(html, /href="#\/tableau"/);
    assert.doesNotMatch(html, /nav-pastille|data-etat|role="img"/);
  }
  assert.doesNotMatch(rendre(h(NavigationLaterale, { accueilCourant: true, convictions: [] }), "en"), /href="#\/tableau"/);
});

test("the three templates fix the order of their slots and the shell draws the banner of the dataset code it is given", () => {
  const nav = h(NavigationLaterale, { accueilCourant: true, convictions: [] });
  const avec = rendre(h(Coquille, { navigation: nav, jeu: "synthetic" }, h("p", null, "x")), "en");
  assert.ok(avec.indexOf("<aside") < avec.indexOf('role="note"') && avec.indexOf('role="note"') < avec.indexOf("<main"));
  assert.match(rendre(h(Coquille, { navigation: nav, jeu: "real" }), "en"), /data-jeu="real"/);
  assert.doesNotMatch(rendre(h(Coquille, { navigation: nav }), "en"), /role="note"/);
  const fiche = rendre(
    h(GabaritFiche, { enonce: "conviction.statement.lead_cycle_h1", badge: h(BadgeVerdict, { etat: "confirmed" }), preuve: h("p", null, "P"), encarts: h("p", null, "E"), pied: h("p", null, "F") }),
    "en",
  );
  const places = ["<h1", "badge", "P</p>", "E</p>", "<footer"].map((m) => fiche.indexOf(m));
  assert.deepEqual([...places].sort((a, b) => a - b), places);
  const indicateurs = rendre(h(GabaritIndicateurs, { titre: "home.title", introduction: "home.intro", cartes: h("p", null, "C"), pied: h("p", null, "F") }), "en");
  assert.ok(indicateurs.indexOf("<h1") < indicateurs.indexOf("C</p>") && indicateurs.indexOf("C</p>") < indicateurs.indexOf("<footer"));
  assert.doesNotMatch(indicateurs, /<section/);
});

// ---- the addresses and the browser memory (tasks 5.2 and 5.3) --------------------------------------------------------------------

test("the address gives the conviction screen for a served kind, with or without an opaque identifier, and the home otherwise", () => {
  assert.equal(ecranDuHash("#/conviction/lead_cycle_h1"), "conviction");
  assert.equal(ecranDuHash("#/conviction/lead_cycle_h5/abc-123"), "conviction");
  assert.deepEqual(convictionDuHash("#/conviction/lead_cycle_h1/abc-123"), { genre: "lead_cycle_h1", id: "abc-123" });
  assert.equal(ecranDuHash("#/conviction/inconnue"), "squelette");
  assert.equal(ecranDuHash("#/conviction/lead_cycle_h1/pas un identifiant"), "squelette");
  assert.equal(ecranDuHash("#/conviction/lead_cycle_h1/a/b"), "squelette");
  assert.equal(ecranDuHash(""), "squelette");
  assert.equal(ecranDuHash("#/autre"), "squelette");
  assert.equal(ecranDuHash("#/tableau"), "tableau");
});

test("the memory keeps one opaque identifier per kind, nothing else (no reference team, no kind opened last), and erases a malformed value", () => {
  const m = memoire();
  assert.equal(lireDerniereFiche("lead_cycle_h1", m), undefined);
  assert.equal(ecrireDerniereFiche("lead_cycle_h1", "fiche-1", m), true);
  assert.equal(ecrireDerniereFiche("lead_cycle_h5", "fiche-2", m), true);
  assert.equal(lireDerniereFiche("lead_cycle_h1", m), "fiche-1");
  assert.equal(lireDerniereFiche("lead_cycle_h5", m), "fiche-2");
  assert.deepEqual(JSON.parse(m.valeur ?? "{}"), { fiches: { lead_cycle_h1: "fiche-1", lead_cycle_h5: "fiche-2" } });
  assert.equal(ecrireDerniereFiche("lead_cycle_h1", "Pas un identifiant", m), false);
  assert.equal(lireDerniereFiche("lead_cycle_h1", m), "fiche-1");
  assert.deepEqual(JSON.parse(m.valeur ?? "{}"), { fiches: { lead_cycle_h1: "fiche-1", lead_cycle_h5: "fiche-2" } });
  for (const mauvais of [
    JSON.stringify({ fiches: { lead_cycle_h1: "a b" } }),
    JSON.stringify({ fiches: { autre: "x" } }),
    // The field of the abandoned design (the kind opened last) is no longer part of the shape: a value that holds it is erased.
    JSON.stringify({ fiches: { lead_cycle_h1: "fiche-1" }, derniere: "lead_cycle_h1" }),
    JSON.stringify({ fiches: {}, texte: "un texte libre" }),
    JSON.stringify({ lead_cycle_h1: "fiche-1" }),
    "pas du json",
  ]) {
    const stockage = memoire(mauvais);
    assert.equal(lireDerniereFiche("lead_cycle_h1", stockage), undefined);
    assert.equal(stockage.valeur, undefined, "the malformed value is erased");
  }
  assert.equal(ecrireDerniereFiche("lead_cycle_h1", "fiche-1", undefined), false);
});

// ---- the memory is written when a draft is created (task 5.3) ------------------------------------------------------------------------

test("the dashboard writes the memory when a draft is created: the opaque identifier of the kind, and nothing when no draft is made", async () => {
  const m = memoire();
  const etat = await ouvrirBrouillon(async () => ({ id: "fiche-9", state: "draft" as const }), "team-a", "2026-10-05", "lead_cycle_h1", {}, m);
  assert.deepEqual(etat, { genre: "brouillon", id: "fiche-9" });
  assert.deepEqual(JSON.parse(m.valeur ?? "{}"), { fiches: { lead_cycle_h1: "fiche-9" } });
  assert.equal(lireDerniereFiche("lead_cycle_h1", m), "fiche-9");
  // A second draft of another kind adds its identifier and keeps the first.
  await ouvrirBrouillon(async () => ({ id: "fiche-10", state: "draft" as const }), "team-a", "2026-10-05", "lead_cycle_h5", {}, m);
  assert.deepEqual(JSON.parse(m.valeur ?? "{}"), { fiches: { lead_cycle_h1: "fiche-9", lead_cycle_h5: "fiche-10" } });
  // A refused request, a missing team and a missing date write nothing.
  const vide = memoire();
  const refuse = await ouvrirBrouillon(
    async () => {
      throw new Error("refus");
    },
    "team-a",
    "2026-10-05",
    "lead_cycle_h1",
    {},
    vide,
  );
  assert.equal(refuse.genre, "erreur");
  assert.equal((await ouvrirBrouillon(async () => ({ id: "x", state: "draft" as const }), "", "2026-10-05", "lead_cycle_h1", {}, vide)).genre, "equipe_requise");
  assert.equal((await ouvrirBrouillon(async () => ({ id: "x", state: "draft" as const }), "team-a", " ", "lead_cycle_h1", {}, vide)).genre, "erreur");
  assert.equal(vide.ecritures, 0);
  assert.equal(vide.valeur, undefined);
});

// ---- the shell: the banner once per screen, the navigation, the home (tasks 5.1, 5.2, 5.4, 5.7) -------------------------------------

// The answers of the dashboard that the tests hand to the application (R-20261031-61): the synthetic view rows go through the contract's
// `tableauLeadCycle`, as the server's route does; the dataset code is then set as the service layer sets it (task 19.6), and the real form is
// the contract's reduction of the answer. The first form carries no dataset code, as an answer of an older service would.
function reponseSansCode(): ReponseLeadCycle {
  const val = (v: number) => ({ state: "value" as const, value: v });
  const ligne = (team: string, debut: string | null) => ({
    team,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    items_lt: val(30),
    items_ct: val(30),
    lead_median_days: val(40),
    cycle_median_days: val(10),
  });
  const debuts = ["2025-10-01", "2026-01-01", "2026-04-01", "2026-07-01"];
  const rows = ["team-a", "team-b"].flatMap((team) => [...debuts.map((d) => ligne(team, d)), ligne(team, null)]);
  const vue = { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows, sources: ["flow"] };
  return tableauLeadCycle(vue as never, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe);
}

function reponseDe(jeu: "synthetic" | "real" | undefined): ReponseLeadCycle | ReponseLeadCycleReduite {
  const base = reponseSansCode();
  if (jeu === undefined) return base;
  return jeu === "synthetic" ? { ...base, dataset: "synthetic" } : reduceToStatistics({ ...base, dataset: "real" });
}

type PropsApplication = Partial<Parameters<typeof Application>[0]>;

// A client whose cache entries are never collected by a timer, so that a test that installs a window (below) leaves no timer alive.
function nouveauClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
}

async function application(props: PropsApplication, jeu: "synthetic" | "real" | undefined): Promise<string> {
  const reponse = reponseDe(jeu);
  const lireTableau = async () => reponse;
  const client = nouveauClient();
  await client.prefetchQuery(optionsLeadCycle(lireTableau));
  const source = { lire: lireTableau, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  return propre(rendre(h(QueryClientProvider, { client }, h(Application, { tableau: source, ...props })), "en"));
}

// Runs the work while a window whose `localStorage` is the given storage is installed (the window the code looks for: `localStorage` and
// `location.hash`), and counts how many times the code asked the window for its storage: a read of the browser memory goes through it. The
// window is removed whatever happens.
async function avecFenetre<T>(stockage: MemoireDeTest, travail: () => Promise<T>): Promise<{ resultat: T; acces: number }> {
  const globale = globalThis as unknown as { window?: unknown };
  const avant = globale.window;
  let acces = 0;
  globale.window = {
    location: { hash: "" },
    get localStorage(): StockageIdentifiant {
      acces += 1;
      return stockage;
    },
  };
  try {
    const resultat = await travail();
    return { resultat, acces };
  } finally {
    if (avant === undefined) delete globale.window;
    else globale.window = avant;
  }
}

test("the answers of the tests come from the contract: every series carries the opaque identifier the contract derives", () => {
  const reponse = reponseDe("synthetic");
  assert.deepEqual(reponse.teams.map((e) => e.teamId), ["team-a", "team-b"].map((t) => identifiantEquipe(t)));
  assert.equal(reponse.dataset, "synthetic");
  assert.equal(reponseDe(undefined).dataset, undefined);
  const reduite = reponseDe("real");
  assert.equal(reduite.dataset, "real");
  assert.equal(JSON.stringify(reduite).includes('"items"'), false);
});

test("one banner per screen, by dataset code, and the dashboard keeps its own note until its redesign without a second banner", async () => {
  const synthetique = await application({}, "synthetic");
  assert.equal((synthetique.match(/class="banniere"/g) ?? []).length, 1);
  assert.match(synthetique, /data-jeu="synthetic"/);
  assert.match(texte(synthetique), /Synthetic data\. These figures are not real\./);
  const reel = await application({}, "real");
  assert.equal((reel.match(/class="banniere"/g) ?? []).length, 1);
  assert.match(reel, /data-jeu="real"/);
  assert.doesNotMatch(reel, /data-jeu="synthetic"/);
  assert.match(texte(reel), /Real data, reduced form\. Statistics only, no counts\./);
  // The dashboard of the synthetic dataset: one banner of the shell, and the note of the dashboard itself (`fiche.syntheticNotice`, kept by D1
  // until the dashboard is redesigned) which is not a banner.
  const tableau = await application({ ecranInitial: "tableau" }, "synthetic");
  assert.equal((tableau.match(/class="banniere"/g) ?? []).length, 1);
  // R-20261101-129 (Q268 (a)): the note of the dashboard moved into the banner as a line; no other note of the synthetic dataset remains.
  assert.equal((tableau.match(/class="fiche-jeu-synthetique"/g) ?? []).length, 0);
  assert.equal((tableau.match(/role="note"/g) ?? []).length, 1);
  assert.match(tableau, /class="banniere-ligne">On the synthetic dataset, not on real data.</);
  assert.doesNotMatch(texte(tableau), /Simulated data: these are not real figures/);
});

test("an answer without a dataset code, or with a code the front does not know, shows no banner", async () => {
  const sans = await application({}, undefined);
  assert.doesNotMatch(sans, /class="banniere"|data-jeu=|role="note"/);
  assert.match(sans, /<h1[^>]*>What the data say about our convictions<\/h1>/);
  const sansEcranTableau = await application({ ecranInitial: "tableau" }, undefined);
  assert.equal((sansEcranTableau.match(/class="banniere"/g) ?? []).length, 0);
  assert.equal(jeuDeDonnees(undefined), undefined);
  assert.equal(jeuDeDonnees("other"), undefined);
  assert.equal(jeuDeDonnees(""), undefined);
  assert.equal(jeuDeDonnees("synthetic"), "synthetic");
  assert.equal(jeuDeDonnees("real"), "real");
  // The component itself has no default: the source requires the code, so that a missing one can never draw the banner of the other.
  assert.match(readFileSync(`${FRONT}src/composants/Banniere.ts`, "utf8"), /\{ jeu \}: \{ jeu: JeuDeDonnees \}/);
});

test("the banner reads the dashboard answer through the query cache: no second request for the dataset code", async () => {
  let appels = 0;
  const reponse = reponseDe("synthetic");
  const lire = async () => {
    appels += 1;
    return reponse;
  };
  const client = new QueryClient();
  await client.prefetchQuery(optionsLeadCycle(lire));
  const source = { lire, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  rendre(h(QueryClientProvider, { client }, h(Application, { tableau: source })), "en");
  assert.equal(appels, 1);
});

test("without a dashboard source the answer is not known and no banner is shown", () => {
  assert.doesNotMatch(rendre(h(QueryClientProvider, { client: new QueryClient() }, h(Application, {})), "en"), /role="note"/);
});

test("the navigation lists no conviction before lot 3b (R-20261101-31: neither hypothesis 1 nor 5), holds the home and the dashboard, and no top navigation", async () => {
  for (const jeu of ["synthetic", "real"] as const) {
    // R-20261101-125 (Q257 (a)): the list of the shipped kinds is injected empty, as lot 3a shipped it; the intention is kept, as strict.
    const html = await application({ convictionsLivrees: [] }, jeu);
    assert.doesNotMatch(html, /href="#\/conviction\//);
    assert.match(html, /href="#\/tableau"/);
    assert.match(html, /<a href="#\/"[^>]*>Home<\/a>/);
    assert.match(html, /<nav[^>]*aria-label="Main navigation"/);
    assert.doesNotMatch(html, /class="navigation"/);
  }
});

test("no entry, link or section for the status by team: the navigation holds the home, the served convictions and the dashboard", async () => {
  for (const langue of LANGUES) {
    const html = await application({ langueInitiale: langue }, "synthetic");
    assert.doesNotMatch(texte(html), /Status by team|Statut par équipe/);
    assert.equal((html.match(/<section/g) ?? []).length, 0);
    assert.equal((html.match(/<table/g) ?? []).length, 0);
  }
  assert.equal("page.statusByTeam.title" in catalogues.en, false);
  assert.equal("page.statusByTeam.title" in catalogues.fr, false);
});

test("the language selector and the identifier field are at the bottom of the side column", async () => {
  const identifiant = { lire: () => "agile-lead-1", ecrire: () => "saved" as const };
  const html = await application({ identifiant }, "synthetic");
  const bas = /<div class="nav-bas">[\s\S]*<\/div><\/aside>/.exec(html)?.[0] ?? "";
  assert.match(bas, /<select/);
  assert.ok(bas.includes(catalogues.en["app.identity.label"]));
  assert.equal(html.split("<select").length - 1, 1);
});

test("the home lists the served convictions only, none before lot 3b, and shows no verdict, no marker, no count, no status section", async () => {
  // R-20261101-125 (Q257 (a)): an empty list is injected instead of reading the constant.
  const html = await application({ convictionsLivrees: [] }, "synthetic");
  assert.equal((html.match(/class="carte-conviction"/g) ?? []).length, 0);
  assert.match(html, /<h1[^>]*>What the data say about our convictions<\/h1>/);
  assert.equal((html.match(/<section/g) ?? []).length, 0);
  assert.doesNotMatch(html, /class="badge|data-etat|nav-pastille/);
  assert.doesNotMatch(texte(html), /\d+ (confirmed|refuted|not settled)/);
});

test("a kind that is not served gives the home, not the page; hypothesis 5 opens its page on the synthetic dataset", async () => {
  const reel = await application({ ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h5" } }, "real");
  assert.match(reel, /What the data say about our convictions/);
  // R-20261103-14 (Q1 (a)): lot 3c ships hypothesis 5 on the synthetic dataset; this assertion, which gave the home before lot 3c, now says the
  // page opens (the statement of the kind, not the home), and the real dataset keeps the home, as strict as before.
  const apres3c = await application({ ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h5" } }, "synthetic");
  assert.doesNotMatch(apres3c, /What the data say about our convictions/);
  assert.ok(texte(apres3c).includes(catalogues.en["conviction.statement.lead_cycle_h5"]));
});

test("the entry of hypothesis 5 is visible in the navigation on the synthetic dataset and absent on the real one, with the shipped list", async () => {
  // R-20261103-14 (Q1 (a)), new test of lot 3c: the shipped list (no list given) serves hypothesis 5 on the synthetic dataset only.
  const synthetique = await application({}, "synthetic");
  const navSynthetique = /<nav[\s\S]*?<\/nav>/.exec(synthetique)?.[0] ?? "";
  assert.deepEqual(genresDe(navSynthetique, DANS_NAV), ORDRE_DU_CONTRAT);
  assert.ok(navSynthetique.includes(catalogues.en["conviction.nav.lead_cycle_h5"]));
  const reel = await application({}, "real");
  const navReel = /<nav[\s\S]*?<\/nav>/.exec(reel)?.[0] ?? "";
  assert.deepEqual(genresDe(navReel, DANS_NAV), ["lead_cycle_h1"]);
  assert.doesNotMatch(reel, /href="#\/conviction\/lead_cycle_h5"/);
  assert.ok(!navReel.includes(catalogues.en["conviction.nav.lead_cycle_h5"]));
});

// ---- the served convictions, with a list given by the test (the shipped list is empty in lot 3a) (tasks 5.2 and 5.4) ---------------------

const genresDe = (html: string, motif: RegExp): string[] => [...html.matchAll(motif)].map((m) => m[1]);
const DANS_NAV = /href="#\/conviction\/([a-z0-9_]+)"/g;
const CARTES = /class="carte-conviction" href="#\/conviction\/([a-z0-9_]+)"/g;

test("the shipped list holds hypotheses 1 and 5 after lot 3c and the served kinds are the contract's list filtered by the dataset, then by the given list", () => {
  // R-20261101-125 (Q257 (a)): lot 3b shipped hypothesis 1 and only it (hypothesis 5 stayed hidden until lot 3c, R-20261101-31); the served-kind
  // filters below are exercised with lists given by the test, an empty one included.
  // R-20261103-14 (Q1 (a)): after lot 3c the shipped list is exact by dataset, as strict as before: hypothesis 1 and hypothesis 5 on the
  // synthetic dataset, hypothesis 1 alone on the real one (the contract's list removes hypothesis 5 there).
  // R-20261103-24 Q4 (b): `CONVICTIONS_LIVREES` is removed; the kinds served by the application are the contract's list filtered by the dataset,
  // exact by dataset and as strict as before.
  assert.deepEqual([...ORDRE_DU_CONTRAT].sort(), ["lead_cycle_h1", "lead_cycle_h5"]);
  assert.deepEqual([...convictionsServies(false)], [...ORDRE_DU_CONTRAT]);
  assert.deepEqual(convictionsServies(false), ORDRE_DU_CONTRAT);
  assert.deepEqual([...convictionsServies(true)], ["lead_cycle_h1"]);
  assert.deepEqual(convictionsServies(false, []), []);
  assert.deepEqual(convictionsServies(false, DEUX_CONVICTIONS), ORDRE_DU_CONTRAT);
  assert.deepEqual(convictionsServies(true, DEUX_CONVICTIONS), ["lead_cycle_h1"]);
  assert.deepEqual(convictionsServies(false, ["lead_cycle_h5"]), ["lead_cycle_h5"]);
  assert.deepEqual(convictionsServies(true, ["lead_cycle_h5"]), []);
  assert.deepEqual(convictionsServies(false, []), []);
  assert.deepEqual(convictionsServies(false, [...DEUX_CONVICTIONS].reverse()), ORDRE_DU_CONTRAT, "the contract's order, one entry per kind");
});

test("the navigation and the home hold one entry and one card per served kind, hypothesis 5 absent on real data, none for the kinds left out", async () => {
  const cas: ReadonlyArray<readonly ["synthetic" | "real", readonly GraphiqueDeFiche[]]> = [
    ["synthetic", ORDRE_DU_CONTRAT],
    ["real", ["lead_cycle_h1"]],
  ];
  for (const [jeu, attendus] of cas) {
    const html = await application({ convictionsLivrees: DEUX_CONVICTIONS }, jeu);
    const nav = /<nav[\s\S]*?<\/nav>/.exec(html)?.[0] ?? "";
    assert.deepEqual(genresDe(nav, DANS_NAV), attendus, jeu);
    assert.deepEqual(genresDe(html, CARTES), attendus, jeu);
    assert.match(nav, />Convictions<\/p>/);
  }
  const seulement = await application({ convictionsLivrees: ["lead_cycle_h5"] }, "synthetic");
  assert.deepEqual(genresDe(seulement, CARTES), ["lead_cycle_h5"]);
  const aucune = await application({ convictionsLivrees: ["lead_cycle_h5"] }, "real");
  assert.deepEqual(genresDe(aucune, CARTES), []);
  assert.doesNotMatch(aucune, />Convictions<\/p>/);
  // Without the answer (no dashboard source) no kind is served: the entries wait for the dataset code.
  const sansSource = propre(rendre(h(QueryClientProvider, { client: nouveauClient() }, h(Application, { convictionsLivrees: DEUX_CONVICTIONS })), "en"));
  assert.deepEqual(genresDe(sansSource, CARTES), []);
});

test("the current entry of the navigation follows the address: the kind of a served address, the home for a kind that is not served", async () => {
  const courante = (html: string): string[] => [...html.matchAll(/<a href="([^"]*)" class="nav-entree nav-entree-courante" aria-current="page">/g)].map((m) => m[1]);
  const h1 = await application({ convictionsLivrees: DEUX_CONVICTIONS, ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h1" } }, "synthetic");
  assert.deepEqual(courante(h1), ["#/conviction/lead_cycle_h1"]);
  const h5Reel = await application({ convictionsLivrees: DEUX_CONVICTIONS, ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h5" } }, "real");
  assert.deepEqual(courante(h5Reel), ["#/"]);
  const accueil = await application({ convictionsLivrees: DEUX_CONVICTIONS }, "synthetic");
  assert.deepEqual(courante(accueil), ["#/"]);
  const tableau = await application({ convictionsLivrees: DEUX_CONVICTIONS, ecranInitial: "tableau" }, "synthetic");
  assert.deepEqual(courante(tableau), ["#/tableau"]);
});

// ---- the navigation and the home read nothing from the browser memory (tasks 5.2 and 5.4, Q158 (b), R-20261101-42) ---------------------

const MEMOIRE_PLEINE = JSON.stringify({ fiches: { lead_cycle_h1: "fiche-1", lead_cycle_h5: "fiche-2" } });

test("the navigation reads no memory, whatever the memory holds: not even the window's storage is asked for", async () => {
  for (const contenu of [undefined, MEMOIRE_PLEINE, "pas du json", JSON.stringify({ fiches: { autre: "x" } })]) {
    const m = memoire(contenu);
    const { resultat, acces } = await avecFenetre(m, () => application({ convictionsLivrees: DEUX_CONVICTIONS }, "synthetic"));
    assert.equal(acces, 0, `le stockage a été demandé (mémoire : ${String(contenu)})`);
    assert.equal(m.lectures, 0);
    assert.equal(m.ecritures, 0);
    assert.equal(m.valeur, contenu, "the memory is left untouched, a malformed value included");
    assert.match(resultat, /<nav[^>]*aria-label="Main navigation"/);
    assert.deepEqual(genresDe(/<nav[\s\S]*?<\/nav>/.exec(resultat)?.[0] ?? "", DANS_NAV), ORDRE_DU_CONTRAT);
  }
});

test("the home is the same with an empty memory and with two remembered sheets, with no share sentence and no other-team sentence", async () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const videM = memoire();
    const pleineM = memoire(MEMOIRE_PLEINE);
    const vide = await avecFenetre(videM, () => application({ convictionsLivrees: DEUX_CONVICTIONS }, jeu));
    const pleine = await avecFenetre(pleineM, () => application({ convictionsLivrees: DEUX_CONVICTIONS }, jeu));
    assert.equal(vide.resultat, pleine.resultat, jeu);
    assert.equal(vide.acces + pleine.acces, 0);
    assert.equal(videM.lectures + pleineM.lectures, 0);
    assert.doesNotMatch(vide.resultat, /class="badge|data-etat|nav-pastille/);
    assert.doesNotMatch(texte(vide.resultat), /\d+ (confirmed|refuted|not settled)|\d+ %/);
  }
  for (const [langue, catalogue] of Object.entries(catalogues)) {
    assert.equal("home.share" in catalogue, false, `home.share (${langue})`);
    assert.equal("home.otherTeam" in catalogue, false, `home.otherTeam (${langue})`);
  }
});

test("only the dashboard page touches the browser memory: the shell, the navigation, the home and the cards import nothing of it", () => {
  const importeurs = sources(FRONT, "src", [".ts", ".tsx"])
    .filter((s) => s.contenu.includes("derniereFiche"))
    .map((s) => s.nom);
  assert.deepEqual(importeurs, ["src/pages/PageTableau.ts"]);
});

test("before lot 3b no conviction page, entry or route exists: the address of hypothesis 1 gives the home under one banner", async () => {
  // R-20261101-125 (Q257 (a)): an empty list is injected instead of reading the constant.
  const html = await application({ convictionsLivrees: [], ecranInitial: "conviction", convictionInitiale: { genre: "lead_cycle_h1" } }, "synthetic");
  assert.equal((html.match(/role="note"/g) ?? []).length, 1);
  assert.match(html, /<h1[^>]*>What the data say about our convictions<\/h1>/);
  assert.doesNotMatch(html, /href="#\/conviction\//);
  assert.doesNotMatch(html, /Most of the lead time is spent waiting/);
});

// ---- the draft panel links to the conviction screen (task 5.3) ----------------------------------------------------------------------

function panneauBrouillon(genreBrouillon: GraphiqueDeFiche, convictionsLivrees?: readonly GraphiqueDeFiche[]): string {
  return rendre(
    h(ContenuTableau, {
      reponse: reponseDe("synthetic"),
      portee: "team-a",
      surPortee: () => undefined,
      fiche: { genre: "brouillon", id: "fiche-7" },
      surFaire: () => undefined,
      surCreer: () => undefined,
      simulee: false,
      genreBrouillon,
      ...(convictionsLivrees === undefined ? {} : { convictionsLivrees }),
    }),
    "en",
  );
}

test("the draft panel links to the conviction screen of the kind it was made for, with the opaque identifier, when that kind is shipped", () => {
  const html = panneauBrouillon("lead_cycle_h1", DEUX_CONVICTIONS);
  assert.match(html, /<a class="lien" href="#\/conviction\/lead_cycle_h1\/fiche-7">Open the conviction sheet<\/a>/);
  assert.match(panneauBrouillon("lead_cycle_h5", ["lead_cycle_h5"]), /href="#\/conviction\/lead_cycle_h5\/fiche-7"/);
});

test("the draft panel offers no link to a conviction page that is not shipped: none in lot 3a, nor for a kind left out of the given list", () => {
  // R-20261101-125 (Q257 (a)): the shipped list now holds hypothesis 1, so the test gives an empty list instead of reading the constant.
  assert.doesNotMatch(panneauBrouillon("lead_cycle_h1", []), /href="#\/conviction\/|Open the conviction sheet/);
  assert.doesNotMatch(panneauBrouillon("lead_cycle_h1", ["lead_cycle_h5"]), /href="#\/conviction\//);
  // The rest of the panel is unchanged: the draft is announced and its state is shown.
  const sans = panneauBrouillon("lead_cycle_h1");
  assert.ok(texte(sans).includes(catalogues.en["tableau.draft.opened"]));
  assert.ok(texte(sans).includes(catalogues.en["tableau.state.draft"]));
});
