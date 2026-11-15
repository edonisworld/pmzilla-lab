// Quick-work reserve of the audit #629, first batch (R-20261107-12): A-06 (the labels of four insufficient quarters overlapped in the chart)
// and A-15 (the scroll position was kept from one screen to the next).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";

import { cleEcran, remonterSiEcranChange } from "../src/Application.ts";
import type { ReponseFiche } from "../src/api/fiche.ts";
import { Fiche } from "../src/composants/Fiche.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { construireOptions } from "../src/composants/optionsGraphique.ts";
import type { Libelles, Palette, Style } from "../src/composants/optionsGraphique.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { ContenuTableau } from "../src/pages/PageTableau.ts";
import { PageConviction } from "../src/pages/PageConviction.ts";
import { ficheSimulee } from "./fiche-simulee.ts";
import { ficheH1 } from "./fiches-h1.ts";
import { ficheH5 } from "./fiches-h5.ts";
import { rendre } from "./rendu.ts";
import { identifiantEquipe } from "@mothra/contract/equipe";
import type { Mesure, PointTrimestre, ReponseLeadCycle } from "@mothra/contract";

// ---- A-06: one label for a series made only of insufficient quarters -----------------------------------------------------------

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
const LIBELLES: Libelles = { lead: "LEAD", cycle: "CYCLE", axis: "AXIS", masked: "M", insufficient: "INSUFFICIENT", quarter: (brut) => `Q<${brut}>` };

const valeur = (v: number): Mesure => ({ state: "value", value: v });
const insuffisante: Mesure = { state: "insufficient_sample" };
const masquee: Mesure = { state: "masked", threshold: 5 };

type Objet = Record<string, unknown>;

// What the custom series draws for each of its marks, with a fake chart API of bands of width 100 centred on the rank (rank * 100 + 50).
function dessins(points: readonly PointTrimestre[]): Array<Objet[]> {
  const options = construireOptions(points, LIBELLES, PALETTE, STYLE) as Objet;
  const serie = (options.series as Objet[]).find((s) => s.type === "custom") as { data: number[][]; renderItem: (p: unknown, a: unknown) => { children: Objet[] } };
  return serie.data.map(([rang, marque]) => {
    const api = {
      value: (dimension: number) => [rang, marque][dimension],
      coord: ([x]: [number, number]) => [x * 100 + 50, 0],
      size: () => [100, 0],
    };
    return serie.renderItem({ coordSys: { x: 40, y: 10, width: 600, height: 200 } }, api).children;
  });
}

const QUATRE_INSUFFISANTS: PointTrimestre[] = [
  { quarter: "2025-Q4", lead: insuffisante, cycle: insuffisante },
  { quarter: "2026-Q1", lead: insuffisante, cycle: insuffisante },
  { quarter: "2026-Q2", lead: insuffisante, cycle: insuffisante },
  { quarter: "2026-Q3", lead: insuffisante, cycle: insuffisante },
  { quarter: "pooled_year", lead: valeur(30), cycle: valeur(10) },
];

test("A-06: four insufficient quarters draw their label once, centred on the four bands and as wide as they are together; every band keeps its outline", () => {
  const bandes = dessins(QUATRE_INSUFFISANTS);
  assert.equal(bandes.length, 4);
  for (const enfants of bandes) assert.equal((enfants[0] as Objet).type, "rect", "chaque bande garde son contour");
  const textes = bandes.flatMap((enfants) => enfants.filter((e) => e.type === "text"));
  assert.equal(textes.length, 1, "un seul libellé");
  const style = textes[0].style as Objet;
  assert.match(String(style.text), /INSUFFICIENT/);
  // Bands at ranks 0 to 3: the centres are 50 and 350, so the label is centred on 200 and as wide as the four bands (4 * 100).
  assert.equal(style.x, 200);
  assert.equal(style.width, 400);
  assert.equal(style.overflow, "break");
  assert.equal(bandes[0].length, 2, "le libellé est porté par la première bande");
  for (const enfants of bandes.slice(1)) assert.equal(enfants.length, 1);
});

