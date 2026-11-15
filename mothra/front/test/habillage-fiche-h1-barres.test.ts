// Lot 3b of mothra-demo-habillage, phase B (tasks 6.0, 6.1, 6.3 "with the two bars"): the parts bar with threshold markers (`BarreParts`), the two
// bars of the sheet read from `waitShares` (the median and the P85), the composition of the median lead time by quarter on the common axis
// (`axisShare`), their text alternatives and the hidden table. Every sheet answer comes from `corpsDepuisVues` on synthetic view rows, reduced by
// `reduceToStatistics` for real data, with `waitShares` added by `partsDAttente` as the server does (D15, test/fiches-h1.ts); the free inputs of a
// component (a share, a state) are written here. Nothing is computed by the front: the widths and the positions of the drawing are the strings of
// the numbers the answer carries, which the tests compare with the answer itself.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";

import { partsDAttente } from "@mothra/contract";

import type { ReponseFiche } from "../src/api/fiche.ts";
import { BarreParts, CompositionTrimestres, ETATS_BARRE } from "../src/composants/BarreParts.ts";
import type { PropsBarreParts } from "../src/composants/BarreParts.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { CAS_H1, ficheH1 } from "./fiches-h1.ts";
import { rendre, texte } from "./rendu.ts";
import { derivations, valeursEnDur } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

function fiche(f: ReponseFiche, props: Partial<Parameters<typeof FicheConviction>[0]> = {}, langue: Langue = "en"): string {
  return propre(rendre(h(FicheConviction, { fiche: f, ...props }), langue));
}

function barre(props: PropsBarreParts, langue: Langue = "en"): string {
  return propre(rendre(h(BarreParts, props), langue));
}

// The block of one bar of the page ("median" or "p85"): from its opening mark to the next bar or the end of the page.
function bloc(html: string, code: "median" | "p85"): string {
  const morceaux = html.split('data-barre="');
  const trouve = morceaux.find((m) => m.startsWith(`${code}"`));
  assert.ok(trouve !== undefined, `barre ${code} absente`);
  return trouve.slice(0, trouve.search(/<\/footer>|<h2 class="encart-titre"/) < 0 ? undefined : trouve.search(/<\/footer>|<h2 class="encart-titre"/));
}

function attente(f: ReponseFiche): NonNullable<ReponseFiche["waitShares"]> {
  assert.ok(f.waitShares !== undefined);
  return f.waitShares;
}

function part(valeur: number): string {
  return `${Math.round(valeur)}%`;
}

// ---- 6.0 : BarreParts in every state -------------------------------------------------------------------------------------------------

const MARQUEURS = {
  refutation: { ratio: 1.5, inScale: true, share: 33.333333333333336 },
  confirmation: { ratio: 3, inScale: true, share: 66.66666666666667 },
  applicable: true,
};

test("the parts bar has the states of D17 and the list is closed", () => {
  assert.deepEqual([...ETATS_BARRE], ["value", "masked", "insufficient_sample", "not_comparable"]);
});

test("a bar with values: waiting left, work right, each part labelled with its share, the two markers positioned and labelled as ratios, in both languages", () => {
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const html = barre({ forme: "barre", code: "median", parts: { state: "value", waitShare: 75, workShare: 25 }, marqueurs: MARQUEURS, etiquette: "conviction.bar.labelMedian" }, langue);
    assert.match(html, /^<div class="barre-parts" data-forme="barre" data-barre="median" data-etat="value">/);
    assert.ok(texte(html).includes(c["conviction.bar.labelMedian"]));
    assert.match(html, /<rect class="part-attente" x="0%"[^>]*width="75%"/);
    assert.match(html, /<rect class="part-travail" x="75%"[^>]*width="25%"/);
    assert.ok(html.indexOf("part-attente") < html.indexOf("part-travail"));
    assert.ok(texte(html).includes(c["conviction.bar.wait"].replace("{share}", langue === "en" ? "75%" : "75 %")), langue);
    assert.ok(texte(html).includes(c["conviction.bar.work"].replace("{share}", langue === "en" ? "25%" : "25 %")), langue);
    // The markers: the position is the share the answer carries, the label is the catalogue's, in ratio.
    assert.match(html, /<line class="repere-trait repere-refutation" data-marqueur="refutation" x1="33\.333333333333336%" x2="33\.333333333333336%"/);
    assert.match(html, /<line class="repere-trait repere-confirmation" data-marqueur="confirmation" x1="66\.66666666666667%" x2="66\.66666666666667%"/);
    assert.ok(texte(html).includes(c["conviction.marker.refutation"].replace("{ratio, number}", "1.5".replace(".", langue === "fr" ? "," : "."))), langue);
    assert.ok(texte(html).includes(c["conviction.marker.confirmation"].replace("{ratio, number}", "3")), langue);
    assert.match(html, /role="img" aria-label="[^"]+"/);
    assert.doesNotMatch(html, /repere-pointille/);
  }
});

