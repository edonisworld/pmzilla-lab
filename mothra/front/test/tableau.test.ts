// Task 19.2: the dashboard "lead time against cycle time" of slice 1 (design D19, D20, D22, D24), on SIMULATED answers (synthetic
// figures, declared as such on the screen and in the module), with "make it a sheet" opening a draft through a simulated route.
// Nothing here calls the network; the real route comes with group 18.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { IntlProvider } from "react-intl";

import { Application, ecranDuHash } from "../src/Application.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";
import type { ReponseLeadCycle } from "@mothra/contract";
import { CelluleInsuffisante } from "../src/composants/Cellule.ts";
import { TableauLeadCycle } from "../src/composants/TableauLeadCycle.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { ContenuTableau, GRAPHIQUES_FICHE, ouvrirBrouillon, ouvrirFormulaire, PageTableau } from "../src/pages/PageTableau.ts";
import { creerFicheSimulee, lireLeadCycleSimule, SOURCE_SIMULEE } from "../src/simule/leadCycle.ts";
import type { SourceLeadCycle } from "../src/api/leadCycle.ts";
import { rendre, texte } from "./rendu.ts";
import { sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

const reponse: ReponseLeadCycle = {
  threshold: 5,
  dataDate: "2026-10-27",
  dataset: "synthetic",
  product: [
    { quarter: "2026-Q1", lead: { state: "value", value: 41 }, cycle: { state: "value", value: 9 }, items: { state: "value", value: 120 } },
    { quarter: "2026-Q2", lead: { state: "value", value: 38 }, cycle: { state: "value", value: 11 }, items: { state: "value", value: 133 } },
  ],
  teams: [
    {
      team: "Team C",
      teamId: identifiantEquipe("Team C"),
      points: [
        { quarter: "2026-Q1", lead: { state: "masked", threshold: 5 }, cycle: { state: "masked", threshold: 5 }, items: { state: "masked", threshold: 5 } },
        { quarter: "2026-Q2", lead: { state: "value", value: 29 }, cycle: { state: "value", value: 7 }, items: { state: "value", value: 22 } },
      ],
    },
    {
      team: "Team A",
      teamId: identifiantEquipe("Team A"),
      points: [
        { quarter: "2026-Q1", lead: { state: "insufficient_sample" }, cycle: { state: "insufficient_sample" }, items: { state: "value", value: 6 } },
        { quarter: "2026-Q2", lead: { state: "value", value: 52 }, cycle: { state: "value", value: 14 }, items: { state: "value", value: 31 } },
      ],
    },
    {
      team: "Team B",
      teamId: identifiantEquipe("Team B"),
      points: [
        { quarter: "2026-Q1", lead: { state: "value", value: 20 }, cycle: { state: "value", value: 6 }, items: { state: "value", value: 18 } },
        { quarter: "2026-Q2", lead: { state: "value", value: 22 }, cycle: { state: "value", value: 5 }, items: { state: "value", value: 19 } },
      ],
    },
  ],
};

const SANS_FICHE = { genre: "aucune" } as const;

function contenu(
  portee: string,
  langue: Langue = "en",
  fiche: Parameters<typeof ContenuTableau>[0]["fiche"] = SANS_FICHE,
  donnees = reponse,
  simulee = true,
): string {
  return rendre(h(ContenuTableau, { reponse: donnees, portee, surPortee: () => undefined, fiche, surFaire: () => undefined, surCreer: () => undefined, simulee }), langue);
}

// A real source: nothing simulated, an answer given, no sheet route used.
const SOURCE_REELLE: SourceLeadCycle = { lire: async () => reponse, creer: async () => ({ id: "reel-1", state: "draft" }), simulee: false };

function cellules(html: string, classe: string): string[] {
  return [...html.matchAll(new RegExp(`<td class="[^"]*${classe}[^"]*"[^>]*>(.*?)</td>`, "g"))].map((m) => texte(m[1]));
}

// ---- simulated data, declared as such ---------------------------------------------------------------------------------------

// R-20261101-40 (Q156): the notice of the simulated data is the banner of the shell (one banner per screen, R-20261101-23), by the dataset
// code of the answer; the panel no longer carries its own, and its key left the catalogues.
test("the data of this screen are simulated, declared so by the flag of the source and on the screen in each language by the banner of the shell", async () => {
  assert.equal(SOURCE_SIMULEE.simulee, true);
  assert.equal((await SOURCE_SIMULEE.lire()).dataset, "synthetic");
  assert.doesNotMatch(texte(contenu("")), /Simulated data|Données simulées/);
  assert.equal("tableau.simulatedData" in en, false);
  assert.match(texte(await application({ ecranInitial: "tableau" })), /Synthetic data\. These figures are not real\./);
  assert.match(texte(await application({ ecranInitial: "tableau", langueInitiale: "fr" })), /Données synthétiques\. Ces chiffres ne sont pas réels\./);
});

test("a real source shows no simulated-data notice, neither on the screen nor in the draft panel", () => {
  assert.doesNotMatch(texte(contenu("", "en", SANS_FICHE, reponse, false)), /Simulated data/);
  assert.doesNotMatch(texte(contenu("", "fr", SANS_FICHE, reponse, false)), /Données simulées/);
  const brouillon = texte(contenu("", "en", { genre: "brouillon", id: "reel-1" }, reponse, false));
  assert.match(brouillon, /A draft sheet is open\./);
  assert.doesNotMatch(brouillon, /Simulated route/);
  assert.doesNotMatch(contenu("", "en", SANS_FICHE, reponse, false), /donnees-simulees/);
});

test("only the entry of the bundle imports the simulated sources: the screens receive them by injection", () => {
  const importeurs = sources(FRONT, "src", [".ts", ".tsx"])
    .filter((s) => !s.nom.startsWith("src/simule/") && /\bfrom\s*["'][^"']*simule\//.test(s.contenu))
    .map((s) => s.nom);
  assert.deepEqual(importeurs, ["src/main.ts"]);
  assert.match(readFileSync(`${FRONT}src/main.ts`, "utf8"), /choisirSource\(SOURCE_SIMULEE/);
});

test("the page names the hypothesis it serves and the date of its data, in each language", () => {
  const anglais = texte(contenu(""));
  assert.match(anglais, /These lead time and cycle time data serve two convictions: “Work stays stable” and “Waiting dominates the lead time”\./);
  assert.match(anglais, /Data as of October 27, 2026/);
  const francais = texte(contenu("", "fr"));
  assert.match(francais, /Ces données de lead time et de cycle time servent deux convictions : « Le travail reste stable » et « L(?:'|&#x27;)attente domine le délai »\./);
  assert.match(francais, /Données au 27 octobre 2026/);
});

test("without the date of the data the screen says so and the sheet button is disabled", () => {
  const sans = { ...reponse, dataDate: "  " };
  const anglais = contenu("", "en", SANS_FICHE, sans);
  assert.match(texte(anglais), /The date of the data is missing/);
  assert.doesNotMatch(texte(anglais), /Data as of/);
  assert.match(anglais, /<button type="button" class="bouton" disabled="">Make it a sheet<\/button>/);
  assert.match(texte(contenu("", "fr", SANS_FICHE, sans)), /La date des données est absente/);
  assert.doesNotMatch(contenu(""), /<button[^>]*disabled/);
});

test("the missing-date message carries the error class and the error colour wins over the muted colour of the date line", () => {
  const html = contenu("", "en", SANS_FICHE, { ...reponse, dataDate: "" });
  assert.match(html, /<p role="alert" class="tableau-date page-erreur">/);
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  const regle = /\.tableau-date\.page-erreur\s*\{([^}]*)\}/.exec(css);
  assert.ok(regle, "règle .tableau-date.page-erreur absente");
  assert.match(regle[1], /color:\s*var\(--color-state-error\)/);
  // two classes beat the one-class rule that sets the muted colour, whatever the order of the rules: the muted rule is a single-class
  // selector list, so the compound selector above is the more specific one
  assert.match(css, /\.tableau-date\s*\{[^}]*color:\s*var\(--color-text-muted\)/);
});

test("the simulated reader answers without any network: it holds all three kinds of cell and no real name", async () => {
  const simulee = await lireLeadCycleSimule();
  const etats = new Set([...simulee.product, ...simulee.teams.flatMap((e) => e.points)].flatMap((p) => [p.lead.state, p.cycle.state, p.items.state]));
  assert.deepEqual([...etats].sort(), ["insufficient_sample", "masked", "value"]);
  assert.ok(simulee.teams.length >= 3);
  assert.ok(simulee.teams.every((e) => /^team-[a-z]$/.test(e.team ?? "")), "noms génériques seulement");
  assert.ok(simulee.threshold >= 5);
});

test("the query options of the dashboard name one key and do not retry", () => {
  const options = optionsLeadCycle(lireLeadCycleSimule);
  assert.deepEqual(options.queryKey, ["lead-cycle"]);
  assert.equal(options.retry, false);
});

// ---- scope: the product or one team, no ranking --------------------------------------------------------------------------------

test("the scope selector offers the product, then the teams in alphabetical order, whatever the figures", () => {
  const options = (html: string) => [...html.matchAll(/<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g)].map((m) => [m[1], m[2]]);
  assert.deepEqual(options(contenu("")), [["", "Product"], ["Team A", "Team A"], ["Team B", "Team B"], ["Team C", "Team C"]]);
  const permutee: ReponseLeadCycle = { ...reponse, teams: [...reponse.teams].reverse().map((e) => ({ ...e, points: [...e.points].reverse() })) };
  assert.deepEqual(options(contenu("", "en", SANS_FICHE, permutee)), options(contenu("")));
  assert.deepEqual(options(contenu("", "fr")).at(0), ["", "Produit"]);
});

test("the screen shows one scope at a time: the product, or one team, never several teams side by side", () => {
  const produit = contenu("");
  assert.deepEqual(cellules(produit, "cellule-valeur"), ["41", "9", "120", "38", "11", "133"]);
  const equipe = contenu("Team B");
  assert.deepEqual(cellules(equipe, "cellule-valeur"), ["20", "6", "18", "22", "5", "19"]);
  assert.equal((equipe.match(/<table/g) ?? []).length, 1);
  assert.doesNotMatch(texte(equipe.replace(/<select[\s\S]*?<\/select>/, "")), /Team [AC]/);
});

test("no rank, no score, no comparison between teams and no total is shown", () => {
  const html = texte(contenu("Team A"));
  assert.doesNotMatch(html, /rank|best|worst|top|#\d|total|average|mean|classement|meilleur/i);
});

test("an unknown scope falls back to the product, never to an arbitrary team", () => {
  assert.deepEqual(cellules(contenu("Team Z"), "cellule-valeur"), cellules(contenu(""), "cellule-valeur"));
});

// ---- the table ---------------------------------------------------------------------------------------------------------------

test("the table has the quarter, lead time, cycle time and item columns, from the tableau.* catalogue keys, in each language", () => {
  const anglais = contenu("");
  for (const t of ["Quarter", "Lead time (median, days)", "Cycle time (median, days)", "Items"]) assert.match(anglais, new RegExp(`<th scope="col">${t.replace(/[()]/g, "\\$&")}</th>`));
  assert.match(contenu("", "fr"), /<th scope="col">Trimestre<\/th>/);
  assert.match(anglais, /<td class="cellule">Q1 2026<\/td>/);
  assert.match(contenu("", "fr"), /<td class="cellule">T1 2026<\/td>/);
  assert.doesNotMatch(anglais, /2026-Q/);
});

test("a masked cell shows the masked label and an insufficient sample shows its own icon and label, in distinct cells", () => {
  const html = contenu("Team C");
  assert.deepEqual(cellules(html, "cellule-masquee"), ["masked", "masked", "masked"]);
  const insuffisant = contenu("Team A");
  assert.deepEqual(cellules(insuffisant, "cellule-insuffisante"), ["... insufficient sample", "... insufficient sample"]);
  assert.deepEqual(cellules(insuffisant, "cellule-masquee"), []);
  assert.match(insuffisant, /data-state="insufficient_sample"/);
  assert.match(contenu("Team A", "fr"), /échantillon insuffisant/);
  assert.match(contenu("Team C", "fr"), />masqué</);
});

test("the insufficient-sample cell hides its icon from assistive technology and keeps the label", () => {
  const html = rendre(h("table", null, h("tbody", null, h("tr", null, h(CelluleInsuffisante)))), "en");
  assert.match(html, /<td class="cellule cellule-insuffisante" data-state="insufficient_sample"><span class="icone-etat" aria-hidden="true">\.\.\.<\/span> insufficient sample<\/td>/);
});

test("the masked threshold is stated once per table, from the tableau.threshold key of the catalogue", () => {
  assert.equal(texte(contenu("Team C")).split("Figures computed on fewer than 5 items are masked.").length - 1, 1);
  assert.equal(texte(contenu("Team C", "fr")).split("Les chiffres calculés sur moins de 5 éléments sont masqués.").length - 1, 1);
  assert.match(en["tableau.threshold"], /\{threshold, number\}/);
  assert.match(fr["tableau.threshold"], /\{threshold, number\}/);
});

test("the threshold sentence is tied to the table and to the chart by aria-describedby", () => {
  const html = contenu("Team C");
  const idSeuil = /<p class="tableau-seuil" id="([^"]+)"/.exec(html)?.[1];
  const idTableau = /<table class="tableau" id="([^"]+)" aria-describedby="([^"]+)"/.exec(html);
  assert.ok(idSeuil !== undefined && idTableau !== null);
  assert.equal(idTableau[2], idSeuil);
  assert.match(html, new RegExp(`class="graphique" role="img" aria-label="[^"]+" aria-describedby="${idTableau[1]} ${idSeuil}"`));
});

test("a masked cell holds no number, and no figure is derived from the cells", () => {
  const masquee = rendre(h(TableauLeadCycle, { points: reponse.teams[0].points, seuil: 5 }), "en");
  const premiereLigne = /<tbody><tr>([\s\S]*?)<\/tr>/.exec(masquee)?.[1] ?? "";
  assert.doesNotMatch(texte(premiereLigne.replace("Q1 2026", "")), /\d/);
});

// ---- the chart and the table share one data layer -------------------------------------------------------------------------------

test("the chart and the table read the same points: one chart container per scope, labelled, above the table", () => {
  const html = contenu("Team A");
  assert.equal((html.match(/class="graphique"/g) ?? []).length, 1);
  assert.ok(html.indexOf('class="graphique"') < html.indexOf("<table"));
  assert.match(html, /aria-label="Median lead time and cycle time per quarter"/);
});

// ---- make it a sheet ------------------------------------------------------------------------------------------------------------

test("the button carries the label of D29 in each language", () => {
  assert.equal(en["tableau.makeSheet"], "Make it a sheet");
  assert.equal(fr["tableau.makeSheet"], "En faire une fiche");
  assert.match(contenu(""), /<button type="button"[^>]*>Make it a sheet<\/button>/);
  assert.match(contenu("", "fr"), /<button type="button"[^>]*>En faire une fiche<\/button>/);
});

test("a sheet is never asked for the product scope: nothing is sent and the screen asks for a team", async () => {
  const demandes: unknown[] = [];
  const creer = async (demande: unknown) => {
    demandes.push(demande);
    return { id: "sim-1", state: "draft" as const };
  };
  const etat = await ouvrirBrouillon(creer, "", reponse.dataDate, "lead_cycle_h5");
  assert.deepEqual(demandes, []);
  assert.deepEqual(etat, { genre: "equipe_requise" });
  assert.match(texte(contenu("", "en", etat)), /Choose a team to make a sheet/);
});

test("a sheet of a team asks for this chart, the scope team.<opaque identifier> and the data date, never the team name, no verdict (D29, R-20261030-60)", async () => {
  const demandes: unknown[] = [];
  const creer = async (demande: unknown) => {
    demandes.push(demande);
    return { id: "sim-1", state: "draft" as const };
  };
  const scope = scopeFiche({ kind: "team", team: identifiantEquipe("Team A") });
  assert.match(scope, /^team\.[a-z0-9_-]{1,59}$/);
  assert.doesNotMatch(scope, /Team A/i);
  assert.deepEqual(await ouvrirBrouillon(creer, "Team A", reponse.dataDate, "lead_cycle_h1"), { genre: "brouillon", id: "sim-1" });
  assert.deepEqual(demandes.at(-1), { chart: "lead_cycle_h1", scope, dataDate: "2026-10-27" });
  assert.deepEqual(await ouvrirBrouillon(creer, "Team A", reponse.dataDate, "lead_cycle_h5"), { genre: "brouillon", id: "sim-1" });
  assert.deepEqual(demandes.at(-1), { chart: "lead_cycle_h5", scope, dataDate: "2026-10-27" });
  assert.equal(demandes.length, 2);
});

test("the form does not offer the product scope: on the product it asks for a team and the draft button stays disabled", () => {
  const produit = contenu("", "en", { genre: "formulaire" });
  assert.match(texte(produit), /Choose a team to make a sheet/);
  assert.match(produit, /<button type="submit"[^>]*disabled=""[^>]*>Create the draft<\/button>/);
  assert.match(texte(contenu("", "fr", { genre: "formulaire" })).replaceAll("&#x27;", "'"), /Choisissez une équipe/);
  assert.doesNotMatch(texte(contenu("Team A", "en", { genre: "formulaire" })), /Choose a team to make a sheet/);
  assert.notEqual(en["tableau.form.teamRequired"], fr["tableau.form.teamRequired"]);
});

test("the page imports the contract's values only through its two browser-safe subpaths, the team identifier and the lists", () => {
  const code = readFileSync(`${FRONT}src/pages/PageTableau.ts`, "utf8");
  assert.match(code, /from "@mothra\/contract\/equipe"/);
  assert.match(code, /from "@mothra\/contract\/listes-fiche"/);
  assert.doesNotMatch(code, /^import\s+(?!type\b)[^;]*from "@mothra\/contract"/m);
  // the whole front: every run-time import of a `@mothra/contract/...` subpath names one of the two
  const sousChemins = sources(FRONT, "src", [".ts", ".tsx"]).flatMap((s) =>
    [...s.contenu.matchAll(/^(?:import|export)\s+(?!type\b)[^;]*?from\s+["']@mothra\/contract\/([^"']+)["']/gm)].map((m) => m[1]),
  );
  assert.ok(sousChemins.length > 0);
  // `reponse` is the older subpath (the view answer), already browser-safe; no other one exists. `composition` (D3) is added by lot 3b: an entry
  // added to a closed list, R-20261101-40.
  assert.deepEqual([...new Set(sousChemins)].filter((c) => !["composition", "equipe", "listes-fiche", "reponse"].includes(c)), []);
});

// ---- the creation form: one button, the hypothesis chosen in the form (R-20261030-60, Q5.1) ----------------------------------------------

test("the closed list of the charts a sheet can be made of holds the two hypotheses, and the old chart name is gone", () => {
  assert.deepEqual([...GRAPHIQUES_FICHE], ["lead_cycle_h5", "lead_cycle_h1"]);
  assert.doesNotMatch(readFileSync(`${FRONT}src/pages/PageTableau.ts`, "utf8"), /FICHE_DEMANDEE|"lead_cycle"/);
});

test("there is one button 'make it a sheet': it opens the form, it does not create the draft", () => {
  const html = contenu("");
  assert.equal((html.match(/Make it a sheet/g) ?? []).length, 1);
  assert.doesNotMatch(texte(html), /Create the draft/);
  assert.deepEqual(ouvrirFormulaire(), { genre: "formulaire" });
});

test("the form offers the two hypotheses as radio buttons, none chosen, and the draft button is disabled until one is chosen, in each language", () => {
  const anglais = contenu("", "en", { genre: "formulaire" });
  assert.equal((anglais.match(/type="radio"/g) ?? []).length, 2);
  assert.doesNotMatch(anglais, /checked/);
  assert.match(anglais, /<fieldset/);
  assert.match(texte(anglais), /Conviction of the sheet/);
  assert.match(texte(/<fieldset[\s\S]*?<\/fieldset>/.exec(anglais)?.[0] ?? ""), /Work stays stable/);
  assert.match(texte(/<fieldset[\s\S]*?<\/fieldset>/.exec(anglais)?.[0] ?? ""), /Waiting dominates the lead time/);
  assert.match(anglais, /<button type="submit"[^>]*disabled=""[^>]*>Create the draft<\/button>/);
  const francais = texte(contenu("", "fr", { genre: "formulaire" })).replaceAll("&#x27;", "'");
  assert.match(francais, /Conviction de la fiche/);
  assert.match(texte(/<fieldset[\s\S]*?<\/fieldset>/.exec(contenu("", "fr", { genre: "formulaire" }))?.[0] ?? "").replaceAll("&#x27;", "'"), /L'attente domine le délai/);
  assert.match(francais, /Créer le brouillon/);
  for (const cle of ["tableau.form.legend", "conviction.nav.lead_cycle_h5", "conviction.nav.lead_cycle_h1", "tableau.form.create"] as const) {
    assert.ok(cle in en && cle in fr, cle);
    assert.notEqual(en[cle], fr[cle]);
  }
});

test("the form shows no verdict and no draft panel", () => {
  const html = contenu("", "en", { genre: "formulaire" });
  assert.doesNotMatch(texte(html), /confirmed|refuted|not settled|A draft sheet is open/);
});

test("a sheet is never requested without the date of its data", async () => {
  const demandes: unknown[] = [];
  const creer = async (demande: unknown) => {
    demandes.push(demande);
    return { id: "sim-1", state: "draft" as const };
  };
  for (const vide of ["", "   "]) assert.deepEqual(await ouvrirBrouillon(creer, "", vide, "lead_cycle_h5"), { genre: "erreur", code: "INTERNAL" });
  assert.deepEqual(demandes, []);
});

test("a refused request shows the translated internal error, never the raw failure", async () => {
  const etat = await ouvrirBrouillon(async () => {
    throw new Error("boom with /secret/path");
  }, "Team A", reponse.dataDate, "lead_cycle_h5");
  assert.deepEqual(etat, { genre: "erreur", code: "INTERNAL" });
  const html = contenu("", "en", etat);
  assert.match(html, /<p role="alert" class="page-erreur">Something went wrong\.<\/p>/);
  assert.doesNotMatch(html, /boom|secret/);
});

test("the simulated route answers a draft with a fixed identifier, and nothing is sent anywhere", async () => {
  const brouillon = await creerFicheSimulee({ chart: "lead_cycle_h5", scope: "product", dataDate: "2026-10-27" });
  assert.deepEqual(brouillon, { id: "simulated-draft-1", state: "draft" });
});

test("an open draft shows the draft state label and the simulated-route notice, in each language", () => {
  const anglais = texte(contenu("", "en", { genre: "brouillon", id: "simulated-draft-1" }));
  assert.match(anglais, /A draft sheet is open\./);
  assert.match(anglais, /draft/);
  assert.match(anglais, /Simulated route: nothing is saved\./);
  const francais = texte(contenu("", "fr", { genre: "brouillon", id: "simulated-draft-1" })).replaceAll("&#x27;", "'");
  assert.match(francais, /Un brouillon de fiche est ouvert\./);
  assert.match(francais, /brouillon/);
  assert.match(francais, /Route simulée : rien n'est enregistré\./);
  assert.doesNotMatch(texte(contenu("")), /A draft sheet is open/);
});

test("the draft panel announces itself to assistive technology and shows no verdict", () => {
  const html = contenu("", "en", { genre: "brouillon", id: "simulated-draft-1" });
  assert.match(html, /role="status"/);
  assert.doesNotMatch(texte(html), /confirmed|refuted|not settled/);
});

// ---- the page ---------------------------------------------------------------------------------------------------------------------

async function page(langue: Langue = "en", source: SourceLeadCycle = SOURCE_SIMULEE): Promise<string> {
  const client = new QueryClient();
  await client.prefetchQuery(optionsLeadCycle(source.lire));
  return renderToStaticMarkup(
    h(QueryClientProvider, { client }, h(IntlProvider, { locale: langue, messages: catalogues[langue] }, h(PageTableau, { source }))),
  );
}

// R-20261101-40 (Q156): the banner of the simulated data is the shell's; the page itself shows none, whatever the source.
test("the page shows no simulated-data banner of its own, with a real source or the simulated one", async () => {
  assert.doesNotMatch(await page("en", SOURCE_REELLE), /Simulated data/);
  assert.match(await page("en", SOURCE_REELLE), /<table/);
  assert.doesNotMatch(await page("en"), /Simulated data|role="note" class="banniere"/);
});

test("the page reads the dashboard data through the query cache and shows one section with title, chart, table and button", async () => {
  const html = await page();
  assert.equal((html.match(/<section/g) ?? []).length, 1);
  assert.match(html, /<h1[^>]*>Lead time against cycle time<\/h1>/);
  assert.equal((html.match(/<table/g) ?? []).length, 1);
  assert.equal((html.match(/class="graphique"/g) ?? []).length, 1);
  assert.match(html, /Make it a sheet/);
  assert.match(html, /Figures computed on fewer than 5 items are masked\./);
  assert.match(await page("fr"), /<h1[^>]*>Lead time contre cycle time<\/h1>/);
});

test("without data the page says it is loading, and shows no table and no chart", () => {
  const html = renderToStaticMarkup(
    h(QueryClientProvider, { client: new QueryClient() }, h(IntlProvider, { locale: "en", messages: en }, h(PageTableau, { source: SOURCE_SIMULEE }))),
  );
  assert.match(html, /<p role="status">Loading…<\/p>/);
  assert.doesNotMatch(html, /<table|graphique/);
});

// ---- reaching the second screen -------------------------------------------------------------------------------------------------

async function application(props: Parameters<typeof Application>[0]): Promise<string> {
  const client = new QueryClient();
  await client.prefetchQuery(optionsLeadCycle(lireLeadCycleSimule));
  return renderToStaticMarkup(h(QueryClientProvider, { client }, h(Application, { tableau: SOURCE_SIMULEE, ...props })));
}

// R-20261101-04: the link of the top navigation to "#/" is now the entry "Home" of the side navigation. R-20261101-28: the home no longer holds
// the status by team section; it is the home of the served convictions.
test("the shell reaches the dashboard from a link, the home stays the default screen", async () => {
  const defaut = await application({});
  assert.match(defaut, /<h1[^>]*>What the data say about our convictions<\/h1>/);
  assert.doesNotMatch(defaut, /Lead time against cycle time<\/h1>/);
  // The nav entry reads the new key nav.dashboard (R-20261101-80 Q187, R-20261101-68 Q161); the page title stays tableau.title.
  assert.match(defaut, /<a href="#\/tableau"[^>]*>Dashboard<\/a>/);
  assert.match(defaut, /<a href="#\/"[^>]*>Home<\/a>/);
  const tableau = await application({ ecranInitial: "tableau" });
  assert.match(tableau, /<h1[^>]*>Lead time against cycle time<\/h1>/);
  assert.doesNotMatch(tableau, /What the data say about our convictions/);
  assert.match(await application({ ecranInitial: "tableau", langueInitiale: "fr" }), /<h1[^>]*>Lead time contre cycle time<\/h1>/);
});

test("without an injected source the shell offers no link to the dashboard and shows the home", async () => {
  const sans = await application({ tableau: undefined, ecranInitial: "tableau" });
  assert.doesNotMatch(sans, /href="#\/tableau"/);
  assert.match(sans, /<h1[^>]*>What the data say about our convictions<\/h1>/);
});

test("the screen is chosen from the address fragment, an unknown fragment gives the skeleton page", () => {
  assert.equal(ecranDuHash("#/tableau"), "tableau");
  assert.equal(ecranDuHash(""), "squelette");
  assert.equal(ecranDuHash("#/autre"), "squelette");
});

// ---- catalogues and network --------------------------------------------------------------------------------------------------------

test("every key added for this screen lives under tableau.* and exists in both catalogues with the same parameters", () => {
  const cles = Object.keys(en).filter((k) => k.startsWith("tableau."));
  assert.ok(cles.length >= 15);
  for (const cle of cles) {
    assert.ok(cle in fr, `absente de fr.json : ${cle}`);
    assert.notEqual(en[cle].trim(), "");
  }
});

test("the new files make no network call and name no address", () => {
  const nouveaux = sources(FRONT, "src", [".ts"]).filter((s) =>
    ["src/api/leadCycle.ts", "src/simule/leadCycle.ts", "src/pages/PageTableau.ts", "src/composants/TableauLeadCycle.ts", "src/composants/Graphique.ts"].includes(s.nom),
  );
  assert.equal(nouveaux.length, 5);
  for (const s of nouveaux) assert.doesNotMatch(readFileSync(`${FRONT}${s.nom}`, "utf8").replace(/\/\/.*$/gm, ""), /\bfetch\b|XMLHttpRequest|["'`]\/api\//, s.nom);
});
