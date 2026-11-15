// The catalogue of the components (mothra-demo-habillage D17, ADR 0002 Q9, R-20261031-77): every component of the design system in each of its
// states, and the three page templates, drawn with the server renderer. Lot 3a draws no sheet answer: its components take free inputs; the
// sheet pages computed by the contract from the synthetic view rows (R-20261031-61, R-20261101-07) come with lot 3b. Run by the npm script
// `catalogue` of the front package:
// `npm run catalogue -- <output file>`. The page is written outside the repository and outside the bundle (this file lives in scripts/, which
// the bundle never reads); a missing path is refused. The style sheets are inlined from the generated tokens and the stylesheet, so the page
// is self-contained: no network, no external resource, no font file (the two font variables are set to the system stacks, as the swatch page
// does) and the logo is embedded. It also shows the colour swatches of the former page `pastilles`.
// Lot 3a holds the components of the shell, the home and the empty state; lot 3b adds the sheet status, the competing explanations, the sheet
// pages of hypothesis 1 computed by the contract (the reduced published sheet among them) and, with lot 1b on main (phase B), the parts bar with
// its markers in every state and the composition by quarter; lot 3c adds the stability table in each of its states and the sheet pages of
// hypothesis 5 computed by the contract; the disabled choice (with its reason, D18) is lot 3d's.
// Replaces: nothing yet (the swatch page `pastilles` stays until the author validates this catalogue). Removal: with the page served in
// development mode, after the demo.
import { existsSync, readFileSync, realpathSync, renameSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { IntlProvider } from "react-intl";

import { BadgeVerdict, ETATS_BADGE } from "../src/composants/BadgeVerdict.ts";
import { Banniere } from "../src/composants/Banniere.ts";
import { BarreParts, CompositionTrimestres } from "../src/composants/BarreParts.ts";
import type { MarqueursBarre, PropsBarreParts } from "../src/composants/BarreParts.ts";
import { CelluleInsuffisante, CelluleMasquee } from "../src/composants/Cellule.ts";
import { ChoixDesactive } from "../src/composants/ChoixDesactive.ts";
import { CarteConviction } from "../src/composants/CarteConviction.ts";
import { EtatVide } from "../src/composants/EtatVide.ts";
import { ExplicationsConcurrentes } from "../src/composants/ExplicationsConcurrentes.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { NavigationLaterale } from "../src/composants/NavigationLaterale.ts";
import { StatutFiche } from "../src/composants/StatutFiche.ts";
import { TableauStabilite } from "../src/composants/TableauStabilite.ts";
import type { PropsTableauStabilite } from "../src/composants/TableauStabilite.ts";
import type { ExplicationFiche, ReponseFiche } from "../src/api/fiche.ts";
import { Coquille } from "../src/gabarits/Coquille.ts";
import { GabaritFiche } from "../src/gabarits/GabaritFiche.ts";
import { GabaritIndicateurs } from "../src/gabarits/GabaritIndicateurs.ts";
import { compositionConviction } from "@mothra/contract/composition";
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";

import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { MARQUE } from "../src/marque.ts";
import { CAS_H1, ficheH1 } from "../test/fiches-h1.ts";
import { CAS_H5, ficheH5 } from "../test/fiches-h5.ts";
import { valeurJeton } from "./generer-jetons.ts";
import type { Jetons } from "./generer-jetons.ts";
import { dansLe, racineGit } from "./sortie.ts";

// The logo of the mark is embedded in the page (a `data:` address built from the file of public/logos/): the page is self-contained, and the
// image it shows is the shipped file, byte for byte (the test decodes it and compares).
// public/logos/ is excluded from the public edition (R-20261114-107): without the file the string is empty and the specimen shows a text
// in place of the image, with no error at load; in the private repository the file is read as before.
const FICHIER_LOGO = new URL(`../public${MARQUE.logo}`, import.meta.url);
const LOGO_INTEGRE = existsSync(FICHIER_LOGO) ? `data:image/svg+xml;base64,${readFileSync(FICHIER_LOGO).toString("base64")}` : "";
const LOGO_ABSENT = '<span class="logo-absent">logo absent de l\'édition publique</span>';

// Each specimen is rendered by its own call, so `useId` would give the same identifier to the specimens of one page (the reason of the disabled
// choice in English and in French, for one): a prefix that counts the specimens keeps the identifiers of the page unique. The counter restarts
// at each generation, so the page stays the same from one run to the next.
let rangDeRendu = 0;

function rendre(element: ReactElement, langue: Langue = "en"): string {
  rangDeRendu += 1;
  const html = renderToStaticMarkup(h(IntlProvider, { locale: langue, messages: catalogues[langue] }, element), { identifierPrefix: `s${rangDeRendu}-` });
  // React 19 writes a preload hint (a `link` element with the file address) before an image: the page loads nothing, so the hint is dropped.
  const sansPreload = html.replaceAll(`<link rel="preload" as="image" href="${MARQUE.logo}"/>`, "");
  if (LOGO_INTEGRE === "") return sansPreload.replace(new RegExp(`<img\\b[^>]*\\bsrc="${MARQUE.logo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"[^>]*>`, "g"), LOGO_ABSENT);
  return sansPreload.replaceAll(`src="${MARQUE.logo}"`, `src="${LOGO_INTEGRE}"`);
}

function echapper(texte: string): string {
  return texte.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// One captioned specimen: the state's name and its rendering.
function specimen(titre: string, html: string): string {
  return `<figure class="specimen"><figcaption>${echapper(titre)}</figcaption><div class="specimen-corps">${html}</div></figure>`;
}

function section(titre: string, specimens: string[]): string {
  return `<section class="catalogue-section"><h2>${echapper(titre)}</h2>${specimens.join("\n")}</section>`;
}

// The cards of the home: the statement and the link of each conviction of the contract's list. No sheet is read (Q158 (b), R-20261101-42).
function cartesDeLaPage(): ReactElement[] {
  return GRAPHIQUES_DE_FICHE.map((genre) => h(CarteConviction, { key: genre, genre }));
}

// The competing explanations in each state of D17: the three states with and without a reason, an unknown name, reason and state (fallbacks),
// and the attachment signal shown, not raised and masked. The inputs are free (rule 4): the states are the component's, not the contract's.
const EXPLICATIONS_DU_CATALOGUE: ReadonlyArray<{ titre: string; explications: ExplicationFiche[]; signalMontre: boolean; motifsSignal: string[] }> = [
  { titre: "ruled out, no reason", explications: [{ name: "capacity", state: "ruled_out" }], signalMontre: false, motifsSignal: [] },
  { titre: "not ruled out, with a reason", explications: [{ name: "capacity", state: "not_ruled_out", reason: "no_adopted_threshold" }], signalMontre: false, motifsSignal: [] },
  { titre: "not ruled out, no reason", explications: [{ name: "unplanned_work", state: "not_ruled_out" }], signalMontre: false, motifsSignal: [] },
  { titre: "not measurable, with a reason", explications: [{ name: "dependencies", state: "not_measurable", reason: "no_data" }], signalMontre: false, motifsSignal: [] },
  { titre: "not measurable, no reason", explications: [{ name: "dependencies", state: "not_measurable" }], signalMontre: false, motifsSignal: [] },
  {
    titre: "unknown name, state and reason (fallbacks)",
    explications: [{ name: "unknown_name", state: "unknown_state", reason: "unknown_reason" } as unknown as ExplicationFiche],
    signalMontre: false,
    motifsSignal: [],
  },
  { titre: "attachment signal shown", explications: [{ name: "capacity", state: "ruled_out" }], signalMontre: true, motifsSignal: [] },
  { titre: "attachment signal masked", explications: [{ name: "capacity", state: "ruled_out" }], signalMontre: false, motifsSignal: ["tasks_without_team_share_masked"] },
];

// The parts bar in each state of D17. The markers are the ones the contract serves for the sheet "confirmed" (D15); the other inputs are free (rule 4).
const MARQUEURS_SERVIS: MarqueursBarre = ficheH1("confirmed").waitShares?.markers ?? { refutation: { ratio: 1.5, inScale: true, share: 33 }, confirmation: { ratio: 3, inScale: true, share: 67 }, applicable: true };
const PARTS_DU_CATALOGUE = { state: "value" as const, waitShare: 60, workShare: 40 };

function barre(parts: PropsBarreParts["parts"], marqueurs: MarqueursBarre | undefined, langue: Langue = "en"): string {
  return rendre(h(BarreParts, { forme: "barre", code: "median", etiquette: "conviction.bar.labelMedian", parts, marqueurs }), langue);
}

// The composition by quarter: the sheet "confirmed" as the contract computes it, then the same sheet with one measure of three quarters changed to
// show a masked, an insufficient and a not comparable row (the lengths come from the contract's axis, not from here).
function compositionDuCatalogue(melangee: boolean): ReactElement {
  const f = ficheH1("confirmed");
  const points = (f.chart?.quarters ?? []).map((p, rang) => {
    if (!melangee) return p;
    if (rang === 0) return { ...p, lead: { state: "masked" as const, threshold: 5 } };
    if (rang === 1) return { ...p, cycle: { state: "insufficient_sample" as const } };
    if (rang === 2) return { ...p, lead: { state: "value" as const, value: 8 } };
    return p;
  });
  return h(CompositionTrimestres, { quarters: compositionConviction({ ...f, chart: { ...f.chart, quarters: points } } as ReponseFiche).quarters });
}

// A sheet answer of the contract whose window limit codes are changed (R-20261114-49, design D8): neither of the two codes, or both. The contract never writes
// such a sheet, a caller error is what the specimen shows: the mention `tableau.panel.mentionMissing` and no grouped row. The only hand-set field is the list of limits.
function sansCodeDeFenetre(f: ReponseFiche, lesDeux = false): ReponseFiche {
  const autres = f.method.limits.filter((l) => l !== "views_last_four_quarters" && l !== "views_last_three_closed_quarters");
  const limits = lesDeux ? [...autres, "views_last_four_quarters", "views_last_three_closed_quarters"] : autres;
  return { ...f, method: { ...f.method, limits } } as ReponseFiche;
}

// The stability table of hypothesis 5 in each state of D17 (lot 3c): the props come from sheet answers computed by the contract, never written by
// hand. A missing position and a missing P85 are the only derived inputs: one entry of the answer is left out, to show the fallback and the empty cell.
// R-20261114-83: `positionJuge` sets the position of the judged quarter, the third derived input: with three closed quarters a masked judged throughput gives
// no reference and so no position on a sheet, yet the table must still show the position code `masked` of the contract's list.
function propsStabilite(f: ReponseFiche, options: { sansPosition?: string; sansP85?: boolean; sansJuge?: boolean; positionJuge?: "masked" } = {}): PropsTableauStabilite {
  const juge = compositionConviction(f).measured.quarter;
  return {
    trimestres: f.chart?.quarters ?? [],
    p85: options.sansP85 === true ? [] : (f.p85?.quarters ?? []),
    positions: (f.throughputPositions ?? [])
      .filter((p) => p.quarter !== options.sansPosition)
      .map((p) => (options.positionJuge !== undefined && p.quarter === juge ? { ...p, position: options.positionJuge } : p)),
    juge: options.sansJuge === true ? undefined : compositionConviction(f).measured.quarter,
  };
}

function stabilite(f: ReponseFiche, options: Parameters<typeof propsStabilite>[1] = {}, langue: Langue = "en"): string {
  return rendre(h(TableauStabilite, propsStabilite(f, options)), langue);
}

function sections(): string[] {
  const badges = ETATS_BADGE.flatMap((etat) => (["en", "fr"] as const).map((langue) => specimen(`badge ${etat} ${langue}`, rendre(h(BadgeVerdict, { etat }), langue))));
  const cartes = (["en", "fr"] as const).flatMap((langue) =>
    cartesDeLaPage().map((carte, rang) => specimen(`card ${rang + 1} ${langue}`, rendre(carte, langue))),
  );
  // The side navigation in each of its states: home current, a conviction current, the dashboard current, no dashboard entry (the source is
  // not given), no conviction served (lot 3a: none is shipped).
  // The entry of the sheets in progress (audit 629, A-04) is offered with the source of the life cycle: in the state `fiches` it is the current one.
  const navigation = (etat: "accueil" | "conviction" | "tableau" | "sans-tableau" | "sans-conviction" | "fiches") =>
    h(NavigationLaterale, {
      accueilCourant: etat === "accueil" || etat === "sans-tableau" || etat === "sans-conviction",
      convictions: etat === "sans-conviction" ? [] : GRAPHIQUES_DE_FICHE.map((genre, rang) => ({ genre, courante: etat === "conviction" && rang === 0 })),
      tableau: etat === "sans-tableau" ? undefined : { courant: etat === "tableau" },
      fiches: etat === "fiches" ? { courant: true } : undefined,
    });
  const accueil = h(GabaritIndicateurs, { titre: "home.title", introduction: "home.intro", cartes: cartesDeLaPage(), pied: h("p", null, "-") });
  const fiche = h(GabaritFiche, { enonce: "conviction.statement.lead_cycle_h1", preuve: h(EtatVide, { phrase: "tableau.form.teamRequired", action: { cle: "tableau.title", adresse: "#/tableau" } }) });
  return [
    section("Verdict badge, every state, both languages", badges),
    section("Banner", [
      specimen("synthetic dataset", rendre(h(Banniere, { jeu: "synthetic" }))),
      specimen("synthetic dataset (French)", rendre(h(Banniere, { jeu: "synthetic" }), "fr")),
      specimen("real data, reduced form", rendre(h(Banniere, { jeu: "real" }))),
      specimen("real data, reduced form (French)", rendre(h(Banniere, { jeu: "real" }), "fr")),
      specimen("answer without a dataset code or not known yet: no banner (the shell draws none)", rendre(h(Coquille, { navigation: navigation("accueil") }, h("p", null, "-")))),
    ]),
    section("Side navigation", [
      specimen("home current", rendre(navigation("accueil"))),
      specimen("conviction current", rendre(navigation("conviction"))),
      specimen("dashboard current", rendre(navigation("tableau"))),
      specimen("without a dashboard entry (source not given)", rendre(navigation("sans-tableau"))),
      specimen("without a conviction served", rendre(navigation("sans-conviction"))),
      specimen("home current (French)", rendre(navigation("accueil"), "fr")),
      specimen("conviction current (French)", rendre(navigation("conviction"), "fr")),
      specimen("dashboard current (French)", rendre(navigation("tableau"), "fr")),
      specimen("sheets in progress current", rendre(navigation("fiches"))),
      specimen("sheets in progress current (French)", rendre(navigation("fiches"), "fr")),
    ]),
    section("Conviction card", cartes),
    section("Explained empty state", [
      specimen("with an action", rendre(h(EtatVide, { phrase: "tableau.form.teamRequired", action: { cle: "tableau.title", adresse: "#/tableau" } }))),
      specimen("without an action", rendre(h(EtatVide, { phrase: "tableau.form.teamRequired" }))),
      specimen("with an action (French)", rendre(h(EtatVide, { phrase: "tableau.form.teamRequired", action: { cle: "tableau.title", adresse: "#/tableau" } }), "fr")),
      specimen("without an action (French)", rendre(h(EtatVide, { phrase: "tableau.form.teamRequired" }), "fr")),
    ]),
    // The disabled choice (lot 3d, D18): the option of "make it a sheet" that real data cannot take, shown disabled with its reason linked by
    // aria-describedby; here beside an enabled option of the same group, in each language.
    section(
      "Disabled choice with its reason",
      (["en", "fr"] as const).map((langue) =>
        specimen(
          `disabled choice, hypothesis 5 on real data, beside an enabled choice (${langue})`,
          rendre(
            h(
              "fieldset",
              null,
              h(ChoixDesactive, { nom: `catalogue-${langue}`, valeur: "lead_cycle_h5", libelle: "conviction.nav.lead_cycle_h5", raison: "tableau.form.h5RealUnavailable" }),
              h("label", { className: "portee" }, h("input", { type: "radio", name: `catalogue-${langue}`, value: "lead_cycle_h1" }), catalogues[langue]["conviction.nav.lead_cycle_h1"]),
            ),
            langue,
          ),
        ),
      ),
    ),
    section(
      "Sheet status",
      (["en", "fr"] as const).flatMap((langue) => [
        specimen(`status draft ${langue}`, rendre(h(StatutFiche, { etat: "draft" }), langue)),
        specimen(`status reviewed ${langue}`, rendre(h(StatutFiche, { etat: "reviewed" }), langue)),
        specimen(`status published with date, version and frozen statement ${langue}`, rendre(h(StatutFiche, { etat: "published", publieLe: "2026-11-02", version: 1 }), langue)),
      ]),
    ),
    section(
      "Competing explanations",
      [
        ...EXPLICATIONS_DU_CATALOGUE.map((e) => specimen(`explanations: ${e.titre}`, rendre(h(ExplicationsConcurrentes, e)))),
        ...EXPLICATIONS_DU_CATALOGUE.slice(0, 5).map((e) => specimen(`explanations: ${e.titre} (French)`, rendre(h(ExplicationsConcurrentes, e), "fr"))),
      ],
    ),
    // The parts bar with threshold markers (lot 3b, phase B, D17): every state of the bar and of a row of the chart, then the composition by quarter.
    section("Parts bar with threshold markers", [
      specimen("bar with values, markers applicable", barre(PARTS_DU_CATALOGUE, MARQUEURS_SERVIS)),
      specimen("bar with values (French)", barre(PARTS_DU_CATALOGUE, MARQUEURS_SERVIS, "fr")),
      specimen("bar with values, markers not applicable", barre(PARTS_DU_CATALOGUE, { ...MARQUEURS_SERVIS, applicable: false })),
      specimen("bar with values, a marker out of scale", barre(PARTS_DU_CATALOGUE, { ...MARQUEURS_SERVIS, refutation: { ratio: 1, inScale: false } })),
      specimen("bar masked", barre({ state: "masked" }, MARQUEURS_SERVIS)),
      specimen("bar masked (French)", barre({ state: "masked" }, MARQUEURS_SERVIS, "fr")),
      specimen("bar insufficient sample, dotted markers", barre({ state: "insufficient_sample" }, { ...MARQUEURS_SERVIS, applicable: false })),
      specimen("bar not comparable", barre({ state: "not_comparable" }, MARQUEURS_SERVIS)),
      specimen("row of the chart without markers", rendre(h(BarreParts, { forme: "ligne", parts: { state: "value", waitShare: 75, workShare: 25 }, longueur: 60, libelleAttente: "30 d", libelleTravail: "10 d" }))),
      ...(["masked", "insufficient_sample", "not_comparable"] as const).map((etat) => specimen(`row of the chart ${etat}`, rendre(h(BarreParts, { forme: "ligne", parts: { state: etat } })))),
      specimen("composition by quarter, on the common axis", rendre(compositionDuCatalogue(false))),
      specimen("composition by quarter, on the common axis (French)", rendre(compositionDuCatalogue(false), "fr")),
      specimen("composition by quarter, with a masked, an insufficient and a not comparable quarter", rendre(compositionDuCatalogue(true))),
    ]),
    // The sheet pages are computed by the contract (R-20261101-07): one per display state and the case where the two medians cannot be compared,
    // on the complete answer (synthetic dataset) and on the reduced one (real data); lot 3b, with the bars of lot 1b, and one without `waitShares`.
    section("Sheet pages computed by the contract (hypothesis 1)", [
      // The label of Q259 (a), R-20261101-125: these states come from invented rows, not from the real screen; the state "confirmed" in
      // particular is set on rows the contract would cap to "not settled" for a team sheet (D20, D33).
      `<p class="catalogue-etiquette"><strong>${echapper("synthetic data, verdict catalogue")} / ${echapper("données synthétiques, catalogue des verdicts")}</strong></p>`,
      ...CAS_H1.flatMap((cas) =>
        (["synthetic", "real"] as const).map((jeu) =>
          specimen(`sheet page ${cas}, ${jeu === "real" ? "real data, reduced form" : "synthetic dataset"}`, rendre(h(FicheConviction, { fiche: ficheH1(cas, { jeu }), seuilMasquage: 5 }))),
        ),
      ),
      specimen("sheet page confirmed, published, real data, reduced form (French)", rendre(h(FicheConviction, { fiche: ficheH1("confirmed", { jeu: "real" }), seuilMasquage: 5 }), "fr")),
      // The answer built without the service layer carries no `waitShares`: no bar and no chart, the ratios as text (the fallback of D4).
      specimen("sheet page confirmed, real data, without waitShares (fallback of D4)", rendre(h(FicheConviction, { fiche: (({ waitShares: _, ...sans }) => sans as ReponseFiche)(ficheH1("confirmed", { jeu: "real" })), seuilMasquage: 5 }))),
      specimen("sheet page draft without effect nor cause", rendre(h(FicheConviction, { fiche: ficheH1("confirmed", { etat: "draft", texte: false }) }))),
      specimen("sheet page reviewed", rendre(h(FicheConviction, { fiche: ficheH1("confirmed", { etat: "reviewed" }) }))),
      specimen("sheet page confirmed, real data, method face open", rendre(h(FicheConviction, { fiche: ficheH1("confirmed", { jeu: "real" }), seuilMasquage: 5, methodeOuverte: true }))),
      // Audit 629, A-01, A-02 and A-04: the link to the screen of the life cycle, the attachment signal next to the verdict, and the sentence
      // that stands for a finding code the table does not know (the raw code is never written into the page).
      specimen("sheet page confirmed, with the link to review or publish the sheet", rendre(h(FicheConviction, { fiche: ficheH1("confirmed"), adresseCycle: "#/fiche/f-1" }))),
      specimen("sheet page confirmed, attachment signal next to the verdict", rendre(h(FicheConviction, { fiche: { ...ficheH1("confirmed"), attachmentSignalShown: true } }))),
      specimen("sheet page confirmed, unknown finding code (fallback sentence)", rendre(h(FicheConviction, { fiche: { ...ficheH1("confirmed"), verdictFindings: ["code_inconnu"] } as unknown as ReponseFiche }))),
      // Three closed quarters (R-20261114-49, design D7 and D8): the sheets above carry `views_last_four_quarters` (a sheet frozen before the change: its former
      // label « Pooled year » and its former note, `data-note="pooled-year"`); a new sheet carries `views_last_three_closed_quarters` (« Last three quarters »,
      // `data-note="last-three-quarters"`); a sheet with neither code, or both, is a caller error: the mention `tableau.panel.mentionMissing`, no grouped row.
      specimen("sheet page confirmed, a new sheet: « Last three quarters » and its note (data-note last-three-quarters)", rendre(h(FicheConviction, { fiche: ficheH1("confirmed", { limite: "neuve" }), seuilMasquage: 5 }))),
      specimen("sheet page confirmed, a new sheet, real data, reduced form (French)", rendre(h(FicheConviction, { fiche: ficheH1("confirmed", { jeu: "real", limite: "neuve" }), seuilMasquage: 5 }), "fr")),
      specimen("sheet page confirmed, a sheet frozen before the change: « Pooled year » and its former note (data-note pooled-year)", rendre(h(FicheConviction, { fiche: ficheH1("confirmed", { limite: "figee" }), seuilMasquage: 5 }))),
      specimen("sheet page confirmed, neither window limit code: the mention tableau.panel.mentionMissing, no grouped row", rendre(h(FicheConviction, { fiche: sansCodeDeFenetre(ficheH1("confirmed")), seuilMasquage: 5 }))),
      specimen("sheet page confirmed, both window limit codes: the same mention", rendre(h(FicheConviction, { fiche: sansCodeDeFenetre(ficheH1("confirmed"), true), seuilMasquage: 5 }))),
      specimen("sheet page confirmed, neither window limit code (French)", rendre(h(FicheConviction, { fiche: sansCodeDeFenetre(ficheH1("confirmed")), seuilMasquage: 5 }), "fr")),
    ]),
    // The stability table of hypothesis 5 (lot 3c, D17): values, a masked measure, an insufficient measure, each position code, a missing position,
    // the judged quarter marked or not; every one from a sheet answer computed by the contract.
    section("Stability table (hypothesis 5)", [
      specimen("stability table, values, every position within the band, judged quarter marked", stabilite(ficheH5("confirmed"))),
      specimen("stability table, values (French)", stabilite(ficheH5("confirmed"), {}, "fr")),
      specimen("stability table, judged throughput under the floor", stabilite(ficheH5("not_settled"))),
      specimen("stability table, judged throughput under the low floor", stabilite(ficheH5("refuted"))),
      specimen("stability table, judged throughput masked", stabilite(ficheH5("confirmed"), { positionJuge: "masked" })),
      specimen("stability table, judged P85 an insufficient sample", stabilite(ficheH5("p85_insufficient"))),
      specimen("stability table, judged P85 masked", stabilite(ficheH5("p85_masked"))),
      specimen("stability table, a missing position (fallback sentence)", stabilite(ficheH5("confirmed"), { sansPosition: "2026-Q1" })),
      specimen("stability table, P85 not given (empty cells)", stabilite(ficheH5("confirmed"), { sansP85: true })),
      specimen("stability table, no quarter marked", stabilite(ficheH5("confirmed"), { sansJuge: true })),
      specimen("stability table, under the floor (French)", stabilite(ficheH5("not_settled"), {}, "fr")),
    ]),
    // The sheet pages of hypothesis 5 are computed by the contract (R-20261101-07): one per display state and the cases the page tells apart, on the
    // complete answer (synthetic dataset) and on the reduced one (real data). The page holds no bar and no waiting (D4).
    section("Sheet pages computed by the contract (hypothesis 5)", [
      `<p class="catalogue-etiquette"><strong>${echapper("synthetic data, verdict catalogue")} / ${echapper("données synthétiques, catalogue des verdicts")}</strong></p>`,
      // The pages "real data, reduced form" below are specimens of the component only: the application never serves hypothesis 5 on real data (R-20261103-14, Q1 (a)).
      `<p class="catalogue-etiquette"><strong>${echapper("real data, reduced form: specimens of the component only, the application never serves this page on real data")} / ${echapper("données réelles, forme réduite : spécimens du composant seulement, l'application ne sert jamais cette page sur données réelles")}</strong></p>`,
      ...CAS_H5.flatMap((cas) =>
        (["synthetic", "real"] as const).map((jeu) =>
          specimen(`sheet page h5 ${cas}, ${jeu === "real" ? "real data, reduced form" : "synthetic dataset"}`, rendre(h(FicheConviction, { fiche: cas === "throughput_masked" ? ({ ...ficheH5("not_settled", { jeu }), h5Reasons: ["throughput_masked"] } as ReponseFiche) : ficheH5(cas, { jeu }), seuilMasquage: 5 }))),
        ),
      ),
      specimen("sheet page h5 confirmed, published, real data, reduced form (French)", rendre(h(FicheConviction, { fiche: ficheH5("confirmed", { jeu: "real" }), seuilMasquage: 5 }), "fr")),
      // R-20261114-83: with three closed quarters a masked judged throughput gives "insufficient sample" and no reason; the reason `throughput_masked` is shown
      // here on a "not settled" answer that carries it (the only hand-set field), so that the page still shows how a reason is told under the badge.
      specimen("sheet page h5 throughput_masked, synthetic dataset (French)", rendre(h(FicheConviction, { fiche: { ...ficheH5("not_settled"), h5Reasons: ["throughput_masked"] } as ReponseFiche, seuilMasquage: 5 }), "fr")),
      specimen("sheet page h5 draft without effect nor cause", rendre(h(FicheConviction, { fiche: ficheH5("confirmed", { etat: "draft", texte: false }) }))),
      specimen("sheet page h5 reviewed", rendre(h(FicheConviction, { fiche: ficheH5("confirmed", { etat: "reviewed" }) }))),
    ]),
    section("Masked cell (existing)", [specimen("masked cell", rendre(h("table", null, h("tbody", null, h("tr", null, h(CelluleMasquee))))))]),
    // The insufficient-sample cell (A-13): its own dotted outline and its own icon shape, apart from the masked cell above.
    section("Insufficient-sample cell", [
      specimen("insufficient-sample cell", rendre(h("table", null, h("tbody", null, h("tr", null, h(CelluleInsuffisante)))))),
      specimen("insufficient-sample cell (French)", rendre(h("table", null, h("tbody", null, h("tr", null, h(CelluleInsuffisante)))), "fr")),
    ]),
    section("Template: shell (side navigation, banner, main column)", [
      specimen("shell, synthetic dataset", rendre(h(Coquille, { navigation: navigation("accueil"), jeu: "synthetic" }, h("p", null, "-")))),
      specimen("shell, real data", rendre(h(Coquille, { navigation: navigation("accueil"), jeu: "real" }, h("p", null, "-")))),
    ]),
    section("Template: sheet page", [specimen("sheet page without a sheet", rendre(fiche))]),
    section("Template: indicators page", [specimen("home grid, one card per conviction", rendre(accueil))]),
  ];
}

// The swatches of the former page `pastilles` (control 24.6): the state, verdict, series and data colours side by side, resolved from the token source.
function pastilles(source: Jetons): string {
  const prefixes = ["state-", "verdict-", "series-", "data-"];
  const noms = Object.keys(source.light).filter((n) => n === "info" || prefixes.some((p) => n.startsWith(p)));
  const valeur = (nom: string): string => {
    const v = valeurJeton(source, nom);
    if (v === undefined) throw new Error(`jeton sans valeur : ${nom}`);
    return v;
  };
  const estFond = (nom: string): boolean => nom.endsWith("-tint") || nom.endsWith("-bg");
  const aplats = noms.map((n) => `<div class="sw"><div class="sw-c" style="background:${valeur(n)}"></div><div class="sw-l">${echapper(n)}<br>${valeur(n)}</div></div>`).join("");
  const puces = noms.map((n) => `<span class="sw-puce" style="border:2px solid ${valeur(n)}"><span class="sw-point" style="background:${valeur(n)}"></span>${echapper(n)} ${valeur(n)}</span>`).join("");
  const textes = noms.filter((n) => !estFond(n)).map((n) => `<span style="color:${valeur(n)}">${echapper(n)} ${valeur(n)}</span>`).join(" · ");
  const fonds = noms.filter(estFond).map((n) => `<div class="sw-fond" style="background:${valeur(n)}">Ordinary ink on ${echapper(n)} ${valeur(n)}</div>`).join("");
  return `<section class="catalogue-section"><h2>Colour swatches (state, verdict, series and data colours; the page for the colour filters of the system)</h2><div class="sw-rangee">${aplats}</div><div class="sw-puces">${puces}</div><p>${textes}</p>${fonds}</section>`;
}

export function genererCatalogue(source: Jetons, css: string): string {
  rangDeRendu = 0;
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mothra component catalogue</title>
<style>
${css}
:root{--font-family:-apple-system,system-ui,sans-serif;--font-family-heading:Georgia,serif}
.catalogue-section{margin:32px 0}.specimen{margin:0 0 24px}.specimen figcaption{font-size:13px;margin-bottom:6px}.specimen-corps{max-width:900px}
.sw-rangee,.sw-puces{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px}.sw{width:150px}.sw-c{height:60px}.sw-l{font-size:12px}
.sw-puce{display:inline-flex;gap:6px;padding:4px 10px;font-size:13px}.sw-point{width:12px;height:12px;border-radius:50%}.sw-fond{padding:8px 12px;margin-bottom:6px}
</style></head><body>
<h1>Mothra component catalogue</h1>
<p>Every component of the design system in each of its states, and the three page templates, as drawn by lots 3a, 3b and 3c (the sheet status, the competing explanations, the parts bar with its markers, the composition by quarter, the stability table and the sheet pages of hypotheses 1 and 5 computed by the contract). Not part of the bundle.</p>
${sections().join("\n")}
${pastilles(source)}
</body></html>
`;
}

export class RefusSortie extends Error {}

// Writes the page to `sortie`, atomically. Refuses without a path, or inside the repository.
export function ecrireCatalogue(sortie: string | undefined, source: Jetons, css: string, racine: string | undefined): string {
  if (sortie === undefined || sortie.trim() === "") throw new RefusSortie("chemin de sortie obligatoire : npm run catalogue -- <fichier.html>");
  const absolu = resolve(sortie);
  const parent = dirname(absolu);
  if (!existsSync(parent)) throw new RefusSortie(`dossier de sortie introuvable : ${parent}`);
  const cible = join(realpathSync(parent), basename(absolu));
  if (racine !== undefined && dansLe(racine, cible)) throw new RefusSortie(`sortie refusée, le chemin est dans le dépôt : ${cible}`);
  const temporaire = `${cible}.tmp-${process.pid}`;
  writeFileSync(temporaire, genererCatalogue(source, css));
  renameSync(temporaire, cible);
  return cible;
}

if (import.meta.main) {
  const dossier = new URL("../src/styles/", import.meta.url);
  const source = JSON.parse(readFileSync(new URL("tokens.json", dossier), "utf8")) as Jetons;
  const css = `${readFileSync(new URL("tokens.css", dossier), "utf8")}\n${readFileSync(new URL("styles.css", dossier), "utf8")}`;
  try {
    const cible = ecrireCatalogue(process.argv[2], source, css, racineGit(new URL(".", import.meta.url).pathname));
    console.log(`page écrite : ${cible}`);
  } catch (e) {
    if (!(e instanceof RefusSortie)) throw e;
    console.error(e.message);
    process.exitCode = 2;
  }
}