test("A-06: a mix of states, or a single insufficient quarter, keeps one label per band as before", () => {
  const mixte: PointTrimestre[] = [
    { quarter: "2025-Q4", lead: valeur(40), cycle: valeur(10) },
    { quarter: "2026-Q1", lead: masquee, cycle: masquee },
    { quarter: "2026-Q2", lead: insuffisante, cycle: insuffisante },
    { quarter: "2026-Q3", lead: valeur(36), cycle: valeur(12) },
  ];
  const bandes = dessins(mixte);
  assert.equal(bandes.length, 2);
  for (const enfants of bandes) {
    assert.equal(enfants.length, 2);
    assert.equal((enfants[1].style as Objet).width, undefined, "pas de largeur imposée au libellé d'une bande");
  }
  const seule = dessins([
    { quarter: "2025-Q4", lead: valeur(40), cycle: valeur(10) },
    { quarter: "2026-Q1", lead: insuffisante, cycle: insuffisante },
  ]);
  assert.equal(seule.length, 1);
  assert.equal(seule[0].length, 2);
  // Insufficient quarters next to a masked one: two different states, so each band keeps its own label.
  const insuffisantsEtMasque = dessins([
    { quarter: "2026-Q1", lead: insuffisante, cycle: insuffisante },
    { quarter: "2026-Q2", lead: masquee, cycle: masquee },
  ]);
  assert.deepEqual(insuffisantsEtMasque.map((enfants) => enfants.length), [2, 2]);
});

test("A-06: the pooled year left aside, two insufficient quarters out of two are enough for the single label", () => {
  const bandes = dessins([
    { quarter: "2026-Q2", lead: insuffisante, cycle: insuffisante },
    { quarter: "2026-Q3", lead: insuffisante, cycle: insuffisante },
    { quarter: "pooled_year", lead: insuffisante, cycle: insuffisante },
  ]);
  // The pooled year is also insufficient here, but only the marks of the quarters are compared (review of the reserve): the two quarters
  // share one label, carried by the first band, and the pooled year keeps its own.
  assert.deepEqual(bandes.map((enfants) => enfants.length), [2, 1, 2]);
  const etendue = (bandes[0][1].style as Objet);
  assert.equal(etendue.x, 100);
  assert.equal(etendue.width, 200);
  // The pooled year sits one empty category after the last quarter (place 3): its label is centred on its own band, with no imposed width.
  const annee = bandes[2][1].style as Objet;
  assert.equal(annee.x, 350);
  assert.equal(annee.width, undefined);
  const sansAnnee = dessins([
    { quarter: "2026-Q2", lead: insuffisante, cycle: insuffisante },
    { quarter: "2026-Q3", lead: insuffisante, cycle: insuffisante },
  ]);
  assert.deepEqual(sansAnnee.map((enfants) => enfants.length), [2, 1]);
});

test("A-06: a quarter with values between two insufficient quarters is never crossed by a label, whatever the pooled year is", () => {
  const avecValeurAuMilieu = (annee: PointTrimestre): Array<Objet[]> =>
    dessins([
      { quarter: "2026-Q1", lead: insuffisante, cycle: insuffisante },
      { quarter: "2026-Q2", lead: valeur(40), cycle: valeur(10) },
      { quarter: "2026-Q3", lead: insuffisante, cycle: insuffisante },
      annee,
    ]);
  // Two insufficient quarters plus an insufficient pooled year make three marks for three quarters: counting the marks alone would merge them.
  for (const annee of [
    { quarter: "pooled_year", lead: insuffisante, cycle: insuffisante },
    { quarter: "pooled_year", lead: valeur(30), cycle: valeur(10) },
  ] as PointTrimestre[]) {
    const bandes = avecValeurAuMilieu(annee);
    for (const enfants of bandes) {
      assert.equal(enfants.length, 2, "un libellé par bande");
      assert.equal((enfants[1].style as Objet).width, undefined, "aucune largeur imposée : aucun libellé ne traverse le trimestre en valeur");
    }
  }
});

// ---- A-15: the page goes back to the top when the screen changes -------------------------------------------------------------

test("A-15: a change of screen scrolls back to the top, from the home, the dashboard and the conviction pages alike", () => {
  const cas: Array<[string, string]> = [
    ["", "#/tableau"],
    ["#/tableau", ""],
    ["#/tableau?team=abc", "#/conviction/lead_cycle_h1/fiche-1"],
    ["#/conviction/lead_cycle_h1/fiche-1", "#/conviction/lead_cycle_h5/fiche-2"],
    ["#/conviction/lead_cycle_h1/fiche-1", "#/conviction/lead_cycle_h1/fiche-2"],
    ["#/conviction/lead_cycle_h1", "#/tableau"],
  ];
  for (const [avant, apres] of cas) {
    let appels = 0;
    assert.equal(remonterSiEcranChange(avant, apres, () => (appels += 1)), true, `${avant} -> ${apres}`);
    assert.equal(appels, 1, `${avant} -> ${apres}`);
  }
});

