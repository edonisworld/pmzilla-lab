// Lot 3c of mothra-demo-habillage (tasks 7.1 and 7.2): the hypothesis 5 sheet, cycle time and throughput by quarter, never waiting (D4), and the
// stability table (`TableauStabilite`, D17) in each of its states. Every sheet answer comes from `corpsDepuisVues` on synthetic view rows, reduced
// by `reduceToStatistics` for real data (D15, test/fiches-h5.ts); the free inputs of a component are written here. Nothing is computed by the
// front: the figures of the page are the measures of the answer, compared here with the answer itself.
// The wiring of the page into the application (the closed list of shipped kinds of D1, `GENRES_LUS` of the conviction page) was decided by
// R-20261103-14 Q1 (a); the tests of that wiring are in test/habillage-fiche-h1.test.ts.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";

import { compositionConviction } from "@mothra/contract/composition";
import { POSITIONS_DEBIT } from "@mothra/contract/listes-fiche";

import type { ReponseFiche } from "../src/api/fiche.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { TableauStabilite } from "../src/composants/TableauStabilite.ts";
import type { PropsTableauStabilite } from "../src/composants/TableauStabilite.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { ATTENDU_H5, CAS_H5, ficheH5 } from "./fiches-h5.ts";
import type { CasH5 } from "./fiches-h5.ts";
import { EQUIPE_SYNTHETIQUE, IDENTIFIANT_OPAQUE } from "./fiches-h1.ts";
import { rendre, texte } from "./rendu.ts";
import { analyser, derivations, valeursEnDur } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

function fiche(f: ReponseFiche, props: Partial<Parameters<typeof FicheConviction>[0]> = {}, langue: Langue = "en"): string {
  return propre(rendre(h(FicheConviction, { fiche: f, ...props }), langue));
}

function tableau(props: PropsTableauStabilite, langue: Langue = "en"): string {
  return propre(rendre(h(TableauStabilite, props), langue));
}

// The evidence card of a page: from its section to the first closing section.
function preuve(html: string): string {
  const carte = /<section class="carte carte-preuve"[^>]*>[\s\S]*?<\/section>/.exec(html)?.[0];
  assert.ok(carte !== undefined, "carte de preuve absente");
  return carte;
}

