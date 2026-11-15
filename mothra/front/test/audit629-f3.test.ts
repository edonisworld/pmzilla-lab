// Audit #629, group F3, points 12, 13 and 21 of A-10 (delegated, decision of 2026-11-04: "lot d'après le 26/11"): the native forms dressed by the
// stylesheet alone, the "make it a sheet" button raised under the date line, one colour for the two key figures of hypothesis 5.
// Points 4, 5, 6, 7 and 22 of A-10 (decision of the author R-20261109-08, Q1 to Q5): one name per conviction, the validated texts, the
// throughput sentence, the column of the positions, the display form of the thresholds.
// The data come from the pure functions of the contract (`reponseComplete`, `ficheH5`, `ficheH1`), as in the neighbouring tests; the only texts
// written here are the table of the labels validated by the author (R-20261109-08 Q2) and the expected display of the thresholds.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { createIntl } from "react-intl";

import { TOUS_LES_CODES_SEUILS } from "@mothra/contract";
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";

import type { ReponseFiche } from "../src/api/fiche.ts";
import { CarteConviction } from "../src/composants/CarteConviction.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { FORMES_SEUILS, valeurSeuil } from "../src/composants/valeurSeuil.ts";
import { CLES_CONVICTION } from "../src/convictions.ts";
import { ContenuTableau } from "../src/pages/PageTableau.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { ficheH1 } from "./fiches-h1.ts";
import { ficheH5 } from "./fiches-h5.ts";
import { reponseComplete } from "./reponses-contrat.ts";
import { rendre, texte } from "./rendu.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

// The stylesheet without its comments, read as rules: the list of the selectors, then the declarations.
const CSS = readFileSync(`${FRONT}src/styles/styles.css`, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
const REGLES = [...CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
  selecteurs: m[1].split(",").map((s) => s.replace(/\s+/g, " ").trim()),
  declarations: m[2].replace(/\s+/g, " ").trim(),
}));

// The rule whose selector list holds `selecteur`.
function regleDe(selecteur: string): { selecteurs: string[]; declarations: string } {
  const trouvee = REGLES.find((r) => r.selecteurs.includes(selecteur));
  assert.ok(trouvee, `règle absente : ${selecteur}`);
  return trouvee;
}