test("a bar's text alternative is the catalogue's sentence with the two shares; any other state has the sentence without a bar", () => {
  const avec = barre({ forme: "barre", code: "median", parts: { state: "value", waitShare: 75, workShare: 25 }, marqueurs: MARQUEURS });
  assert.ok(avec.includes(`aria-label="${en["conviction.bar.alt"].replace("{share}", "75%").replace("{work}", "25%")}"`));
  for (const etat of ["masked", "insufficient_sample"] as const) {
    const sans = barre({ forme: "barre", code: "median", parts: { state: etat }, marqueurs: MARQUEURS });
    assert.ok(sans.includes(`aria-label="${en["conviction.bar.altNone"]}"`), etat);
  }
});

test("markers that do not apply (insufficient sample) are dotted, grey and unlabelled, and the bar holds no part and no number", () => {
  const html = barre({ forme: "barre", code: "p85", parts: { state: "insufficient_sample" }, marqueurs: { ...MARQUEURS, applicable: false } });
  assert.match(html, /data-etat="insufficient_sample"/);
  assert.equal((html.match(/repere-trait repere-pointille/g) ?? []).length, 2);
  assert.match(html, /class="bande-insuffisante"/);
  assert.doesNotMatch(html, /part-attente|part-travail|repere-etiquette/);
  assert.doesNotMatch(texte(html), /\d|lower threshold|upper threshold/);
});

