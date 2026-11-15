// Design review, pass 1 (R-20261104-42; points 1, 3, 8, 11, 14, 25, 26 and Q4 of point 18): the catalogue capitals, the stacked mentions, the French
// threshold wording, the shell and the bottom field of the navigation, the accessible names, the card link, the headings, the pooled-year point.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";

import { CarteConviction } from "../src/composants/CarteConviction.ts";
import { ChampIdentifiant } from "../src/composants/ChampIdentifiant.ts";
import { Mentions } from "../src/composants/FicheMentions.ts";
import { NavigationLaterale } from "../src/composants/NavigationLaterale.ts";
import { construireOptions } from "../src/composants/optionsGraphique.ts";
import type { Libelles, Palette, Style } from "../src/composants/optionsGraphique.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { reponseComplete } from "./reponses-contrat.ts";
import { rendre, texte } from "./rendu.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const CSS = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
const en = catalogues.en;
const fr = catalogues.fr;

// The declarations of the rule whose selector list is exactly `selecteur`.
function regle(selecteur: string): string {
  const echappe = selecteur.replace(/[.*+?^${}()|[\]\\>]/g, "\\$&");
  const trouvee = new RegExp(`(?:^|\\})\\s*${echappe}\\s*\\{([^}]*)\\}`, "m").exec(CSS);
  assert.ok(trouvee, `règle absente : ${selecteur}`);
  return trouvee[1].replace(/\s+/g, " ").trim();
}

// ---- point 1: the capital of the stand-alone texts ------------------------------------------------------------------------------

const TEXTES: Record<string, [string, string]> = {
  "tableau.makeSheet": ["Make it a sheet", "En faire une fiche"],
  "tableau.state.draft": ["Draft", "Brouillon"],
  "fiche.state.draft": ["Draft", "Brouillon"],
  "fiche.state.reviewed": ["Reviewed", "Relue"],
  "fiche.state.published": ["Published", "Publiée"],
  "fiche.syntheticNotice": ["On the synthetic dataset, not on real data.", "Sur le jeu synthétique, pas sur des données réelles."],
  "tableau.signal.served_scope_differs": ["Shown for the product: this panel has no team view.", "Affiché pour le produit : ce panneau n'a pas de vue par équipe."],
  "fiche.throughputOwnPastOnly": ["A team's throughput compares only with its own past.", "Le débit d'une équipe ne se compare qu'à son propre passé."],
  "app.identity.help": ["Pseudonym or role, not a person's name.", "Pseudonyme ou rôle, pas de nom de personne."],
  "fiche.text.missing": ["Not provided yet", "À renseigner"],
  "fiche.form.question.none": ["Not chosen yet", "À choisir"],
  "tableau.hypothesis.h1_second_half": ["Serves the question: inflow against outflow", "Sert la question : entrées contre sorties"],
  "tableau.hypothesis.h3": ["Serves the question: quality per version", "Sert la question : qualité par version"],
  "tableau.hypothesis.dependencies_explanation": ["Competing explanation: dependencies", "Explication concurrente : dépendances"],
  "fiche.explanationState.ruled_out": ["Ruled out", "Écartée"],
  "fiche.explanationState.not_ruled_out": ["Not ruled out", "Non écartée"],
  "fiche.explanationState.not_measurable": ["Not measurable", "Non mesurable"],
};

test("point 1: each stand-alone text of the closed list has the text of the design review, with a capital first letter, in both languages", () => {
  for (const [cle, [anglais, francais]] of Object.entries(TEXTES)) {
    assert.equal(en[cle], anglais, `en ${cle}`);
    assert.equal(fr[cle], francais, `fr ${cle}`);
    for (const message of [en[cle], fr[cle]]) {
      const [premier] = message;
      assert.ok(premier === premier.toUpperCase() && premier !== premier.toLowerCase(), `majuscule initiale : ${cle}`);
    }
  }
  assert.equal(Object.keys(TEXTES).length, 17);      // 18 before the removal of the truncated-quarter flag text (R-20261114-49, design D9)
});