test("A-15: no scroll when the address changes without changing the screen: the filters of the dashboard, the same page, an unknown address", () => {
  const cas: Array<[string, string]> = [
    ["#/tableau", "#/tableau?team=abc"],
    ["#/tableau?team=abc&from=2025-Q4", "#/tableau?team=def&from=2026-Q1&to=2026-Q3"],
    ["#/conviction/lead_cycle_h1/fiche-1", "#/conviction/lead_cycle_h1/fiche-1"],
    ["", ""],
    ["#/autre", "#/inconnue"],
  ];
  for (const [avant, apres] of cas) {
    let appels = 0;
    assert.equal(remonterSiEcranChange(avant, apres, () => (appels += 1)), false, `${avant} -> ${apres}`);
    assert.equal(appels, 0, `${avant} -> ${apres}`);
  }
});

test("A-15: the identity of a screen holds the sheet of a conviction page and nothing of the filters", () => {
  assert.equal(cleEcran("#/tableau?team=abc"), cleEcran("#/tableau"));
  assert.notEqual(cleEcran("#/conviction/lead_cycle_h1/a"), cleEcran("#/conviction/lead_cycle_h1/b"));
  assert.notEqual(cleEcran("#/conviction/lead_cycle_h1"), cleEcran("#/conviction/lead_cycle_h5"));
  assert.notEqual(cleEcran("#/tableau"), cleEcran(""));
});

// ---- Second batch of the reserve (R-20261107-33): A-12, A-14, A-08 labels, A-09, A-16, complement of A-05 ------------------------

const en = catalogues.en as Record<string, string>;
const fr = catalogues.fr as Record<string, string>;

test("A-12: the link of the empty state of a conviction page reuses the dashboard key of the navigation, in both languages", () => {
  const page = (langue: Langue): string =>
    rendre(h(QueryClientProvider, { client: new QueryClient() }, h(PageConviction, { conviction: { genre: "lead_cycle_h1" } })), langue);
  assert.match(page("en"), /<a class="lien" href="#\/tableau">Dashboard<\/a>/);
  assert.match(page("fr"), /<a class="lien" href="#\/tableau">Tableau de bord<\/a>/);
  assert.equal(en["nav.dashboard"], "Dashboard");
  assert.equal(fr["nav.dashboard"], "Tableau de bord");
});

test("A-14: the labels of the sheet start with a capital, in English and in French, and only the capital changes", () => {
  const attendus: Array<[string, string, string]> = [
    ["fiche.question.scope_growth", "Scope growth during a release", "Croissance du périmètre pendant une release"],
    ["fiche.question.scope_reachability", "Reachability of the release scope", "Atteignabilité du périmètre de la release"],
    ["fiche.question.predictability", "Predictability", "Prévisibilité"],
    ["fiche.question.next_version_quality", "Quality of the next version", "Qualité de la prochaine version"],
    ["fiche.signal.notRaised", "No attachment signal", "Pas de signal de rattachement"],
    [
      "fiche.attachmentSignal",
      "The change in this team's throughput may come from the attachment of tasks to teams, not from a real change",
      "La variation du débit de cette équipe peut venir du rattachement des tâches aux équipes, et non d'un changement réel",
    ],
    ["fiche.fixedBy.author_alone", "The author alone", "L'auteur seul"],
  ];
  for (const [cle, anglais, francais] of attendus) {
    assert.equal(en[cle], anglais, cle);
    assert.equal(fr[cle], francais, cle);
  }
});