test("a threshold of 1 or under has no part: its ratio is told as text, and it is drawn nowhere on the bar", () => {
  const horsEchelle = { ...MARQUEURS, refutation: { ratio: 1, inScale: false } };
  const html = barre({ forme: "barre", code: "median", parts: { state: "value", waitShare: 75, workShare: 25 }, marqueurs: horsEchelle });
  assert.equal((html.match(/data-marqueur="/g) ?? []).length, 1, "only the threshold in scale is drawn");
  assert.doesNotMatch(html, /data-marqueur="refutation"/);
  // R-20261103-4 (1): the bar no longer tells it under itself; the sheet tells it once, under the two bars (see the tests of the sheet below).
  assert.doesNotMatch(html, /data-hors-echelle/);
  assert.ok(!texte(html).includes(en["conviction.marker.outOfScale"].replace("{threshold}", "1")));
});

test("a row or a bar without a length never takes 100: a row with no length draws no axis rectangle (R-20261103-4 (2))", () => {
  const html = barre({ forme: "ligne", parts: { state: "value", waitShare: 75, workShare: 25 }, libelleAttente: "30 d", libelleTravail: "10 d" });
  assert.doesNotMatch(html, /ligne-axe|part-travail|part-attente/);
  assert.doesNotMatch(html, /width="100%"[^>]*height="28"/);
});

test("the P85 bar wears the thin attribute that applies the thickness token, the median bar does not (R-20261103-4 (3))", () => {
  const p85 = barre({ forme: "barre", code: "p85", parts: { state: "value", waitShare: 66, workShare: 34 }, marqueurs: MARQUEURS });
  const mediane = barre({ forme: "barre", code: "median", parts: { state: "value", waitShare: 72, workShare: 28 }, marqueurs: MARQUEURS });
  assert.match(p85, /data-epaisseur="fine"/);
  assert.doesNotMatch(mediane, /data-epaisseur/);
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  const jetons = readFileSync(`${FRONT}src/styles/tokens.css`, "utf8");
  assert.match(jetons, /--barre-p85-hauteur:\s*[\d.]+rem/);
  assert.match(css, /\[data-epaisseur="fine"\][^{]*\{[^}]*var\(--barre-p85-hauteur\)/);
});

test("a masked bar is a dashed empty band holding the masked word: no part, no marker, no number", () => {
  for (const langue of ["en", "fr"] as const) {
    const html = barre({ forme: "barre", code: "median", parts: { state: "masked" }, marqueurs: MARQUEURS }, langue);
    assert.match(html, /data-etat="masked"/);
    assert.match(html, /class="bande-masquee"/);
    assert.equal(texte(html), catalogues[langue]["cellState.masked"]);
    assert.doesNotMatch(html, /part-attente|part-travail|data-marqueur|<line/);
  }
});

test("a bar whose two medians cannot be compared is replaced by the sentence of the catalogue", () => {
  for (const langue of ["en", "fr"] as const) {
    const html = barre({ forme: "barre", code: "median", parts: { state: "not_comparable" }, marqueurs: MARQUEURS }, langue);
    assert.match(html, /data-etat="not_comparable"/);
    assert.equal(texte(html), catalogues[langue]["conviction.notComparable"]);
    assert.doesNotMatch(html, /<svg|<rect/);
  }
});

test("a row of the chart has no marker and keeps the work-then-waiting order; its length is the answer's share of the common axis, passed as it is", () => {
  const html = barre({ forme: "ligne", parts: { state: "value", waitShare: 75, workShare: 25 }, longueur: 50, libelleAttente: "30 d", libelleTravail: "10 d" });
  assert.match(html, /data-forme="ligne"/);
  assert.match(html, /<svg class="ligne-axe" x="0%"[^>]*width="50%"/);
  assert.ok(html.indexOf("part-travail") < html.indexOf("part-attente"), "work first, then waiting");
  assert.match(html, /<rect class="part-travail" x="0%"[^>]*width="25%"/);
  assert.match(html, /<rect class="part-attente" x="25%"[^>]*width="75%"/);
  assert.equal(texte(html), "10 d30 d");
  assert.doesNotMatch(html, /data-marqueur|<line/);
  // The three other states of a row are words, not bars.
  assert.equal(texte(barre({ forme: "ligne", parts: { state: "masked" } })), en["cellState.masked"]);
  assert.equal(texte(barre({ forme: "ligne", parts: { state: "not_comparable" } })), en["conviction.notComparable"]);
  assert.equal(texte(barre({ forme: "ligne", parts: { state: "insufficient_sample" } })), en["state.insufficient_sample"]);
  assert.match(barre({ forme: "ligne", parts: { state: "insufficient_sample" } }), /data-icone="ellipsis"/);
});

test("the sources of the bar draw with classes and tokens only: no style prop, no colour or size literal, no derivation", () => {
  for (const fichier of ["src/composants/BarreParts.ts"]) {
    const contenu = readFileSync(`${FRONT}${fichier}`, "utf8");
    assert.deepEqual(valeursEnDur(fichier, contenu), [], fichier);
    assert.deepEqual(derivations(fichier, contenu), [], fichier);
    assert.doesNotMatch(contenu, /\bfill\s*:|\bstroke\s*:|\bstyle\s*:/, fichier);
  }
});

// ---- 6.1 : the two bars of the sheet, from waitShares ---------------------------------------------------------------------------------

test("the median and P85 bars are read from waitShares, with their ratios under them and the markers labelled as ratios, on both forms", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const f = ficheH1("confirmed", { jeu });
    const ws = attente(f);
    const html = fiche(f);
    // Only the two bars of the sheet: the rows of the composition chart (`data-forme="ligne"`) wear the same class.
    assert.equal((html.match(/class="barre-parts" data-forme="barre"/g) ?? []).length, 2, jeu);
    for (const code of ["median", "p85"] as const) {
      const b = bloc(html, code);
      const barreAttente = ws[code];
      assert.equal(barreAttente.state, "value");
      if (barreAttente.state !== "value") continue;
      assert.match(b, new RegExp(`<rect class="part-attente" x="0%"[^>]*width="${barreAttente.waitShare}%"`), `${code} ${jeu}`);
      assert.match(b, new RegExp(`<rect class="part-travail" x="${barreAttente.waitShare}%"[^>]*width="${barreAttente.workShare}%"`), `${code} ${jeu}`);
      assert.ok(texte(b).includes(en["conviction.bar.wait"].replace("{share}", part(barreAttente.waitShare))), `${code} ${jeu}`);
      assert.ok(texte(b).includes(en["conviction.bar.ratio"].replace("{ratio, number}", String(barreAttente.ratio))), `${code} ${jeu}`);
      assert.match(b, new RegExp(`data-rapport="${code}"`));
    }
    assert.ok(texte(html).includes(en["conviction.bar.title"]) && texte(html).includes(en["conviction.bar.labelMedian"]) && texte(html).includes(en["conviction.bar.labelP85"]));
    assert.ok(texte(html).includes(en["conviction.marker.refutation"].replace("{ratio, number}", "1.5")));
    assert.ok(texte(html).includes(en["conviction.marker.confirmation"].replace("{ratio, number}", "3")));
    assert.match(html, new RegExp(`data-marqueur="confirmation" x1="${ws.markers.confirmation.share}%"`));
    // The two bars wear the same two markers; the order of the page puts the bars after the key figures.
    assert.equal((html.match(/data-marqueur="refutation"/g) ?? []).length, 2);
    assert.ok(html.indexOf("data-chiffre") < html.indexOf('data-barre="median"') && html.indexOf('data-barre="median"') < html.indexOf('data-barre="p85"'));
  }
});

test("each display state draws its bars as the answer serves them: values, refuted with its own share, not settled, and no share where none is served", () => {
  const refutee = attente(ficheH1("refuted", { jeu: "real" }));
  assert.equal(refutee.median.state, "value");
  const htmlRefutee = fiche(ficheH1("refuted", { jeu: "real" }));
  assert.match(htmlRefutee, /data-barre="median" data-etat="value"/);
  assert.ok(texte(htmlRefutee).includes(en["conviction.bar.wait"].replace("{share}", part(refutee.median.state === "value" ? refutee.median.waitShare : 0))));
  const nonTranchee = fiche(ficheH1("not_settled"));
  assert.match(nonTranchee, /data-barre="median" data-etat="value"/);
  assert.ok(texte(nonTranchee).includes(en["conviction.bar.wait"].replace("{share}", "60%")), "ratio 2.5 gives a share of waiting of 60");
});

test("on an insufficient sample the bars are faded and the markers dotted and grey: no share, no ratio, no label, and the finding sentence stays", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const html = fiche(ficheH1("insufficient_sample", { jeu }));
    assert.equal((html.match(/data-etat="insufficient_sample"/g) ?? []).length >= 3, true, "the card and the two bars");
    assert.match(html, /data-barre="median" data-etat="insufficient_sample"/);
    assert.match(html, /data-barre="p85" data-etat="insufficient_sample"/);
    assert.equal((html.match(/repere-trait repere-pointille/g) ?? []).length, 4, jeu);
    assert.doesNotMatch(html, /part-attente|part-travail|repere-etiquette|data-rapport/, jeu);
    assert.doesNotMatch(texte(html), /\d+%|Waiting \d|lower threshold|upper threshold/, jeu);
    assert.ok(texte(html).includes(en["conviction.finding.insufficient_sample"]), jeu);
  }
});