test("point 1: the key sets are unchanged by the capitals, and the masked state and the position texts are left as they were", () => {
  assert.deepEqual(Object.keys(en).sort(), Object.keys(fr).sort());
  assert.equal(en["cellState.masked"], "masked");
  assert.equal(fr["cellState.masked"], "masqué");
  for (const cle of Object.keys(en).filter((k) => k.startsWith("fiche.position."))) {
    for (const t of [en[cle], fr[cle]]) assert.equal(t[0], t[0].toLowerCase(), `position modifiée : ${cle}`);
  }
});

// ---- point 3: the mentions stack, a space between two small texts ---------------------------------------------------------------

test("point 3: the mentions are a flex column with a space-1 gap, and a mention in a cell is a block", () => {
  const colonne = regle(".fiche-mentions");
  assert.match(colonne, /display: flex/);
  assert.match(colonne, /flex-direction: column/);
  assert.match(colonne, /gap: var\(--space-1\)/);
  assert.match(regle(".cellule .fiche-mention"), /display: block/);
});

test("point 3: two mentions are separated by a space, one mention has none", () => {
  const deux = rendre(h(Mentions, { codes: ["blocked_share_current_links", "indirect_indicator"] }), "en");
  assert.match(deux, /<\/small> <small[^>]*data-mention="indirect_indicator"/);
  assert.doesNotMatch(deux, /<\/small><small/);
  const une = rendre(h(Mentions, { codes: ["cycle_time_includes_ready_queue"] }), "en");
  assert.doesNotMatch(une, /<\/small> |> </);
});


// ---- point 8: the French threshold footer ---------------------------------------------------------------------------------------

// A-16 (a), R-20261107-33: the footer lines of the thresholds are withdrawn (the thresholds stay on the method face), so is their key.
test("point 8: the threshold footer line of the conviction page is withdrawn, in both languages (A-16 (a))", () => {
  assert.equal("conviction.footer.threshold" in fr, false);
  assert.equal("conviction.footer.threshold" in en, false);
});

// ---- point 11: the shell height and the field in the bottom of the navigation -------------------------------------------------------

test("point 11: the shell is at least one viewport high, through a token, and the bottom field stays in the bar", () => {
  const jetons = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as { scales: Record<string, string> } & Record<string, unknown>;
  assert.match(regle(".coquille"), /min-height: var\(--shell-min-height\)/);
  assert.match(readFileSync(`${FRONT}src/styles/tokens.css`, "utf8"), /--shell-min-height: 100vh;/);
  assert.ok(JSON.stringify(jetons).includes('"shell-min-height": "100vh"') || JSON.stringify(jetons).includes('"shell-min-height":"100vh"'));
  const champ = regle(".nav-bas input");
  assert.match(champ, /width: 100%/);
  assert.match(champ, /min-width: 0/);
  assert.match(champ, /box-sizing: border-box/);
});

// ---- point 25: accessible names ------------------------------------------------------------------------------------------------

function liens(html: string): string[] {
  return [...html.matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)].map((m) => texte(m[1]).trim());
}

// The accessible name of each link: its text, plus the alt of the images it holds.
function nomsDesLiens(html: string): string[] {
  return [...html.matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)].map((m) => (texte(m[1]).trim() + " " + [...m[1].matchAll(/<img\b[^>]*\balt="([^"]*)"/g)].map((i) => i[1]).join(" ")).trim());
}

test("point 25: the identifier field has an explicit id, its label points to it, and the label has a text", () => {
  for (const langue of ["en", "fr"] as const) {
    const html = rendre(h(ChampIdentifiant, { lire: () => undefined, ecrire: () => "saved" as const }), langue);
    const pour = /<label\b[^>]*\bfor="([^"]+)"/.exec(html)?.[1];
    const id = /<input\b[^>]*\bid="([^"]+)"/.exec(html)?.[1];
    assert.ok(pour !== undefined && id !== undefined, `for et id explicites (${langue})`);
    assert.equal(pour, id);
    assert.equal(html.split(`id="${id}"`).length - 1, 1, "l'identifiant est unique");
    assert.ok(texte(/<label\b[^>]*>([\s\S]*?)<input/.exec(html)?.[1] ?? "").trim().length > 0, "le libellé a un texte");
    assert.match(html, /aria-describedby="[^"]+"/);
  }
});