// A value written in the rule instead of a token: a colour, a length in px or rem, a function other than var().
function enDur(declarations: string): string[] {
  return [...declarations.matchAll(/:\s*([^;]+)/g)].map((m) => m[1]).filter((v) => /#[0-9a-fA-F]{3,8}\b|\d+(?:\.\d+)?(?:px|rem|em)\b|\brgba?\(|\bhsla?\(/.test(v));
}

// ---- point 12: the native forms, dressed with the tokens ---------------------------------------------------------------------------

test("point 12: the fields, the fieldset, its legend and the radio buttons have common rules built from the existing tokens only", () => {
  const champs = regleDe('.page input[type="text"]');
  for (const s of ['.page select', '.page textarea', '.nav-bas select', '.nav-bas input[type="text"]']) assert.ok(champs.selecteurs.includes(s), s);
  for (const jeton of ["--border-width", "--color-border", "--radius", "--space-1", "--space-2", "--color-surface", "--color-text", "--font-family", "--font-size-base"]) {
    assert.ok(champs.declarations.includes(`var(${jeton})`), `jeton absent du champ : ${jeton}`);
  }
  assert.match(regleDe(".page fieldset").declarations, /border: var\(--border-width\) solid var\(--color-border\)/);
  assert.match(regleDe(".page fieldset").declarations, /border-radius: var\(--radius\)/);
  assert.match(regleDe(".page fieldset").declarations, /padding: var\(--space-3\)/);
  assert.match(regleDe(".page legend").declarations, /padding: 0 var\(--space-1\)/);
  // the label already spaces its radio button (gap of the `portee` line): the button carries no margin of its own, a size from the scale
  assert.match(regleDe('.page input[type="radio"]').declarations, /margin: 0;/);
  assert.match(regleDe('.page input[type="radio"]').declarations, /width: var\(--space-3\); height: var\(--space-3\)/);
  // the language list sits on the line of its label
  const langue = regleDe(".fiche-champ-langue").declarations;
  assert.match(langue, /display: flex/);
  assert.match(langue, /align-items: center/);
  assert.match(langue, /gap: var\(--space-2\)/);
});

test("point 12: the common form rules hold no value written in place of a token, and no colour but the declared pair text on surface", () => {
  for (const selecteur of ['.page input[type="text"]', ".page fieldset", ".page legend", '.page input[type="radio"]', ".fiche-champ-langue"]) {
    const { declarations } = regleDe(selecteur);
    assert.deepEqual(enDur(declarations), [], selecteur);
    for (const jeton of declarations.matchAll(/var\((--[a-z0-9-]+)\)/g)) assert.match(jeton[1], /^--(?:border-width|color-border|color-surface|color-text|radius|space-\d|font-family|font-size-base|font-size-small)$/, selecteur);
  }
});

test("point 12: no common form rule names the filter bar, whose rules may carry neither colour nor background (panneaux.test.ts)", () => {
  for (const selecteur of ['.page input[type="text"]', ".page fieldset", ".page legend", '.page input[type="radio"]', ".fiche-champ-langue"]) {
    assert.ok(!regleDe(selecteur).selecteurs.some((s) => s.includes("barre-filtres")), selecteur);
  }
});

// ---- point 13: the button under the date line --------------------------------------------------------------------------------------

function contenu(options: { dataDate?: string } = {}): string {
  const reponse = { ...reponseComplete(), ...options };
  return rendre(
    h(ContenuTableau, { reponse, portee: "", surPortee: () => undefined, fiche: { genre: "aucune" }, surFaire: () => undefined, surCreer: () => undefined, simulee: true }),
    "en",
  );
}

test("point 13: the button 'make it a sheet' is in the actions row, under the date line and before the chart, with the same class", () => {
  const html = contenu();
  const bouton = `<button type="button" class="bouton">${en["tableau.makeSheet"]}</button>`;
  assert.equal((html.match(new RegExp(en["tableau.makeSheet"], "g")) ?? []).length, 1);
  assert.ok(html.includes(`<div class="tableau-actions">${bouton}</div>`), "bouton absent de la rangée des actions");
  const rang = html.indexOf('<div class="tableau-actions">');
  assert.ok(html.indexOf('class="tableau-date"') < rang, "la ligne de date précède la rangée");
  assert.ok(rang < html.indexOf('class="graphique"'), "le bouton précède le graphique");
  assert.ok(rang < html.indexOf("<select"), "le bouton précède le sélecteur de périmètre");
  assert.ok(rang < html.indexOf("<table"), "le bouton précède le tableau");
});

test("point 13: without the date of the data the button stays in the row and stays disabled", () => {
  const html = contenu({ dataDate: "  " });
  assert.ok(html.includes(`<div class="tableau-actions"><button type="button" class="bouton" disabled="">${en["tableau.makeSheet"]}</button></div>`));
  assert.ok(html.indexOf('class="tableau-actions"') < html.indexOf('class="graphique"'));
});

// ---- point 21: one colour for the two key figures of hypothesis 5 ------------------------------------------------------------------

test("point 21: the median and the P85 of the cycle time, on the page of hypothesis 5, take the same colour rule", () => {
  const html = rendre(h(FicheConviction, { fiche: ficheH5("confirmed") }), "en");
  assert.match(html, /data-chiffre="cycle_median"/);
  assert.match(html, /data-chiffre="cycle_p85"/);
  const mediane = regleDe('.chiffre[data-chiffre="cycle_median"] .chiffre-valeur');
  const p85 = regleDe('.chiffre[data-chiffre="cycle_p85"] .chiffre-valeur');
  assert.equal(p85, mediane, "une seule règle pour les deux chiffres");
  assert.match(p85.declarations, /^color: var\(--color-data-work-strong\);?$/);
  assert.equal(p85.selecteurs[0], '.chiffre[data-chiffre="cycle_p85"] .chiffre-valeur', "placé en tête de la liste (habillage-fiche-h1.test.ts)");
});

// ---- R-20261109-08 -------------------------------------------------------------------------------------------------------------------

type Langue = "en" | "fr";

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

function fiche(f: ReponseFiche, props: Partial<Parameters<typeof FicheConviction>[0]> = {}, langue: Langue = "en"): string {
  return propre(rendre(h(FicheConviction, { fiche: f, ...props }), langue));
}

function pageTableau(genre: "aucune" | "formulaire", langue: Langue): string {
  const reponse = reponseComplete();
  return propre(rendre(h(ContenuTableau, { reponse, portee: "", surPortee: () => undefined, fiche: { genre }, surFaire: () => undefined, surCreer: () => undefined, simulee: true }), langue));
}

// The first fieldset of the form: the choices of the conviction, apart from the introduction of the dashboard, which holds the same names.
function champ(html: string): string {
  return /<fieldset[\s\S]*?<\/fieldset>/.exec(html)?.[0] ?? "";
}

// Q1 (a): one name per conviction, the one of the menu.
test("Q1 (a): the card, the form and the menu read one name per conviction, conviction.nav.*, and no other name is in a catalogue", () => {
  for (const [langue, catalogue] of Object.entries(catalogues)) {
    const restes = Object.keys(catalogue).filter((cle) => cle.startsWith("conviction.theme.") || cle === "tableau.form.h5" || cle === "tableau.form.h1");
    assert.deepEqual(restes, [], langue);
  }
  for (const genre of GRAPHIQUES_DE_FICHE) {
    assert.deepEqual(Object.keys(CLES_CONVICTION[genre]).sort(), ["enonce", "nav"], genre);
    for (const langue of ["en", "fr"] as const) {
      const nom = catalogues[langue][CLES_CONVICTION[genre].nav];
      assert.ok(propre(texte(rendre(h(CarteConviction, { genre }), langue))).includes(nom), `carte ${genre} ${langue}`);
      assert.ok(texte(champ(pageTableau("formulaire", langue))).includes(nom), `formulaire ${genre} ${langue}`);
    }
  }
});

// Q2: the five texts validated by the author, in English and in French.
const TEXTES_VALIDES: Record<string, { en: string; fr: string }> = {
  "tableau.hypothesis": { en: "These lead time and cycle time data serve two convictions: “{h5}” and “{h1}”.", fr: "Ces données de lead time et de cycle time servent deux convictions : « {h5} » et « {h1} »." },
  "tableau.form.legend": { en: "Conviction of the sheet", fr: "Conviction de la fiche" },
  "tableau.hypothesis.h1_second_half": { en: "Serves the question: inflow against outflow", fr: "Sert la question : entrées contre sorties" },
  "tableau.hypothesis.h3": { en: "Serves the question: quality per version", fr: "Sert la question : qualité par version" },
  "fiche.verdict.computed": {
    en: "Computed from the data and the thresholds set in advance; nobody enters it.",
    fr: "Calculé à partir des données et des seuils fixés à l'avance ; personne ne le saisit.",
  },
};

test("Q2: the five validated texts are in both catalogues, and the introduction of the dashboard names the two convictions by their one name", () => {
  for (const [cle, attendu] of Object.entries(TEXTES_VALIDES)) {
    assert.equal(en[cle], attendu.en, `en ${cle}`);
    assert.equal(fr[cle], attendu.fr, `fr ${cle}`);
  }
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const phrase = TEXTES_VALIDES["tableau.hypothesis"][langue].replace("{h5}", c["conviction.nav.lead_cycle_h5"]).replace("{h1}", c["conviction.nav.lead_cycle_h1"]);
    assert.ok(texte(pageTableau("aucune", langue)).includes(phrase), langue);
  }
});