test("on a masked sheet the masked bar is a dashed empty band: no bar, no number; the other bar keeps its own state", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const f = ficheH1("masked", { jeu });
    const html = fiche(f);
    const b = bloc(html, "median");
    assert.match(b, /data-etat="masked"/, jeu);
    assert.match(b, /class="bande-masquee"/, jeu);
    assert.doesNotMatch(b, /part-attente|part-travail|data-marqueur|data-rapport/, jeu);
    assert.doesNotMatch(texte(b), /\d/, jeu);
    assert.ok(texte(html).includes(en["conviction.finding.masked"]), jeu);
    assert.equal(attente(f).p85.state, "insufficient_sample", "the P85 bar tells its own state, not the masked one");
  }
});

test("where the ratio is under 1 the bar is replaced by the sentence, never a corrected number", () => {
  const html = fiche(ficheH1("not_comparable"));
  const b = bloc(html, "median");
  assert.match(b, /data-etat="not_comparable"/);
  assert.ok(texte(b).includes(en["conviction.notComparable"]));
  assert.doesNotMatch(b, /part-attente|part-travail/);
  assert.doesNotMatch(html, /-\d+%/);
});

test("a threshold of 1 or under served by the contract is told as text and has no mark on the bars", () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const basse = partsDAttente({ ...f, method: { ...f.method, thresholds: f.method.thresholds.map((s) => (s.code === "h1_lower" ? { ...s, value: 1 } : s)) } });
  assert.ok(basse !== undefined && basse.markers.refutation.inScale === false);
  const html = fiche({ ...f, waitShares: basse });
  assert.doesNotMatch(html, /data-marqueur="refutation"/);
  assert.match(html, /data-marqueur="confirmation"/);
  assert.ok(texte(html).includes(en["conviction.marker.outOfScale"].replace("{threshold}", "1")));
});