// The rows of the stability table, by quarter label of the answer.
function lignes(html: string): Map<string, string> {
  return new Map([...html.matchAll(/<tr[^>]*data-trimestre="([^"]+)"[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => [m[1], m[0]] as [string, string]));
}

function ligne(html: string, trimestre: string): string {
  const trouvee = lignes(html).get(trimestre);
  assert.ok(trouvee !== undefined, `ligne absente : ${trimestre}`);
  return trouvee;
}

const JUGE = "2026-Q3";
const QUARTS = ["Q1 2026", "Q2 2026", "Q3 2026"];      // the three closed quarters (R-20261114-49)

// The position of the judged quarter's throughput that each case must give (the fixture is checked, not trusted).
const POSITION_JUGEE: Partial<Record<CasH5, string>> = {
  confirmed: "throughput_within_band",
  refuted: "throughput_under_low_floor",
  not_settled: "throughput_under_floor",
  // R-20261114-83: the cases throughput_masked, p85_insufficient and p85_masked have an incomplete judged quarter: two complete quarters, no reference, no
  // position (the branch "no reference, no position" of the test below).
};

// ---- the answers come from the contract (D15) ------------------------------------------------------------------------------------

test("the sheet answers of the tests come from the contract: one per case, the verdict is the service's, hypothesis 5 without bars, the real form carries no count", () => {
  for (const cas of CAS_H5) {
    const synthetique = ficheH5(cas);
    assert.equal(synthetique.verdict, ATTENDU_H5[cas].verdict, cas);
    assert.equal(compositionConviction(synthetique).state, ATTENDU_H5[cas].etat, cas);
    assert.equal(synthetique.method.hypothesis, "h5");
    assert.equal(synthetique.dataset, "synthetic");
    assert.equal(synthetique.waitShares, undefined, "the bars measure hypothesis 1 only: the service layer adds none (D3b)");
    assert.equal(synthetique.ratios, undefined);
    assert.ok(synthetique.method.limits.includes("throughput_own_past_only"));
    const attendue = POSITION_JUGEE[cas];
    if (attendue !== undefined) assert.equal(synthetique.throughputPositions?.find((p) => p.quarter === JUGE)?.position, attendue, cas);
    else assert.deepEqual(synthetique.throughputPositions, [], `${cas}: no reference, no position`);
    const reelle = ficheH5(cas, { jeu: "real" });
    assert.equal(reelle.dataset, "real");
    assert.ok(reelle.method.limits.includes("reduced_form"), cas);
    assert.deepEqual(reelle.throughputPositions, synthetique.throughputPositions, "the reduced form keeps the positions");
    assert.equal(JSON.stringify(reelle).includes('"items"'), false, cas);
    assert.equal(JSON.stringify(reelle).includes("7919"), false, cas);
  }
  // The rows whose figures would confirm: the contract itself gives "not settled" to a team sheet (the ban of D20, unplanned work not measurable
  // for a team, D33). The case "confirmed" sets the verdict on those rows to exercise the display state; this is the only hand-set field.
  const duContrat = ficheH5("confirmed", { verdictDuContrat: true });
  assert.equal(duContrat.verdict, "not_settled");
  assert.deepEqual({ ...duContrat, verdict: "confirmed", verdictReasons: [], verdictFindings: ["h5_within_band"] }, ficheH5("confirmed"));
  // The cases the page tells apart: a masked throughput gives its reason; fewer than three complete quarters give two rows and no reference.
  // R-20261114-83: with three closed quarters the masked judged throughput leaves two complete quarters: no reference, no reason (before: ["throughput_masked"]).
  for (const cas of CAS_H5) assert.deepEqual(ficheH5(cas).h5Reasons, [], cas);
  assert.equal(ficheH5("insufficient_sample").chart?.quarters.length, 2);
  assert.equal(ficheH5("p85_insufficient").p85?.quarters.find((p) => p.quarter === JUGE)?.cycle.state, "insufficient_sample");
  assert.equal(ficheH5("p85_insufficient").chart?.quarters.find((p) => p.quarter === JUGE)?.cycle.state, "value");
  assert.equal(ficheH5("p85_masked").p85?.quarters.find((p) => p.quarter === JUGE)?.cycle.state, "masked");
});

// ---- the page of hypothesis 5 (D4) -------------------------------------------------------------------------------------------------

test("the page shows the statement of hypothesis 5, the badge, the key figures of the judged quarter and one row per quarter, on both forms and in both languages", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    for (const langue of ["en", "fr"] as const) {
      const c = catalogues[langue];
      const f = ficheH5("confirmed", { jeu });
      const html = fiche(f, {}, langue);
      const periode = langue === "en" ? "Q3 2026" : "T3 2026";
      assert.ok(texte(html).includes(c["conviction.statement.lead_cycle_h5"]), `${jeu} ${langue}`);
      assert.doesNotMatch(texte(html), new RegExp(c["conviction.statement.lead_cycle_h1"].slice(1, 20)), `${jeu} ${langue}`);
      assert.match(html, /class="badge[^"]*" data-etat="confirmed"/);
      assert.match(html, /carte-preuve" data-etat="confirmed"/);
      const carte = preuve(html);
      // The key figures: the median and the P85 of the cycle time of the judged quarter, each a measure of the answer, with its label.
      const jours = (n: string): string => c["conviction.chart.days"].replace("{days}", n);
      assert.match(carte, new RegExp(`data-chiffre="cycle_median"[\\s\\S]*?<span[^>]*data-state="value">${jours("10")}</span>`), `${jeu} ${langue}`);
      assert.match(carte, new RegExp(`data-chiffre="cycle_p85"[\\s\\S]*?<span[^>]*data-state="value">${jours("20")}</span>`), `${jeu} ${langue}`);
      assert.ok(texte(carte).includes(c["conviction.h5.figure.median"].replace("{period}", periode)), `${jeu} ${langue}`);
      assert.ok(texte(carte).includes(c["conviction.h5.figure.p85"].replace("{period}", periode)), `${jeu} ${langue}`);
      // The throughput position of the judged quarter, as its sentence: no count.
      const position = c["fiche.position.throughput_within_band"];
      assert.ok(texte(carte).includes(c["conviction.h5.figure.throughput"].replace("{period}", periode).replace("{position}", position)), `${jeu} ${langue}`);
      assert.match(carte, /data-chiffre="throughput"/);
      // The stability table: one row per point of the sheet, in their order, the median, the P85 and the position of each.
      assert.deepEqual([...lignes(carte).keys()], (f.chart?.quarters ?? []).map((q) => q.quarter), `${jeu} ${langue}`);
      assert.deepEqual([...lignes(carte).keys()], ["2026-Q1", "2026-Q2", JUGE]);
      assert.ok(texte(carte).includes(c["conviction.h5.table.title"]), `${jeu} ${langue}`);
      for (const colonne of ["tableau.column.quarter", "fiche.measure.cycle_median_days", "fiche.measure.cycle_p85_days", "fiche.column.throughputPosition"]) {
        assert.match(carte, new RegExp(`<th scope="col">${c[colonne]}</th>`), `${colonne} ${jeu} ${langue}`);
      }
      for (const trimestre of lignes(carte).keys()) {
        const t = texte(ligne(carte, trimestre));
        assert.ok(t.includes(jours("10")) && t.includes(jours("20")) && t.includes(position), `${trimestre} ${jeu} ${langue}`);
      }
      assert.ok(texte(ligne(carte, JUGE)).startsWith(langue === "en" ? "Q3 2026" : "T3 2026"), langue);
    }
  }
});