test("Q2 (a): the footer of a sheet holds no line of the hypothesis served, and the number of the hypothesis stays on the method face", () => {
  for (const [genre, f, lien] of [
    ["lead_cycle_h5", ficheH5("confirmed"), "fiche.link.h5"],
    ["lead_cycle_h1", ficheH1("confirmed"), "fiche.link.h1_first_half"],
  ] as const) {
    for (const langue of ["en", "fr"] as const) {
      const c = catalogues[langue];
      const html = fiche(f, { methodeOuverte: true, seuilMasquage: 5 }, langue);
      const pied = /<footer[\s\S]*<\/footer>/.exec(html)?.[0] ?? "";
      assert.ok(texte(pied).includes(c["conviction.footer.masking"].replace("{threshold}", "5")), `${genre} ${langue}: le pied est celui du masquage`);
      assert.ok(!texte(pied).includes(c[lien]), `${genre} ${langue}`);
      assert.equal("conviction.footer.hypothesis" in c, false);
      assert.ok(texte(html).includes(c["fiche.method.hypothesis"]) && texte(html).includes(c[lien]), `${genre} ${langue}: le numéro reste sur la face méthode`);
    }
  }
});

// Q3: the throughput sentence of the key figures holds the period and the position, no repeated word.
test("Q3: the throughput line of the card of hypothesis 5 is the period, then the position, in both languages", () => {
  assert.equal(en["conviction.h5.figure.throughput"], "{period}: {position}");
  assert.equal(fr["conviction.h5.figure.throughput"], "{period} : {position}");
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const html = fiche(ficheH5("confirmed"), {}, langue);
    const ligne = /<p class="chiffre-debit"[^>]*>([^<]*)<\/p>/.exec(html)?.[1] ?? "";
    assert.equal(ligne, c["conviction.h5.figure.throughput"].replace("{period}", langue === "en" ? "Q3 2026" : "T3 2026").replace("{position}", c["fiche.position.throughput_within_band"]), langue);
  }
});