test("A-08: the chart row replaces the method row, the insufficient samples are those of the verdict, and the quarters of the chart come on their own line", () => {
  assert.equal(en["fiche.method.method"], "Chart");
  assert.equal(fr["fiche.method.method"], "Graphique");
  assert.equal(en["fiche.method.insufficientSamples"], "Insufficient samples (verdict)");
  assert.equal(fr["fiche.method.insufficientSamples"], "Échantillons insuffisants (verdict)");
  assert.equal(en["fiche.method.insufficientQuarters"], "Quarters with an insufficient sample");
  assert.equal(fr["fiche.method.insufficientQuarters"], "Trimestres en échantillon insuffisant");
  const vide = { ...ficheSimulee().method, insufficientSamples: [] };
  const chart = {
    quarters: [
      { quarter: "2026-Q1", lead: valeur(40), cycle: valeur(10) },
      { quarter: "2026-Q2", lead: insuffisante, cycle: insuffisante },
    ],
    pooledYear: { quarter: "pooled_year", lead: insuffisante, cycle: valeur(3) },
  };
  const ouverte = (langue: Langue, modifs: Parameters<typeof ficheSimulee>[0]): string => rendre(h(Fiche, { fiche: ficheSimulee({ method: vide, ...modifs }), methodeOuverte: true }), langue);
  const anglais = ouverte("en", { chart });
  assert.ok(anglais.includes("<dt>Insufficient samples (verdict)</dt><dd><p>None.</p></dd>"));
  assert.ok(anglais.includes("<dt>Quarters with an insufficient sample</dt><dd>Q2 2026</dd>"), "the pooled year is not a quarter");
  const francais = ouverte("fr", { chart });
  assert.ok(francais.includes("<dt>Échantillons insuffisants (verdict)</dt><dd><p>Aucun.</p></dd>"));
  assert.ok(francais.includes("<dt>Trimestres en échantillon insuffisant</dt><dd>T2 2026</dd>"));
  // No chart, or no insufficient quarter in it: the line is left out.
  assert.ok(!ouverte("en", {}).includes("Quarters with an insufficient sample"));
  assert.ok(!ouverte("en", { chart: { quarters: [{ quarter: "2026-Q1", lead: valeur(40), cycle: valeur(10) }] } }).includes("Quarters with an insufficient sample"));
  // Review of the reserve (A-08): the list follows the state the chart draws. A quarter whose cycle time is masked is drawn masked, even if
  // its lead time is an insufficient sample: it is not listed.
  const masqueEtInsuffisant = {
    quarters: [
      { quarter: "2026-Q1", lead: insuffisante, cycle: masquee },
      { quarter: "2026-Q2", lead: masquee, cycle: insuffisante },
      { quarter: "2026-Q3", lead: valeur(40), cycle: insuffisante },
    ],
  };
  const liste = ouverte("en", { chart: masqueEtInsuffisant });
  assert.ok(liste.includes("<dt>Quarters with an insufficient sample</dt><dd>Q3 2026</dd>"), "only the quarter drawn insufficient is listed");
  // The period row of the simulated sheet also reads "Q1 2026" and "Q2 2026": the check is on the value of the line of the quarters only.
  const valeurListee = /<dt>Quarters with an insufficient sample<\/dt><dd>(.*?)<\/dd>/.exec(liste)?.[1];
  assert.equal(valeurListee, "Q3 2026");
  const toutMasque = { quarters: [{ quarter: "2026-Q1", lead: insuffisante, cycle: masquee }] };
  assert.ok(!ouverte("en", { chart: toutMasque }).includes("Quarters with an insufficient sample"));
});

test("A-09: the common reason no_data says what the view holds, in both languages", () => {
  assert.equal(en["fiche.reason.no_data"], "the view holds no data for the last closed quarter");
  assert.equal(fr["fiche.reason.no_data"], "la vue ne contient aucune donnée pour le dernier trimestre clos");
});