test("the judged quarter is the only row marked, with the current-item attribute and no text of its own", () => {
  const carte = preuve(fiche(ficheH5("confirmed")));
  assert.equal((carte.match(/aria-current="true"/g) ?? []).length, 1);
  assert.match(ligne(carte, JUGE), /class="ligne-jugee"[^>]*aria-current="true"|aria-current="true"[^>]*class="ligne-jugee"/);
  for (const t of ["2026-Q1", "2026-Q2"]) assert.doesNotMatch(ligne(carte, t), /aria-current|ligne-jugee/, t);
  // The mark is in the stylesheet by weight and line, with no colour of its own.
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  const regle = /\.ligne-jugee th,\s*\.ligne-jugee td\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
  assert.match(regle, /font-weight:\s*700/);
  assert.doesNotMatch(regle, /color|background/);
});

test("the band and the floors are the adopted values of the answer, stated next to the table; the cycle time mention and the throughput's own past come after it", () => {
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const f = ficheH5("confirmed");
    const html = fiche(f, {}, langue);
    const carte = preuve(html);
    const valeur = (code: string): string => {
      const seuil = f.method.thresholds.find((s) => s.code === code);
      assert.ok(seuil !== undefined, code);
      // R-20261109-08 Q5: the stored fraction is shown as a percentage, with the sign "±" for the band (the stored value stays the fraction, next line).
      const pourcent = new Intl.NumberFormat(langue, { style: "percent", maximumFractionDigits: 1 }).format(seuil.value);
      return code === "h5_band" || code === "h5_double_band" ? `±${pourcent}` : pourcent;
    };
    assert.deepEqual(["0.2", "0.4", "0.8", "0.6"], ["h5_band", "h5_double_band", "h5_floor", "h5_low_floor"].map((code) => String(f.method.thresholds.find((s) => s.code === code)?.value)));
    assert.ok(texte(carte).includes(c["conviction.h5.band"].replace("{band}", valeur("h5_band")).replace("{doubleBand}", valeur("h5_double_band"))), langue);
    assert.ok(texte(carte).includes(c["conviction.h5.floor"].replace("{floor}", valeur("h5_floor")).replace("{lowFloor}", valeur("h5_low_floor"))), langue);
    assert.ok(carte.indexOf("<table") < carte.indexOf('data-seuil-h5="band"'), "stated next to the table, after it");
    assert.ok(carte.indexOf('data-seuil-h5="floor"') < carte.indexOf("fiche-mentions"));
    assert.ok(texte(carte).includes(c["fiche.mention.cycle_time_includes_ready_queue"]), langue);
    assert.ok(texte(carte).includes(c["fiche.throughputOwnPastOnly"]), langue);
    assert.ok(carte.indexOf("fiche-mentions") < carte.indexOf('data-limite="throughput_own_past_only"'));
  }
  // The line of the throughput's own past follows the limits of the answer: without the limit, no line.
  const f = ficheH5("confirmed");
  const sansLimite = { ...f, method: { ...f.method, limits: f.method.limits.filter((l) => l !== "throughput_own_past_only") } } as ReponseFiche;
  assert.doesNotMatch(fiche(sansLimite), /throughput_own_past_only/);
  // A band or a floor the answer does not hold is left out, never invented.
  const sansSeuils = { ...f, method: { ...f.method, thresholds: f.method.thresholds.filter((s) => !s.code.startsWith("h5_")) } } as ReponseFiche;
  assert.doesNotMatch(fiche(sansSeuils), /data-seuil-h5/);
});

// ---- no waiting anywhere on the page (D4, R-20261101-14) ------------------------------------------------------------------------------

// The longest static part of a message: what the page would show of it whatever its values.
function fragment(catalogue: Record<string, string>, cle: string): string {
  return [...catalogue[cle].split(/\{[^}]*\}/)].map((s) => s.trim()).sort((a, b) => b.length - a.length)[0];
}

// The keys that D13 marks "hypothesis 1 only" and whose text is long enough to be told apart from the words of the hypothesis 5 page.
const CLES_H1_SEULEMENT = [
  "conviction.bar.title",
  "conviction.bar.alt",
  "conviction.bar.altNone",
  "conviction.bar.ratio",
  "conviction.marker.refutation",
  "conviction.marker.confirmation",
  "conviction.marker.outOfScale",
  "conviction.notComparable",
  "conviction.chart.title",
  "conviction.chart.work",
  "conviction.chart.wait",
  "conviction.chart.alt",
  "conviction.footer.waitDefinition",
  "conviction.footer.cycleScope",
  "conviction.figure.wait",
  "conviction.figure.work",
];