test("point 25: every link of the card and of the navigation has an accessible name", () => {
  for (const langue of ["en", "fr"] as const) {
    for (const genre of ["lead_cycle_h1", "lead_cycle_h5"] as const) {
      const noms = liens(rendre(h(CarteConviction, { genre }), langue));
      assert.equal(noms.length, 1);
      assert.ok(noms[0].length > 0);
    }
    const nav = rendre(
      h(NavigationLaterale, { accueilCourant: true, convictions: [{ genre: "lead_cycle_h1", courante: false }], tableau: { courant: false } }),
      langue,
    );
    const noms = nomsDesLiens(nav);
    assert.equal(noms.length, 4);
    for (const nom of noms) assert.ok(nom.length > 0, "lien sans nom");
    assert.match(nav, /<a[^>]*><img[^>]*\balt="[^"]+"/);
  }
});

// ---- point 26: the card link ----------------------------------------------------------------------------------------------------

test("point 26: the conviction card shows the text link of conviction.open, with hover and focus states from the tokens", () => {
  for (const langue of ["en", "fr"] as const) {
    for (const genre of ["lead_cycle_h1", "lead_cycle_h5"] as const) {
      const html = rendre(h(CarteConviction, { genre }), langue);
      assert.ok(texte(html).includes(catalogues[langue]["conviction.open"]), `${genre} ${langue}`);
      assert.equal(liens(html).length, 1, "le lien reste un seul lien, sans lien imbriqué");
    }
  }
  assert.match(CSS, /\.carte-conviction:hover/);
  assert.match(CSS, /\.carte-conviction:focus-visible/);
  assert.match(regle(".carte-lien"), /color: var\(--color-accent-text\)/);
});

// ---- point 14 (CSS alone): the page headings -----------------------------------------------------------------------------------

test("point 14: the h1 of a page and the title of the dashboard page use the heading face", () => {
  assert.match(regle("h1,\n.page > h2"), /font-family: var\(--font-family-heading\)/);
});

// ---- Q4 (point 18): the pooled year is an isolated point -----------------------------------------------------------------------

const PALETTE = Object.fromEntries(
  ["text", "textMuted", "border", "surface", "leadSeries", "cycleSeries", "maskedText", "maskedBackground", "maskedBorder", "insufficientBorder", "insufficientText"].map((k) => [k, `P-${k}`]),
) as unknown as Palette;
const STYLE: Style = {
  maskedBorderStyle: "S1",
  insufficientBorderStyle: "S2",
  maskedFontStyle: "S3",
  insufficientFontStyle: "S4",
  insufficientBackground: "S5",
  borderWidth: 7,
  seriesWidth: 5,
  fontFamily: "F",
  fontSize: 13,
};
const LIBELLES: Libelles = { lead: "LEAD", cycle: "CYCLE", axis: "AXIS", masked: "M", insufficient: "I", quarter: (brut) => `Q<${brut}>` };
test("Q4, on the contract's data: the pooled year follows one empty category, with no value in it, and the marked quarters keep their category", () => {
  for (const equipe of reponseComplete().teams.slice(0, 2)) {
    const points = equipe.points;
    const rang = points.findIndex((p) => p.quarter === "pooled_year");
    assert.equal(rang, points.length - 1);
    assert.ok(rang > 0);
    const options = construireOptions(points, LIBELLES, PALETTE, STYLE) as { xAxis: { data: string[] }; series: Array<{ type: string; data: unknown[]; connectNulls?: boolean }> };
    assert.deepEqual(options.xAxis.data, [...points.slice(0, rang).map((p) => `Q<${p.quarter}>`), "", "Q<pooled_year>"]);
    for (const serie of options.series.filter((s) => s.type === "line")) {
      assert.equal(serie.data.length, points.length + 1);
      assert.equal(serie.data[rang], null);
      assert.notEqual(serie.connectNulls, true);
    }
    const marques = options.series.find((s) => s.type === "custom");
    for (const [place] of (marques?.data ?? []) as number[][]) assert.notEqual(options.xAxis.data[place], "", "une bande sur la catégorie vide");
    const sans = construireOptions(points.slice(0, rang), LIBELLES, PALETTE, STYLE) as { xAxis: { data: string[] } };
    assert.deepEqual(sans.xAxis.data, points.slice(0, rang).map((p) => `Q<${p.quarter}>`));
  }
  assert.equal(reponseComplete().teams[1].points.at(-1)?.lead.state, "masked");
});