// Q4: the head of the column of the positions says what it holds.
test("Q4: the last column of the stability table is headed by the new key, the measure key stays for the method face", () => {
  assert.equal(en["fiche.column.throughputPosition"], "Throughput against the floors");
  assert.equal(fr["fiche.column.throughputPosition"], "Débit face aux planchers");
  assert.equal(en["fiche.measure.throughput"], "Throughput");
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const html = fiche(ficheH5("confirmed"), {}, langue);
    const tete = /<thead>[\s\S]*?<\/thead>/.exec(html.slice(html.indexOf('data-tableau="stabilite"')))?.[0] ?? "";
    assert.ok(tete.endsWith(`<th scope="col">${c["fiche.column.throughputPosition"]}</th></tr></thead>`), langue);
    assert.ok(!tete.includes(`<th scope="col">${c["fiche.measure.throughput"]}</th>`), langue);
  }
  assert.equal(Object.keys(en).filter((k) => /^conviction\.h5\./.test(k)).length, 6, "no new key in the space conviction.h5.*");
});

// Q5: the display form of the thresholds, the stored value unchanged.
const EN_SEUILS: Record<string, string> = {
  h5_band: "±20%",
  h5_double_band: "±40%",
  h5_run_rises: "2",
  h5_run_min_cumulative_rise: "10%",
  h5_floor: "80%",
  h5_low_floor: "60%",
  h1_lower: "1.5×",
  h1_upper: "3×",
  attachment_threshold_points: "10",
  sample_median_min_items: "10",
  sample_p85_min_items: "20",
};

function valeurAffichee(html: string, code: string, langue: Langue): string | undefined {
  const table = /<table[^>]*data-tableau="seuils"[\s\S]*?<\/table>/.exec(html)?.[0] ?? "";
  const libelle = catalogues[langue][`fiche.threshold.${code}`];
  const ligne = [...table.matchAll(/<tr[\s\S]*?<\/tr>/g)].map((m) => m[0]).find((l) => texte(l).includes(libelle));
  return ligne === undefined ? undefined : /<td class="cellule cellule-valeur">([^<]*)<\/td>/.exec(ligne)?.[1];
}

test("Q5: the table of the display forms is closed on the thresholds of the contract, with the same keys (source: the contract)", () => {
  assert.deepEqual(Object.keys(FORMES_SEUILS).sort(), [...TOUS_LES_CODES_SEUILS].sort());
  assert.deepEqual(Object.keys(EN_SEUILS).sort(), [...TOUS_LES_CODES_SEUILS].sort());
});