test("on every case, the hypothesis 5 page shows no bar, no waiting and none of the labels D13 marks hypothesis 1 only", () => {
  for (const cas of CAS_H5) {
    for (const jeu of ["synthetic", "real"] as const) {
      for (const langue of ["en", "fr"] as const) {
        const html = fiche(ficheH5(cas, { jeu }), { methodeOuverte: true }, langue);
        const note = `${cas} ${jeu} ${langue}`;
        assert.doesNotMatch(html, /barre-parts|barre-titre|barre-svg|data-barre|data-marqueur|data-rapport|data-hors-echelle|class="composition|cache-visuel|ligne-axe|part-attente|part-travail/, note);
        assert.doesNotMatch(html, /data-chiffre="(wait|work)"/, note);
        // The only drawings of the page are the vector icons (the badge, the lock, the ellipsis): no chart, no bar.
        assert.doesNotMatch(html, /<svg(?![^>]*data-icone=)/, note);
        assert.doesNotMatch(html, /role="img"/, note);
        for (const cle of CLES_H1_SEULEMENT) assert.ok(!texte(html).includes(fragment(catalogues[langue], cle)), `${note} : ${cle}`);
      }
    }
  }
  for (const [langue, catalogue] of Object.entries(catalogues)) assert.equal("conviction.bar.titlePlain" in catalogue, false, langue);
});

test("the sources of hypothesis 5 read no bar, no waitShares and no key of hypothesis 1 only, and of the composition they read the state and the judged quarter", () => {
  const interdit = /^conviction\.(bar|marker|figure|caption)\.|^conviction\.notComparable$|^conviction\.footer\.(waitDefinition|cycleScope)$|^conviction\.chart\.(?!days$)/;
  for (const fichier of ["src/composants/PreuveH5.ts", "src/composants/TableauStabilite.ts"]) {
    const contenu = readFileSync(`${FRONT}${fichier}`, "utf8");
    assert.deepEqual(analyser(contenu).litteraux.filter((l) => interdit.test(l.texte)).map((l) => `${fichier}:${l.ligne} ${l.texte}`), [], fichier);
    assert.doesNotMatch(analyser(contenu).code, /BarreParts|CompositionTrimestres|HorsEchelle|waitShares|compositionConviction|\.measured\b|axisShare|waitDays|workDays|leadDays/, fichier);
    assert.deepEqual(valeursEnDur(fichier, contenu), [], fichier);
    assert.deepEqual(derivations(fichier, contenu), [], fichier);
    assert.doesNotMatch(contenu, /\bstyle\s*:|\bfill\s*:|\bstroke\s*:/, fichier);
  }
  // The block of `FicheConviction` that serves hypothesis 5 reads `state` (through `etat`) and `measured.quarter` of the composition, nothing else.
  const source = readFileSync(`${FRONT}src/composants/FicheConviction.ts`, "utf8");
  const debut = source.indexOf("// ---- hypothesis 5 begin");
  const fin = source.indexOf("// ---- hypothesis 5 end");
  assert.ok(debut >= 0 && fin > debut, "bornes du bloc de l'hypothèse 5");
  const bloc = analyser(source.slice(debut, fin)).code;
  assert.match(bloc, /composition\?\.measured\.quarter/);
  assert.doesNotMatch(bloc, /\.quarters\b|waitShares|BarreParts|waitDays|workDays|leadDays|axisShare|\.measured\.(?!quarter\b)/);
  assert.match(source, /h\(PreuveH5, \{ fiche, etat, trimestreJuge \}\)/);
  // The only read of `waitShares` in the component is guarded by the hypothesis: hypothesis 5 never reads it.
  const lectures = analyser(source).code.match(/\.waitShares\b/g) ?? [];
  assert.equal(lectures.length, 1, "une seule lecture de waitShares");
  assert.match(analyser(source).code, /h5\s*\?\s*undefined\s*:\s*fiche\.waitShares/);
  // The evidence imports the type of the display state from the composition subpath, and no function of it.
  assert.doesNotMatch(readFileSync(`${FRONT}src/composants/PreuveH5.ts`, "utf8"), /^import\s+(?!type\b)[^;]*from\s+"@mothra\/contract\/composition"/m);
});

// ---- the display states (D5) ----------------------------------------------------------------------------------------------------------

test("each case shows the badge and the outline of its display state, in both languages", () => {
  for (const cas of CAS_H5) {
    for (const langue of ["en", "fr"] as const) {
      const html = fiche(ficheH5(cas), {}, langue);
      assert.match(html, new RegExp(`class="badge[^"]*" data-etat="${ATTENDU_H5[cas].etat}"`), `${cas} ${langue}`);
      assert.match(html, new RegExp(`carte-preuve" data-etat="${ATTENDU_H5[cas].etat}"`), `${cas} ${langue}`);
      assert.ok(texte(html).includes(catalogues[langue][`conviction.badge.${ATTENDU_H5[cas].etat}`]), `${cas} ${langue}`);
    }
  }
});

test("the position of the judged quarter follows the answer: within the band, under the floor, under the low floor", () => {
  for (const cas of ["confirmed", "not_settled", "refuted"] as const) {
    const f = ficheH5(cas);
    const position = f.throughputPositions?.find((p) => p.quarter === JUGE)?.position;
    assert.equal(position, POSITION_JUGEE[cas]);
    const carte = preuve(fiche(f));
    assert.match(ligne(carte, JUGE), new RegExp(`data-position="${position}"`), cas);
    assert.ok(texte(ligne(carte, JUGE)).includes(en[`fiche.position.${position}`]), cas);
    assert.ok(texte(carte).includes(en["conviction.h5.figure.throughput"].replace("{period}", "Q3 2026").replace("{position}", en[`fiche.position.${position}`])), cas);
  }
});

test("an insufficient sample and a masked sheet show their sentence alone: no key figure, no table, no number, and the band and floors stay stated", () => {
  for (const cas of ["insufficient_sample", "masked"] as const) {
    for (const jeu of ["synthetic", "real"] as const) {
      for (const langue of ["en", "fr"] as const) {
        const c = catalogues[langue];
        const f = ficheH5(cas, { jeu });
        const carte = preuve(fiche(f, {}, langue));
        const note = `${cas} ${jeu} ${langue}`;
        assert.ok(texte(carte).includes(c[cas === "masked" ? "conviction.finding.masked" : "conviction.finding.insufficient_sample"]), note);
        assert.doesNotMatch(carte, /data-chiffre|chiffres|<table|data-trimestre|data-position|mesure-valeur|fiche-mentions|throughput_own_past_only/, note);
        // No figure: no number of days (the band and the floors are thresholds, not figures of the sheet).
        assert.doesNotMatch(texte(carte), new RegExp(`\\d+ ${langue === "en" ? "d" : "j"}\\b`), note);
        assert.ok(texte(carte).includes(c["conviction.h5.band"].replace("{band}", `±${new Intl.NumberFormat(langue, { style: "percent" }).format(0.2)}`).replace("{doubleBand}", `±${new Intl.NumberFormat(langue, { style: "percent" }).format(0.4)}`)), note);
        assert.match(carte, /data-seuil-h5="floor"/, note);
        assert.deepEqual(f.throughputPositions, [], "the answer holds no position without a reference");
      }
    }
  }
  // A masked sheet is a masked outline; its badge says so.
  assert.match(fiche(ficheH5("masked")), /class="badge[^"]*" data-etat="masked"/);
});

test("a team with fewer than three complete quarters gets the insufficient sample badge and no number", () => {
  const f = ficheH5("insufficient_sample");
  assert.equal(f.chart?.quarters.length, 2, "two quarters only");
  assert.equal(f.verdict, "insufficient_sample");
  const html = fiche(f);
  assert.match(html, /class="badge[^"]*" data-etat="insufficient_sample"/);
  const carte = preuve(html);
  assert.ok(texte(carte).includes(en["conviction.finding.insufficient_sample"]));
  assert.doesNotMatch(texte(carte), /\d+ d\b/);
  assert.doesNotMatch(carte, /<table|<tr/);
});

// ---- the reason of a masked throughput (D4) ---------------------------------------------------------------------------------------------

test("a masked throughput gives \"insufficient sample\" with three closed quarters (R-20261114-83); the reason of the answer is told under the badge, a reason the contract gives", () => {
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const f = ficheH5("throughput_masked");
    assert.equal(f.verdict, "insufficient_sample");      // two complete quarters, no reference: no reason, no position, no table
    const sans = fiche(f, {}, langue);
    assert.match(sans, /class="badge[^"]*" data-etat="insufficient_sample"/);
    assert.doesNotMatch(sans, /fiche-raison/);
    // The page tells the reason the ANSWER carries, under the badge and before the evidence: here on a "not settled" answer that carries it.
    const avec = fiche({ ...ficheH5("not_settled"), h5Reasons: ["throughput_masked"] } as ReponseFiche, {}, langue);
    assert.match(avec, /<p class="fiche-raison" data-raison="throughput_masked">/);
    assert.ok(texte(avec).includes(c["fiche.reason.throughput_masked"]), langue);
    assert.ok(avec.indexOf('class="badge') < avec.indexOf("fiche-raison") && avec.indexOf("fiche-raison") < avec.indexOf("carte carte-preuve"), "under the badge, before the evidence");
    // The other quarters keep their position, the judged quarter keeps its two cycle time figures.
    const carte = preuve(avec);
    assert.match(ligne(carte, "2026-Q2"), /data-position="throughput_within_band"/);
    assert.match(ligne(carte, JUGE), /data-state="value"/);
  }
  // No case tells a reason of its own now; the reason is the answer's, not a rule of the page.
  for (const cas of CAS_H5) assert.doesNotMatch(fiche(ficheH5(cas)), /fiche-raison/, cas);
  assert.doesNotMatch(fiche({ ...ficheH5("not_settled"), h5Reasons: [] }), /fiche-raison/);
  // A reason the catalogue does not know has the fallback sentence, never the raw code.
  const inconnu = { ...ficheH5("not_settled"), h5Reasons: ["strange_reason"] } as unknown as ReponseFiche;
  assert.ok(texte(fiche(inconnu)).includes(en["fiche.reason.unknown"]));
  assert.doesNotMatch(texte(fiche(inconnu)), /strange_reason/);
});