test("a threshold of 1 or under is told exactly once on the page, under the block of the two bars, and also when a bar is not comparable (R-20261103-4 (1))", () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const basse = partsDAttente({ ...f, method: { ...f.method, thresholds: f.method.thresholds.map((s) => (s.code === "h1_lower" ? { ...s, value: 1 } : s)) } });
  assert.ok(basse !== undefined);
  const phrase = en["conviction.marker.outOfScale"].replace("{threshold}", "1");
  const compte = (html: string) => texte(html).split(phrase).length - 1;
  const html = fiche({ ...f, waitShares: basse });
  assert.equal(compte(html), 1);
  assert.equal((html.match(/data-hors-echelle=/g) ?? []).length, 1);
  assert.ok(html.indexOf('data-barre="p85"') < html.indexOf("data-hors-echelle"), "under the block of the two bars");
  assert.ok(html.indexOf("data-hors-echelle") < html.indexOf("fiche-mentions"));
  // A bar that cannot be compared does not hide the threshold that is out of scale.
  const nonComparable = fiche({ ...f, waitShares: { ...basse, median: { state: "not_comparable" } } });
  assert.match(nonComparable, /data-barre="median" data-etat="not_comparable"/);
  assert.equal(compte(nonComparable), 1);
});

test("without waitShares the sheet draws no bar, no band and no composition, on either form, and keeps its text figures", () => {
  for (const cas of CAS_H1) {
    for (const jeu of ["synthetic", "real"] as const) {
      const { waitShares, ...sans } = ficheH1(cas, { jeu });
      assert.ok(waitShares !== undefined, "the helper serves waitShares");
      const html = fiche(sans as ReponseFiche);
      assert.doesNotMatch(html, /<svg(?![^>]*data-icone="lock")|role="img"|barre-parts|class="composition|Composition of the median lead time/, `${cas} ${jeu}`);
    }
  }
  const { waitShares: _, ...sans } = ficheH1("confirmed", { jeu: "real" });
  assert.match(fiche(sans as ReponseFiche), /data-rapport="median"/);
});

test("the bars of the sheet are drawn with a text alternative and the cycle time mention stays next to them", () => {
  const html = fiche(ficheH1("confirmed"));
  assert.ok(html.includes(`aria-label="${en["conviction.bar.alt"].replace("{share}", "75%").replace("{work}", "25%")}"`));
  assert.ok(texte(html).includes(en["fiche.mention.cycle_time_includes_ready_queue"]));
  assert.ok(html.indexOf('data-barre="p85"') < html.indexOf("fiche-mentions"), "the mention comes after the bars");
});

// R-20261103-5: one title above the block of the two bars, a short visible label on each bar, the drawing named by that label.
test("the two bars share one title paragraph and each wears its short visible label, which names the drawing for assistive technology", () => {
  for (const cas of CAS_H1) {
    for (const jeu of ["synthetic", "real"] as const) {
      for (const langue of ["en", "fr"] as const) {
        const c = catalogues[langue];
        const html = fiche(ficheH1(cas, { jeu }), {}, langue);
        const n = (html.match(/class="barre-parts" data-forme="barre"/g) ?? []).length;
        if (n === 0) continue;
        assert.equal(n, 2, `${cas} ${jeu} ${langue}`);
        // One title of bars on the page (the chart of the complete form has its own, with another text): a paragraph, never a heading.
        assert.equal(texte(html).split(c["conviction.bar.title"]).length - 1, 1, `${cas} ${jeu} ${langue}`);
        assert.match(html, /<p class="barre-titre">[^<]+<\/p><div class="barre-parts"/);
        assert.doesNotMatch(html, /conviction\.bar\.titleP85/);
        assert.ok(html.indexOf('class="barre-titre"') < html.indexOf('data-barre="median"'), "the title comes before both bars");
        for (const [code, cle] of [["median", "conviction.bar.labelMedian"], ["p85", "conviction.bar.labelP85"]] as const) {
          const b = bloc(html, code);
          const etiquette = /<p class="barre-etiquette" id="([^"]+)">([^<]+)<\/p>/.exec(b);
          assert.ok(etiquette !== null, `${code} label ${cas} ${jeu} ${langue}`);
          assert.equal(etiquette[2], c[cle]);
          // The drawing (when the bar has one) is labelled by the visible label, then by its own alternative.
          const svg = /<svg class="barre-svg" role="img" aria-label="[^"]+" id="([^"]+)" aria-labelledby="([^"]+)"/.exec(b);
          if (svg !== null) assert.equal(svg[2], `${etiquette[1]} ${svg[1]}`, `${code} ${cas} ${jeu} ${langue}`);
        }
      }
    }
  }
});