test("Q5: valeurSeuil writes the band as a signed percentage, the floors as percentages, the bounds as ratios, the counts as numbers", () => {
  const intl = createIntl({ locale: "en", messages: en });
  const intlFr = createIntl({ locale: "fr", messages: fr });
  assert.equal(valeurSeuil(intl, "h5_band", 0.2), "±20%");
  assert.equal(valeurSeuil(intl, "h5_floor", 0.8), "80%");
  assert.equal(valeurSeuil(intl, "h1_lower", 1.5), "1.5×");
  // one decimal at most (skeleton `::percent .#` of the catalogues), as habillage-fiche-h5.test.ts computes it
  assert.equal(valeurSeuil(intl, "h5_floor", 0.125), "12.5%");
  assert.equal(valeurSeuil(intlFr, "h5_floor", 0.125), new Intl.NumberFormat("fr", { style: "percent", maximumFractionDigits: 1 }).format(0.125));
  assert.equal(valeurSeuil(intl, "sample_p85_min_items", 20), "20");
  assert.equal(valeurSeuil(intl, "a_code_the_table_does_not_know", 0.2), "0.2", "an unknown code shows the number");
  assert.equal(valeurSeuil(intlFr, "h1_lower", 1.5), "1,5×");
  assert.equal(valeurSeuil(intlFr, "h5_band", 0.2), `±${new Intl.NumberFormat("fr", { style: "percent" }).format(0.2)}`);
});

test("Q5: the method face and the card of hypothesis 5 show the thresholds in that form, and the stored values stay the fractions", () => {
  const f = ficheH5("confirmed");
  const stockees = Object.fromEntries(f.method.thresholds.map((s) => [s.code, s.value]));
  assert.equal(stockees["h5_band"], 0.2);
  assert.equal(stockees["h5_double_band"], 0.4);
  assert.equal(stockees["h5_floor"], 0.8);
  assert.equal(stockees["h5_low_floor"], 0.6);
  assert.equal(stockees["h5_run_min_cumulative_rise"], 0.1);
  const html = fiche(f, { methodeOuverte: true });
  assert.ok(f.method.thresholds.length > 0);
  for (const { code } of f.method.thresholds) assert.equal(valeurAffichee(html, code, "en"), EN_SEUILS[code], code);
  const h1 = ficheH1("confirmed");
  assert.equal(h1.method.thresholds.find((s) => s.code === "h1_lower")?.value, 1.5);
  const htmlH1 = fiche(h1, { methodeOuverte: true });
  assert.equal(valeurAffichee(htmlH1, "h1_lower", "en"), "1.5×");
  assert.equal(valeurAffichee(htmlH1, "h1_upper", "en"), "3×");
  for (const { code } of h1.method.thresholds) assert.equal(valeurAffichee(htmlH1, code, "en"), EN_SEUILS[code], code);
  const carte = texte(/<section class="carte carte-preuve"[\s\S]*?<\/section>/.exec(html)?.[0] ?? "");
  assert.ok(carte.includes(en["conviction.h5.band"].replace("{band}", "±20%").replace("{doubleBand}", "±40%")));
  assert.ok(carte.includes(en["conviction.h5.floor"].replace("{floor}", "80%").replace("{lowFloor}", "60%")));
  const francais = fiche(f, { methodeOuverte: true }, "fr");
  const pourcent = (v: number): string => new Intl.NumberFormat("fr", { style: "percent" }).format(v);
  assert.equal(valeurAffichee(francais, "h5_floor", "fr"), pourcent(0.8));
  assert.equal(valeurAffichee(fiche(h1, { methodeOuverte: true }, "fr"), "h1_lower", "fr"), "1,5×");
});

test("Q5: the line of a threshold modified after reading writes the former value in the same form", () => {
  const f = ficheH5("confirmed");
  const modifiee = {
    ...f,
    method: {
      ...f.method,
      thresholds: f.method.thresholds.map((s) =>
        s.code === "h5_band" || s.code === "sample_median_min_items" ? { ...s, modifiedAfterReading: { formerValue: s.code === "h5_band" ? 0.3 : 20, formerDate: "2026-10-28" } } : s,
      ),
    },
  } as ReponseFiche;
  const lignes = [...fiche(modifiee, { methodeOuverte: true }).matchAll(/<p class="fiche-seuil-modifie">([^<]*)<\/p>/g)].map((m) => m[1]);
  assert.deepEqual([...lignes].sort(), ["Threshold modified after reading: former value 20, fixed on Oct 28, 2026", "Threshold modified after reading: former value ±30%, fixed on Oct 28, 2026"].sort());
});