test("a quarter whose P85 is an insufficient sample or masked shows that state in its cell and its key figure, and keeps its median", () => {
  // R-20261114-83: with three closed quarters such a sheet is an "insufficient sample" (two complete quarters, no reference) and draws no table and no key
  // figure; the state of the judged P85 stays in the answer, and the stability table draws it from that answer.
  const insuffisante = fiche(ficheH5("p85_insufficient"));
  assert.match(insuffisante, /class="badge[^"]*" data-etat="insufficient_sample"/);
  const tableInsuffisante = tableau(proprietes(ficheH5("p85_insufficient")));
  assert.ok(ligne(tableInsuffisante, JUGE).includes("cellule-insuffisante"));
  assert.ok(texte(ligne(tableInsuffisante, JUGE)).includes(en["state.insufficient_sample"]));
  assert.match(ligne(tableInsuffisante, JUGE), /data-state="value">10 d</);
  const tableMasquee = tableau(proprietes(ficheH5("p85_masked")));
  assert.ok(ligne(tableMasquee, JUGE).includes("cellule-masquee"));
  assert.ok(texte(ligne(tableMasquee, JUGE)).includes(en["cellState.masked"]));
  // The other quarters are untouched.
  assert.ok(!ligne(tableMasquee, "2026-Q2").includes("cellule-masquee"));
  // The assertions of the key figures, kept (R-20261114-83): a "not settled" answer (it has a reference and draws its key figures) whose judged P85 carries the
  // state of the case, set by hand like the reason `throughput_masked` above; the median of the judged quarter stays a value of 10 days.
  const nonTranchee = ficheH5("not_settled");
  const p85Insuffisant = fiche({ ...nonTranchee, p85: ficheH5("p85_insufficient").p85 } as ReponseFiche);
  assert.match(p85Insuffisant, /class="badge[^"]*" data-etat="not_settled"/);
  assert.ok(ligne(p85Insuffisant, JUGE).includes("cellule-insuffisante"));
  assert.ok(texte(ligne(p85Insuffisant, JUGE)).includes(en["state.insufficient_sample"]));
  assert.match(preuve(p85Insuffisant), /data-chiffre="cycle_p85"[\s\S]*?class="mesure-insuffisante"/);
  assert.match(preuve(p85Insuffisant), /data-chiffre="cycle_median"[\s\S]*?data-state="value">10 d</);
  const p85Masque = fiche({ ...nonTranchee, p85: ficheH5("p85_masked").p85 } as ReponseFiche);
  assert.ok(ligne(p85Masque, JUGE).includes("cellule-masquee"));
  assert.ok(texte(ligne(p85Masque, JUGE)).includes(en["cellState.masked"]));
  assert.match(preuve(p85Masque), /data-chiffre="cycle_p85"[\s\S]*?class="mesure-masquee"/);
  assert.ok(!ligne(p85Masque, "2026-Q2").includes("cellule-masquee"));
});