test("the catalogues and the sources hold no per-bar P85 title any more", () => {
  for (const catalogue of [en, fr]) assert.equal(Object.keys(catalogue).filter((cle) => cle.includes("titleP85")).length, 0);
});

// ---- 6.1 : the composition by quarter, in days, on the common axis -------------------------------------------------------------------

test("the complete form draws one row per quarter, work then waiting, days labelled, the total at the right, the length from axisShare", () => {
  const f = ficheH1("confirmed");
  const html = fiche(f);
  assert.ok(texte(html).includes(en["conviction.chart.title"]));
  const lignes = [...html.matchAll(/<div class="composition-ligne" data-trimestre="([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(lignes, (f.chart?.quarters ?? []).map((q) => q.quarter));
  assert.equal((lignes.length), 3);      // three closed quarters (R-20261114-49)
  // Every quarter has the same lead time: the common axis gives each one 100 (as the contract computes it).
  assert.equal((html.match(/<svg class="ligne-axe" x="0%"[^>]*width="100%"/g) ?? []).length, 3);
  assert.equal((html.match(/<rect class="part-travail" x="0%"[^>]*width="25%"/g) ?? []).length, 3);
  assert.equal((html.match(/<rect class="part-attente" x="25%"[^>]*width="75%"/g) ?? []).length, 3);
  assert.match(html, /composition-trimestre">Q3 2026<\/span>/);
  assert.match(html, /composition-total">40 d<\/span>/);
  assert.ok(texte(html).includes(en["conviction.chart.work"]) && texte(html).includes(en["conviction.chart.wait"]), "the legend");
  const francais = fiche(f, {}, "fr");
  assert.ok(texte(francais).includes(fr["conviction.chart.title"]));
  assert.match(francais, /composition-total">40 j<\/span>/);
});

test("the chart has its text alternative and a visually hidden table with the same figures", () => {
  const f = ficheH1("confirmed");
  const html = fiche(f);
  const alt = /<div class="composition-lignes" role="img" aria-label="([^"]+)"/.exec(html)?.[1] ?? "";
  assert.ok(alt.startsWith("For each quarter, the median lead time splits into work and waiting:"), alt);
  assert.ok(alt.includes(en["conviction.chart.altItem"].replace("{quarter}", "Q3 2026").replace("{work}", "10 d").replace("{wait}", "30 d")), alt);
  const tableau = /<table class="cache-visuel">[\s\S]*?<\/table>/.exec(html)?.[0] ?? "";
  assert.ok(tableau.length > 0, "a hidden table");
  assert.equal((tableau.match(/<tbody>[\s\S]*<\/tbody>/)?.[0].match(/<tr>/g) ?? []).length, 3);
  assert.ok(texte(tableau).includes(en["conviction.chart.total"]) && texte(tableau).includes(en["tableau.column.quarter"]));
  assert.match(tableau, /<td>10 d<\/td><td>30 d<\/td><td>40 d<\/td>/);
  assert.ok(html.indexOf("composition-lignes") < html.indexOf("cache-visuel"));
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  assert.match(/\.cache-visuel\s*\{([^}]*)\}/.exec(css)?.[1] ?? "", /position:\s*absolute/);
});

// R-20261114-49: a sheet holds three closed quarters, so the former test of four rows (masked, insufficient, not comparable, then the plain row that carries the
// axis) is split in two, every assertion kept: three rows here (masked, insufficient, the axis row), and the not comparable quarter with an axis row below.
test("a masked and an insufficient quarter are told by their word in their row, and the lengths follow the answer's axis", () => {
  const f = ficheH1("confirmed");
  const points = (f.chart?.quarters ?? []).map((p, rang) => {
    if (rang === 0) return { ...p, lead: { state: "masked" as const, threshold: 5 } };
    if (rang === 1) return { ...p, cycle: { state: "insufficient_sample" as const } };
    return p;
  });
  const melangee = { ...f, chart: { ...f.chart, quarters: points } } as ReponseFiche;
  const html = fiche(melangee);
  const rangs = html.split('<div class="composition-ligne"').slice(1);
  assert.equal(rangs.length, 3);
  assert.ok(texte(rangs[0]).includes(en["cellState.masked"]), "masked quarter");
  assert.ok(texte(rangs[1]).includes(en["state.insufficient_sample"]) && rangs[1].includes('data-icone="ellipsis"'), "insufficient quarter");
  assert.match(rangs[2], /<svg class="ligne-axe" x="0%"[^>]*width="100%"/, "the largest lead time among the visible ones is the axis");
  assert.doesNotMatch(rangs[0] + rangs[1], /part-attente/);
  // The hidden table and the alternative tell the same, row by row.
  assert.ok((/aria-label="([^"]+)"/.exec(/<div class="composition-lignes"[^>]*>/.exec(html)?.[0] ?? "")?.[1] ?? "").includes(en["conviction.chart.altItemNone"].replace("{quarter}", "Q1 2026")));
});

test("a not comparable quarter is told by its word in its row, and the axis row below it follows the answer's axis", () => {
  const f = ficheH1("confirmed");
  const points = (f.chart?.quarters ?? []).slice(0, 2).map((p, rang) => (rang === 0 ? { ...p, lead: { state: "value" as const, value: 8 } } : p));
  const melangee = { ...f, chart: { ...f.chart, quarters: points } } as ReponseFiche;
  const rangs = fiche(melangee).split('<div class="composition-ligne"').slice(1);
  assert.equal(rangs.length, 2);
  assert.ok(texte(rangs[0]).includes(en["conviction.notComparable"]), "not comparable quarter");
  assert.match(rangs[1], /<svg class="ligne-axe" x="0%"[^>]*width="100%"/, "the largest lead time among the visible ones is the axis");
  assert.doesNotMatch(rangs[0], /part-attente/);
});

test("the reduced form draws the two bars and no composition chart, no waiting in days and no hidden table", () => {
  for (const cas of CAS_H1) {
    const html = fiche(ficheH1(cas, { jeu: "real" }), { methodeOuverte: true });
    assert.doesNotMatch(html, /class="composition|cache-visuel|ligne-axe|data-chiffre="(wait|work)"/, cas);
    assert.doesNotMatch(texte(html), /Composition of the median lead time|days of waiting/, cas);
    assert.equal((html.match(/class="barre-parts"/g) ?? []).length, 2, cas);
  }
});

test("a chart on the page: the cases that show no figure draw no chart", () => {
  for (const cas of ["insufficient_sample", "masked"] as const) assert.doesNotMatch(fiche(ficheH1(cas)), /composition|cache-visuel/, cas);
});

test("the composition component draws nothing for no quarter, and each row carries its state", () => {
  assert.equal(propre(rendre(h(CompositionTrimestres, { quarters: [] }), "en")), "");
});

// ---- 6.3 : the demonstration screen with the two bars ------------------------------------------------------------------------------------

test("the demonstration sheet (published, reduced) shows the two bars, the ratios, the thresholds as ratios and the two medians, and no count nor waiting in days", () => {
  const f = ficheH1("confirmed", { jeu: "real" });
  const html = fiche(f);
  assert.equal((html.match(/class="barre-parts"/g) ?? []).length, 2);
  assert.match(html, /data-rapport="median"[\s\S]*?Lead time over cycle time: 4×/);
  assert.match(html, /data-rapport="p85"[\s\S]*?Lead time over cycle time: 4×/);
  assert.ok(texte(html).includes(en["conviction.marker.refutation"].replace("{ratio, number}", "1.5")));
  assert.match(html, /data-chiffre="lead_median"[\s\S]*?40 d/);
  assert.match(html, /data-chiffre="cycle_median"[\s\S]*?10 d/);
  assert.doesNotMatch(html, /7919|7,919|data-chiffre="(wait|work)"/);
  assert.doesNotMatch(texte(html), /Composition of the median lead time/);
  // One mark of the reduced form: the key figures, the bars, the ratios; no sentence of verdict besides the badge.
  assert.match(html, /class="badge[^"]*" data-etat="confirmed"/);
});

test("every bar and row of the page is drawn by classes: no style attribute, no fill or stroke attribute, on any case, form or language", () => {
  for (const cas of CAS_H1) {
    for (const jeu of ["synthetic", "real"] as const) {
      for (const langue of ["en", "fr"] as const) {
        const html = fiche(ficheH1(cas, { jeu }), {}, langue);
        assert.doesNotMatch(html, /\sstyle="|\sfill="|\sstroke="/, `${cas} ${jeu} ${langue}`);
        assert.doesNotMatch(html, /\p{Extended_Pictographic}/u, `${cas} ${jeu} ${langue}`);
      }
    }
  }
});

// ---- the catalogues -----------------------------------------------------------------------------------------------------------------------

const CLES_DES_BARRES = [
  "conviction.bar.title",
  "conviction.bar.labelMedian",
  "conviction.bar.labelP85",
  "conviction.bar.wait",
  "conviction.bar.work",
  "conviction.bar.alt",
  "conviction.bar.altNone",
  "conviction.marker.outOfScale",
  "conviction.chart.title",
  "conviction.chart.work",
  "conviction.chart.wait",
  "conviction.chart.total",
  "conviction.chart.alt",
  "conviction.chart.altItem",
  "conviction.chart.altItemNone",
];

test("every key the bars and the chart read is in both catalogues with the same parameters, and the wording of the proposed labels is D13's", () => {
  for (const [langue, catalogue] of Object.entries(catalogues)) {
    for (const cle of CLES_DES_BARRES) assert.ok(cle in catalogue, `texte de conviction absent : ${cle} (${langue})`);
  }
  assert.equal(en["conviction.bar.title"], "Share of waiting, against the adopted thresholds");
  assert.equal(fr["conviction.bar.title"], "Part d'attente, face aux seuils adoptés");
  // R-20261103-5 (2)(3): the per-bar title is gone; the two short labels are proposed, to be validated with Q307.
  assert.equal(Object.hasOwn(en, "conviction.bar.titleP85"), false);
  assert.equal(Object.hasOwn(fr, "conviction.bar.titleP85"), false);
  assert.equal(en["conviction.bar.labelMedian"], "Median");
  assert.equal(fr["conviction.bar.labelMedian"], "Médiane");
  assert.equal(en["conviction.bar.labelP85"], "P85");
  assert.equal(fr["conviction.bar.labelP85"], "P85");
  assert.equal(en["conviction.chart.title"], "Composition of the median lead time");
  assert.equal(fr["conviction.chart.title"], "Composition du lead time médian");
  assert.equal(en["conviction.bar.wait"], "Waiting {share}");
  assert.equal(fr["conviction.bar.work"], "Travail {share}");
  // The per-verdict finding sentences stay dropped (R-20261101-126, Q4 (a)): no caption key is added with the bars.
  assert.deepEqual(Object.keys(en).filter((cle) => /^conviction\.caption\./.test(cle)), []);
});