test("A-16: the thresholds are on the method face only, the footer of a conviction page holds no threshold line", () => {
  const source = readFileSync(new URL("../src/composants/FicheConviction.ts", import.meta.url), "utf8");
  assert.doesNotMatch(source, /data-seuil"|seuilsDuPied/);
  const methode = rendre(h(Fiche, { fiche: ficheSimulee(), methodeOuverte: true }), "en");
  assert.match(methode, /data-tableau="seuils"/);
});

test("A-16 (a): the method face of the hypothesis 1 page and of the hypothesis 5 page holds the thresholds table and the labels of its thresholds", () => {
  const cas: Array<[ReponseFiche, string]> = [
    [ficheH1("confirmed"), "h1_"],
    [ficheH5("confirmed"), "h5_"],
  ];
  for (const [f, prefixe] of cas) {
    const html = rendre(h(FicheConviction, { fiche: f, methodeOuverte: true }), "en").replaceAll("&#x27;", "'");
    assert.match(html, /data-tableau="seuils"/, prefixe);
    const codes = f.method.thresholds.map((s) => s.code).filter((code) => code.startsWith(prefixe));
    assert.ok(codes.length > 0, `the answer holds thresholds ${prefixe}`);
    for (const code of codes) assert.ok(html.includes(en[`fiche.threshold.${code}`]), code);
  }
});

test("R-20261108-08: the hypothesis 1 page carries the fixed sentence on the pooled year, in both languages; the hypothesis 5 page does not", () => {
  assert.equal(fr["conviction.pooledYearNote"], "Année groupée, sans les éléments créés plus d'un an avant leur engagement.");
  assert.equal(en["conviction.pooledYearNote"], "The pooled year leaves out the items created more than one year before their commitment.");
  for (const langue of ["fr", "en"] as const) {
    const phrase = (catalogues[langue] as Record<string, string>)["conviction.pooledYearNote"];
    const rendu = (f: ReponseFiche): string => rendre(h(FicheConviction, { fiche: f }), langue).replaceAll("&#x27;", "'");
    assert.ok(rendu(ficheH1("confirmed")).includes(phrase), `h1 ${langue}`);
    assert.ok(!rendu(ficheH5("confirmed")).includes(phrase), `h5 ${langue}`);
  }
});

test("R-20261108-08: the fixed sentence is on EVERY hypothesis 1 page (masked, insufficient sample, unknown verdict), once, and on no hypothesis 5 page", () => {
  const inconnu = { ...ficheH1("confirmed"), verdict: "mystery_verdict" } as unknown as ReponseFiche;
  const h1: Array<[string, ReponseFiche]> = [
    ["masked", ficheH1("masked")],
    ["insufficient_sample", ficheH1("insufficient_sample")],
    ["unknown verdict", inconnu],
  ];
  for (const langue of ["fr", "en"] as const) {
    const phrase = (catalogues[langue] as Record<string, string>)["conviction.pooledYearNote"];
    const rendu = (f: ReponseFiche): string => rendre(h(FicheConviction, { fiche: f }), langue).replaceAll("&#x27;", "'");
    for (const [cas, f] of h1) {
      const html = rendu(f);
      assert.ok(html.includes(phrase), `h1 ${cas} ${langue}`);
      assert.equal((html.match(/data-note="pooled-year"/g) ?? []).length, 1, `h1 ${cas} ${langue}: once`);
    }
    for (const etat of ["masked", "insufficient_sample", "confirmed"] as const) {
      const html = rendu(ficheH5(etat));
      assert.ok(!html.includes(phrase), `h5 ${etat} ${langue}`);
      assert.doesNotMatch(html, /data-note="pooled-year"/, `h5 ${etat} ${langue}`);
    }
  }
});

test("complement of A-05: when every cell of the view is masked for the team and the period, a fixed sentence says so; otherwise it is absent", () => {
  assert.equal(en["tableau.allMasked"], "Everything is masked for this team over the period; choose another team or another period.");
  assert.equal(fr["tableau.allMasked"], "Tout est masqué pour cette équipe sur la période ; choisissez une autre équipe ou une autre période.");
  const masque = { state: "masked", threshold: 5 } as const;
  const reponse: ReponseLeadCycle = {
    threshold: 5,
    dataDate: "2026-10-27",
    dataset: "synthetic",
    product: [{ quarter: "2026-Q1", lead: valeur(41), cycle: valeur(9), items: { state: "value", value: 120 } }],
    teams: [
      {
        team: "Team C",
        teamId: identifiantEquipe("Team C"),
        points: [
          { quarter: "2026-Q1", lead: masque, cycle: masque, items: masque },
          { quarter: "2026-Q2", lead: masque, cycle: masque, items: masque },
        ],
      },
      {
        team: "Team B",
        teamId: identifiantEquipe("Team B"),
        points: [
          { quarter: "2026-Q1", lead: masque, cycle: masque, items: masque },
          { quarter: "2026-Q2", lead: valeur(22), cycle: valeur(5), items: { state: "value", value: 19 } },
        ],
      },
    ],
  };
  const contenu = (portee: string, langue: Langue): string =>
    rendre(h(ContenuTableau, { reponse, portee, surPortee: () => undefined, fiche: { genre: "aucune" }, surFaire: () => undefined, surCreer: () => undefined, simulee: true }), langue);
  assert.ok(contenu("Team C", "en").includes(en["tableau.allMasked"]));
  assert.ok(contenu("Team C", "fr").includes(fr["tableau.allMasked"]));
  assert.ok(!contenu("Team B", "en").includes(en["tableau.allMasked"]), "one readable cell is enough to leave the sentence out");
  assert.ok(!contenu("", "en").includes(en["tableau.allMasked"]), "the product is not masked");
  // R-20261108-03 Q9 (a): product scope with everything masked, no sentence (it names a team); team scope with everything masked, the sentence.
  const produitMasque: ReponseLeadCycle = {
    ...reponse,
    product: [{ quarter: "2026-Q1", lead: masque, cycle: masque, items: masque }],
  };
  const contenuProduit = (portee: string): string =>
    rendre(h(ContenuTableau, { reponse: produitMasque, portee, surPortee: () => undefined, fiche: { genre: "aucune" }, surFaire: () => undefined, surCreer: () => undefined, simulee: true }), "en");
  assert.ok(!contenuProduit("").includes(en["tableau.allMasked"]), "product scope, everything masked: no sentence");
  assert.ok(contenuProduit("Team C").includes(en["tableau.allMasked"]), "team scope, everything masked: the sentence");
});