// ---- the insets, the explanations, the status and the footer, as for hypothesis 1 (D6) -----------------------------------------------------

test("the order of the page is the one of hypothesis 1: statement, badge and status, evidence, the three insets, the competing explanations, the footer", () => {
  for (const jeu of ["synthetic", "real"] as const) {
    const html = fiche(ficheH5("confirmed", { jeu }));
    const marques = ["<h1", 'class="badge', 'class="statut-fiche', "carte carte-preuve", 'data-encart="question"', 'data-encart="effet"', 'data-encart="cause"', "explications-concurrentes", "<footer"];
    const places = marques.map((m) => html.indexOf(m));
    assert.ok(places.every((p) => p >= 0), `${jeu} : ${marques[places.findIndex((p) => p < 0)]}`);
    assert.deepEqual([...places].sort((a, b) => a - b), places, jeu);
  }
});

test("the insets are the fields of the sheet, the explanations state and reason only, the status is the life cycle's, and no action is offered", () => {
  const f = ficheH5("confirmed");
  const html = fiche({ ...f, effect: { text: "Effet inventé.", lang: "fr" }, cause: { text: "Invented cause.", lang: "en" } });
  assert.ok(texte(html).includes(en["conviction.inset.managementQuestion"]) && texte(html).includes(en["fiche.question.predictability"]));
  assert.match(html, /<span lang="fr">Effet inventé\.<\/span>/);
  assert.match(html, /<span>Invented cause\.<\/span>/, "same language as the screen: no lang attribute");
  assert.equal((texte(fiche(ficheH5("confirmed", { etat: "draft", texte: false }))).match(new RegExp(en["fiche.text.missing"], "g")) ?? []).length, 2);
  const bloc = /<section class="explications-concurrentes">[\s\S]*?<\/section>/.exec(html)?.[0] ?? "";
  for (const nom of ["unplanned_work", "capacity", "dependencies"]) assert.match(bloc, new RegExp(`data-explication="${nom}"`));
  assert.doesNotMatch(texte(bloc), /%/);
  assert.match(html, /data-etat-fiche="published"/);
  assert.ok(texte(fiche(f)).includes("Published on November 2, 2026 · version 1 · frozen"));
  for (const etat of ["draft", "reviewed", "published"] as const) {
    const page = fiche(ficheH5("confirmed", { etat }), { methodeOuverte: true });
    assert.doesNotMatch(page, /<input|<textarea|<select|<form/, etat);
    assert.equal((page.match(/<button/g) ?? []).length, 1, etat);
  }
});

test("the footer states the masking threshold, with no line of the hypothesis served (R-20261109-08 Q2 (a)), no threshold line (A-16 (a)) and no definition of the waiting", () => {
  const html = fiche(ficheH5("confirmed"), { seuilMasquage: 5 });
  const pied = /<footer[\s\S]*<\/footer>/.exec(html)?.[0] ?? "";
  assert.ok(texte(pied).includes(en["conviction.footer.masking"].replace("{threshold}", "5")));
  assert.doesNotMatch(texte(pied), /Hypothesis served/);
  assert.ok(!texte(pied).includes(en["fiche.link.h5"]), "the number of the hypothesis stays on the method face");
  assert.equal("conviction.footer.hypothesis" in en, false);
  assert.doesNotMatch(pied, /data-seuil=/, "the thresholds are on the method face only (A-16 (a))");
  assert.ok(!texte(pied).includes(en["conviction.footer.waitDefinition"]) && !texte(pied).includes(en["conviction.footer.cycleScope"]));
});

test("the page names the team once, by its opaque identifier, and never the witness name of the rows", () => {
  const f = ficheH5("confirmed", { jeu: "real" });
  const html = fiche(f);
  assert.equal(texte(html).split(IDENTIFIANT_OPAQUE).length - 1, 1, "the identifier is shown once");
  assert.doesNotMatch(html, new RegExp(EQUIPE_SYNTHETIQUE, "i"));
  assert.doesNotMatch(html, /<select|<option/, "no team selector");
  assert.ok(texte(html).includes(en["conviction.scope.team"].replace("{team}", IDENTIFIANT_OPAQUE)));
});

test("the detail by quarter is offered on the complete form only, and the reduced form shows the table without a count", () => {
  assert.match(fiche(ficheH5("confirmed"), { seuilMasquage: 5 }), new RegExp(`<a class="lien" href="#/tableau\\?team=${IDENTIFIANT_OPAQUE}&amp;from=2026-Q1&amp;to=2026-Q3">See the detail by quarter</a>`));
  const reduite = fiche(ficheH5("confirmed", { jeu: "real" }), { seuilMasquage: 5 });
  assert.doesNotMatch(reduite, /See the detail by quarter/);
  assert.equal(lignes(preuve(reduite)).size, 3);
  assert.doesNotMatch(reduite, /7919|7,919/);
  assert.doesNotMatch(fiche(ficheH5("confirmed"), { avecTableau: false }), /See the detail by quarter/);
});

test("every case is drawn by classes: no style attribute, no fill or stroke attribute, no emoji", () => {
  for (const cas of CAS_H5) {
    for (const langue of ["en", "fr"] as const) {
      const html = fiche(ficheH5(cas), {}, langue);
      assert.doesNotMatch(html, /\sstyle="|\sfill="|\sstroke="/, `${cas} ${langue}`);
      assert.doesNotMatch(html, /\p{Extended_Pictographic}/u, `${cas} ${langue}`);
    }
  }
});

// ---- the stability table in each of its states (D17) -----------------------------------------------------------------------------------------

// The props of the table from a sheet answer: the judged quarter marked unless told otherwise.
function proprietes(f: ReponseFiche, options: { sansJuge?: boolean } = {}): PropsTableauStabilite {
  return {
    trimestres: f.chart?.quarters ?? [],
    p85: f.p85?.quarters ?? [],
    positions: f.throughputPositions ?? [],
    juge: options.sansJuge === true ? undefined : JUGE,
  };
}

test("the table draws a value, a masked measure and an insufficient measure by their state, in both languages", () => {
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    const valeurs = tableau(proprietes(ficheH5("confirmed")), langue);
    assert.match(valeurs, /^<div class="tableau-conteneur" tabindex="0"><table class="tableau tableau-stabilite" data-tableau="stabilite">/);
    assert.equal((valeurs.match(/<td class="cellule cellule-valeur" data-state="value">/g) ?? []).length, 6, "two measures in three rows");
    assert.ok(texte(valeurs).includes(c["conviction.chart.days"].replace("{days}", "10")));
    assert.ok(texte(valeurs).includes(c["conviction.h5.table.title"]));
    assert.match(tableau(proprietes(ficheH5("p85_masked")), langue), /<td class="cellule cellule-masquee" data-state="masked">/);
    assert.match(tableau(proprietes(ficheH5("p85_insufficient")), langue), /<td class="cellule cellule-insuffisante" data-state="insufficient_sample">/);
    assert.ok(texte(tableau(proprietes(ficheH5("p85_insufficient")), langue)).includes(c["state.insufficient_sample"]), langue);
    assert.ok(texte(tableau(proprietes(ficheH5("p85_masked")), langue)).includes(c["cellState.masked"]), langue);
  }
});

test("each throughput position code has its sentence in the table, and a missing or unknown position has the fallback sentence, never the raw code", () => {
  const fiches: Record<string, ReponseFiche> = {
    throughput_within_band: ficheH5("confirmed"),
    throughput_under_floor: ficheH5("not_settled"),
    throughput_under_low_floor: ficheH5("refuted"),
    // R-20261114-83: a masked judged throughput no longer gives a position on a sheet (no reference with three closed quarters): the position code `masked`
    // of the contract's list is set on the judged quarter of the "confirmed" answer, the only hand-set field.
    masked: { ...ficheH5("confirmed"), throughputPositions: (ficheH5("confirmed").throughputPositions ?? []).map((p) => (p.quarter === JUGE ? { ...p, position: "masked" as const } : p)) } as ReponseFiche,
  };
  assert.deepEqual(Object.keys(fiches).sort(), [...POSITIONS_DEBIT].sort(), "the list of the contract is covered");
  for (const langue of ["en", "fr"] as const) {
    const c = catalogues[langue];
    for (const [code, f] of Object.entries(fiches)) {
      const html = tableau(proprietes(f), langue);
      assert.match(ligne(html, JUGE), new RegExp(`data-position="${code}"`), code);
      assert.ok(texte(ligne(html, JUGE)).includes(c[`fiche.position.${code}`]), `${code} ${langue}`);
    }
  }
  const f = ficheH5("confirmed");
  const sans = tableau({ ...proprietes(f), positions: (f.throughputPositions ?? []).filter((p) => p.quarter !== "2026-Q1") });
  assert.match(ligne(sans, "2026-Q1"), /data-position="unknown"/);
  assert.ok(texte(ligne(sans, "2026-Q1")).includes(en["fiche.position.unknown"]));
  const etrange = tableau({ ...proprietes(f), positions: [{ quarter: "2026-Q1", position: "odd_position" }] });
  assert.ok(texte(ligne(etrange, "2026-Q1")).includes(en["fiche.position.unknown"]));
  assert.doesNotMatch(texte(etrange), /odd_position/);
});

test("a P85 the answer does not give is an empty cell, the judged quarter is marked only when given, and no quarter gives no table", () => {
  const f = ficheH5("confirmed");
  const sansP85 = tableau({ ...proprietes(f), p85: [] });
  assert.equal((sansP85.match(/class="cellule cellule-vide" data-state="empty"/g) ?? []).length, 3);
  assert.equal((tableau(proprietes(f, { sansJuge: true })).match(/aria-current/g) ?? []).length, 0);
  assert.equal((tableau(proprietes(f)).match(/aria-current="true"/g) ?? []).length, 1);
  assert.equal(tableau({ trimestres: [], p85: [], positions: [] }), "");
});

test("the table's rows follow the quarters of the answer in their order, one row each, and its head holds the four columns", () => {
  const f = ficheH5("confirmed");
  const html = tableau(proprietes(f));
  assert.deepEqual([...lignes(html).keys()], (f.chart?.quarters ?? []).map((q) => q.quarter));
  assert.equal((html.match(/<th scope="col">/g) ?? []).length, 4);
  assert.match(html, /<caption>Cycle time and throughput by quarter<\/caption>/);
  assert.equal((html.match(/<th scope="row">/g) ?? []).length, 3);
  assert.deepEqual([...lignes(html).values()].map((l) => /<th scope="row">([^<]+)<\/th>/.exec(l)?.[1]), QUARTS);
});

// ---- the catalogues -----------------------------------------------------------------------------------------------------------------------

test("the six labels of hypothesis 5 are in both catalogues with the wording of D13 and the same arguments, and no other label is shipped for it", () => {
  const D13: Record<string, { en: string; fr: string }> = {
    "conviction.h5.figure.median": { en: "{period}: median cycle time, in days", fr: "{period} : cycle time médian, en jours" },
    "conviction.h5.figure.p85": { en: "{period}: P85 of the cycle time, in days", fr: "{period} : P85 du cycle time, en jours" },
    "conviction.h5.figure.throughput": { en: "{period}: {position}", fr: "{period} : {position}" },
    "conviction.h5.table.title": { en: "Cycle time and throughput by quarter", fr: "Cycle time et débit par trimestre" },
    "conviction.h5.band": { en: "Band of the team's own reference: {band}; double band: {doubleBand}.", fr: "Bande de la référence propre à l'équipe : {band} ; double bande : {doubleBand}." },
    "conviction.h5.floor": {
      en: "Throughput floor: {floor}; low floor: {lowFloor}, against the team's own reference.",
      fr: "Plancher du débit : {floor} ; plancher bas : {lowFloor}, par rapport à la référence propre à l'équipe.",
    },
  };
  for (const [cle, texteAttendu] of Object.entries(D13)) {
    assert.ok(cle in en && cle in fr, `texte de conviction absent : ${cle}`);
    assert.equal(en[cle], texteAttendu.en, cle);
    assert.equal(fr[cle], texteAttendu.fr, cle);
    const arguments_ = (t: string): string[] => [...t.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    assert.deepEqual(arguments_(en[cle]), arguments_(fr[cle]), cle);
  }
  assert.deepEqual(Object.keys(en).filter((k) => /^conviction\.h5\./.test(k)).sort(), Object.keys(D13).sort());
  assert.deepEqual(Object.keys(fr).filter((k) => /^conviction\.h5\./.test(k)).sort(), Object.keys(D13).sort());
});
