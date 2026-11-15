// The reading face of a hypothesis 1 sheet (mothra-demo-habillage D4, D6, D17): the statement, the verdict badge, the status of the sheet, the
// context line, the evidence card, the three insets of the real fields, the competing explanations, the footer. It shows what the sheet answer
// holds, complete or reduced: it computes no verdict, no ratio, no share and no sum (the display state comes from `compositionConviction`).
// The existing `Fiche` component (the workflow screen) is not changed; both read the same contract answer.
// Lot 3b, phase A: the fallback of D4 without lot 1b. No bar and no composition chart are drawn; the page shows the verdict, the median and
// P85 ratios of the pooled year as text, and the key figures in days that do not depend on lot 1b.
// Replaces: nothing (the fallback). Removal: falls once lot 1b is on main (the bars of `BarreParts` take its place).
// Lot 3b, phase B: when the answer carries `waitShares` (lot 1b), the evidence draws the median bar and the P85 bar with their ratios under them
// and the two thresholds as markers (`BarreParts`); on the complete form it also draws the composition of the median lead time by quarter in days
// on the common axis (`CompositionTrimestres`, from `axisShare`). The reduced form keeps its two bars and draws no composition (D4, R-20261101-33).
// On an insufficient sample or a masked sheet the bars are drawn faded or masked, with no number (D5).
// Lot 3c: the same face reads a hypothesis 5 sheet (`method.hypothesis`): the evidence is `PreuveH5` (cycle time and throughput by quarter, the
// stability table, the band and the floors), never a bar or a waiting (D4); the reasons of the verdict come under the badge, the thresholds are
// on the method face only (A-16 (a)). Of `compositionConviction` it reads `state` and `measured.quarter` only.
import { Children, createElement as h, Fragment, useId, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";
import type { IntlShape } from "react-intl";

import { compositionConviction, ETATS_AFFICHAGE } from "@mothra/contract/composition";
import type { EtatAffichage } from "@mothra/contract/composition";
import type { CodeConstatDeVerdict, MotifDeFiche } from "@mothra/contract/listes-fiche";

import type { MethodeFiche, ReponseFiche, TexteLibre } from "../api/fiche.ts";
import { adresseTableauDeFiche } from "../api/filtres.ts";
import { CLES_CONVICTION } from "../convictions.ts";
import { GabaritFiche } from "../gabarits/GabaritFiche.ts";
import { BadgeVerdict } from "./BadgeVerdict.ts";
import { libelleEquipe } from "./libelleEquipe.ts";
import type { TableauEnMemoire } from "./libelleEquipe.ts";
import { BarreParts, CompositionTrimestres, HorsEchelle } from "./BarreParts.ts";
import { CLES_ANNEE_FIGEE, clesAnneeGroupee } from "./annee-groupee.ts";
import { CLES_QUESTION } from "./ChampsFiche.ts";
import { Chiffre, jours, ValeurMesure } from "./ChiffreCle.ts";
import { ExplicationsConcurrentes } from "./ExplicationsConcurrentes.ts";
import { CLES_MOTIF } from "./Fiche.ts";
import { Mentions, MENTIONS_CYCLE_TIME } from "./FicheMentions.ts";
import { CLES_PERIMETRE, FicheMethode } from "./FicheMethode.ts";
import { PreuveH5 } from "./PreuveH5.ts";
import { StatutFiche } from "./StatutFiche.ts";

// The name of the team on the context line: decided by `libelleEquipe` alone (libelleEquipe.ts; R-20261104-62 Q1 (a), R-20261104-33, N2 (a)).
// The sheet's scope carries the opaque identifier; the name comes from the dashboard answer in memory, looked up by that identifier, when the
// server's setting is on; otherwise the identifier is shown. A scope that is not of that shape has no identifier: the line then shows the level
// of the scope, as a catalogue word, and nothing else.
export { libelleEquipe };

// The catalogue key of the sentence of each finding of a verdict (A-01, Q6), written in full so that the catalogue test finds it; a code the
// table does not know has the fallback sentence, never the raw code. The codes are the contract's closed list.
export const CLES_CONSTAT: Record<CodeConstatDeVerdict, string> = {
  h1_above_upper: "fiche.finding.h1_above_upper",
  h1_median_under_lower: "fiche.finding.h1_median_under_lower",
  h1_median_in_grey_zone: "fiche.finding.h1_median_in_grey_zone",
  h1_p85_not_above_upper: "fiche.finding.h1_p85_not_above_upper",
  h1_p85_not_readable: "fiche.finding.h1_p85_not_readable",
  h5_within_band: "fiche.finding.h5_within_band",
  h5_double_band: "fiche.finding.h5_double_band",
  h5_rising_run: "fiche.finding.h5_rising_run",
  h5_under_low_floor: "fiche.finding.h5_under_low_floor",
  h5_out_of_band: "fiche.finding.h5_out_of_band",
  h5_under_floor: "fiche.finding.h5_under_floor",
  confirmation_barred: "fiche.finding.confirmation_barred",
};

// A message with elements among its values, as one node: one ICU message per line.
function message(intl: IntlShape, id: string, valeurs: Record<string, ReactNode>): ReactElement {
  return h(Fragment, null, Children.toArray(intl.formatMessage({ id }, valeurs)));
}

function trimestre(intl: IntlShape, t: MethodeFiche["period"]["quarters"][number] | undefined): string {
  if (t === undefined) return intl.formatMessage({ id: "fiche.quarter.unknown" });
  return intl.formatMessage({ id: "fiche.quarter" }, { quarter: String(t.quarter), year: String(t.year) });
}

function dateCourte(intl: IntlShape, iso: string): string {
  return intl.formatDate(iso, { dateStyle: "medium", timeZone: "UTC" });
}

// The masking threshold of the footer: the one the answer holds (a masked cell of the method, the masked coverage), else the one of the
// dashboard answer, given by the caller. None known: the sentence is left out rather than invented.
function seuilDeMasquage(methode: MethodeFiche, repli: number | undefined): number | undefined {
  const masquee = methode.maskedCells[0];
  if (masquee !== undefined) return masquee.cell.threshold;
  if (methode.coverage !== undefined && methode.coverage.state === "masked") return methode.coverage.threshold;
  return repli;
}

// A written text with its own language: marked with `lang` when it is not the language of the screen, never translated.
function TexteLangue({ texte }: { texte: TexteLibre | undefined }): ReactElement {
  const intl = useIntl();
  if (texte === undefined) return h("span", { className: "fiche-champ-absent" }, intl.formatMessage({ id: "fiche.text.missing" }));
  return h("span", { lang: texte.lang === intl.locale ? undefined : texte.lang }, texte.text);
}

function rapport(intl: IntlShape): (valeur: number) => ReactNode {
  return (valeur) => intl.formatMessage({ id: "conviction.bar.ratio" }, { ratio: valeur });
}

function estEtatAffichage(verdict: string): verdict is EtatAffichage {
  return (ETATS_AFFICHAGE as readonly string[]).includes(verdict);
}

// The key figures: on the reduced form the median lead time and the median cycle time of the pooled year (two kept medians); on the full form
// the waiting and the work of the pooled year, as `compositionConviction` gives them.
function ChiffresCles({ fiche, reduite, mesuree, libelleAnnee }: { fiche: ReponseFiche; reduite: boolean; mesuree: ReturnType<typeof compositionConviction>["measured"]; libelleAnnee: string }): ReactElement {
  const intl = useIntl();
  const enJours = jours(intl);
  const annee = fiche.chart?.pooledYear;
  if (reduite) {
    if (annee === undefined) return h(Fragment, null);
    return h(
      "div",
      { className: "chiffres" },
      h(Chiffre, {
        code: "lead_median",
        valeur: h(ValeurMesure, { mesure: annee.lead, format: enJours }),
        libelle: intl.formatMessage({ id: "fiche.measure.lead_median_days" }),
      }),
      h(Chiffre, {
        code: "cycle_median",
        valeur: h(ValeurMesure, { mesure: annee.cycle, format: enJours }),
        libelle: intl.formatMessage({ id: "fiche.measure.cycle_median_days" }),
      }),
    );
  }
  return h(
    "div",
    { className: "chiffres" },
    h(Chiffre, {
      code: "wait",
      valeur: h(ValeurMesure, { mesure: mesuree.waitDays, format: enJours }),
      libelle: intl.formatMessage({ id: "conviction.figure.wait" }, { period: intl.formatMessage({ id: libelleAnnee }) }),
    }),
    h(Chiffre, { code: "work", valeur: h(ValeurMesure, { mesure: mesuree.workDays, format: enJours }), libelle: intl.formatMessage({ id: "conviction.figure.work" }) }),
  );
}

// The ratios of the pooled year, as text (the fallback without lot 1b): read from the answer, nothing computed.
function Rapports({ fiche }: { fiche: ReponseFiche }): ReactElement | null {
  const intl = useIntl();
  const annee = fiche.ratios?.pooledYear;
  if (annee === undefined) return null;
  const format = rapport(intl);
  return h(
    "dl",
    { className: "rapports" },
    h("div", { className: "rapport", "data-rapport": "median" }, h("dt", null, intl.formatMessage({ id: "fiche.measure.median_ratio" })), h("dd", null, h(ValeurMesure, { mesure: annee.median, format }))),
    h("div", { className: "rapport", "data-rapport": "p85" }, h("dt", null, intl.formatMessage({ id: "fiche.measure.p85_ratio" })), h("dd", null, h(ValeurMesure, { mesure: annee.p85, format }))),
  );
}

// One ratio of the pooled year, under its bar: the label of the measure and its value, read from the answer, nothing computed.
function RapportDeBarre({ fiche, code }: { fiche: ReponseFiche; code: "median" | "p85" }): ReactElement | null {
  const intl = useIntl();
  const annee = fiche.ratios?.pooledYear;
  if (annee === undefined) return null;
  return h(
    "dl",
    { className: "rapports barre-rapport" },
    h(
      "div",
      { className: "rapport", "data-rapport": code },
      h("dt", null, intl.formatMessage({ id: code === "median" ? "fiche.measure.median_ratio" : "fiche.measure.p85_ratio" })),
      h("dd", null, h(ValeurMesure, { mesure: code === "median" ? annee.median : annee.p85, format: rapport(intl) })),
    ),
  );
}

// The two bars of the share of waiting, the median and the P85, read from `waitShares` (R-20261101-20): the shares, the ratios of the markers and
// their position are the numbers the server served; the thresholds are drawn as markers on both bars (R-20261102-71 (1)). The ratio of each bar
// is told under it when the page shows figures; on an insufficient sample or a masked sheet the bars hold no number.
function Barres({ attente, fiche, avecChiffres }: { attente: NonNullable<ReponseFiche["waitShares"]>; fiche: ReponseFiche; avecChiffres: boolean }): ReactElement {
  const intl = useIntl();
  return h(
    Fragment,
    null,
    // R-20261103-5 (1)(4): one title above the block of the two bars, a title paragraph (not a heading element); each bar keeps a short label.
    h("p", { className: "barre-titre" }, intl.formatMessage({ id: "conviction.bar.title" })),
    h(BarreParts, {
      forme: "barre",
      code: "median",
      etiquette: "conviction.bar.labelMedian",
      parts: attente.median,
      marqueurs: attente.markers,
      rapport: avecChiffres ? h(RapportDeBarre, { fiche, code: "median" }) : undefined,
    }),
    h(BarreParts, {
      forme: "barre",
      code: "p85",
      etiquette: "conviction.bar.labelP85",
      parts: attente.p85,
      marqueurs: attente.markers,
      rapport: avecChiffres ? h(RapportDeBarre, { fiche, code: "p85" }) : undefined,
    }),
    // R-20261103-4 (1): the text of a threshold out of scale is told once, under the block of the two bars, also when a bar is not comparable.
    attente.markers.applicable && [attente.median.state, attente.p85.state].some((etat) => etat === "value" || etat === "not_comparable")
      ? h(HorsEchelle, { intl, marqueurs: attente.markers })
      : null,
  );
}

export interface PropsFicheConviction {
  fiche: ReponseFiche;
  // The masking threshold of the dashboard answer, used by the footer when the sheet holds none.
  seuilMasquage?: number;
  // Whether the link to the dashboard is drawn (the dashboard source is given).
  avecTableau?: boolean;
  // The method face starts closed; the argument is for tests and for a screen that opens it directly.
  methodeOuverte?: boolean;
  // The dashboard answer held in memory, if any: the name of the team comes from it when the server's setting is on (N2 (a)).
  tableau?: TableauEnMemoire;
  // The address of the life cycle screen of this sheet, given by the page for a sheet in progress when the screens are offered (A-04); absent: no link.
  adresseCycle?: string;
}

export function FicheConviction({ fiche, seuilMasquage, avecTableau = true, methodeOuverte = false, tableau, adresseCycle }: PropsFicheConviction): ReactElement {
  const intl = useIntl();
  const idMethode = useId();
  const [ouverte, setOuverte] = useState(methodeOuverte);
  const methode = fiche.method;
  const reduite = methode.limits.includes("reduced_form");
  // A verdict the front does not know is drawn by the fallback badge and shows no figure (D5).
  const connu = estEtatAffichage(fiche.verdict);
  const composition = connu ? compositionConviction(fiche) : undefined;
  const etat = composition?.state;
  const avecChiffres = etat === "confirmed" || etat === "refuted" || etat === "not_settled";
  const equipe = libelleEquipe(methode, tableau);
  const perimetre =
    equipe === undefined
      ? intl.formatMessage({ id: Object.hasOwn(CLES_PERIMETRE, methode.scope.level) ? CLES_PERIMETRE[methode.scope.level] : "fiche.scope.unknown" })
      : message(intl, "conviction.scope.team", { team: h("data", { value: equipe }, equipe) });
  const debut = methode.period.quarters[0];
  const fin = methode.period.quarters[methode.period.quarters.length - 1];
  const masquage = seuilDeMasquage(methode, seuilMasquage);
  const question = fiche.managementQuestion;
  // ---- hypothesis 5 begin (lot 3c, D4): no waiting on this page. Of `compositionConviction` it reads `state` and `measured.quarter` only; it
  // reads no bar, no `waitShares`, no share and no day of waiting. The test of lot 3c checks this block.
  const h5 = methode.hypothesis === "h5";
  const trimestreJuge = composition?.measured.quarter ?? "";
  // The reasons of the verdict that the page tells under the badge: `throughput_masked` (a masked throughput forbids "confirmed").
  const motifsH5: readonly string[] = h5 ? fiche.h5Reasons : [];
  // ---- hypothesis 5 end
  // The findings of the verdict (A-01): shown on both hypotheses, for a verdict the front knows (an unknown verdict shows none).
  const constats: readonly string[] = connu ? (fiche.verdictFindings ?? []) : [];
  const montreAttente = avecChiffres && !reduite && !h5;
  // The bars of lot 1b: absent from an answer built without the service layer (the fallback of D4).
  // Hypothesis 5 never reads `waitShares` (D4): the guard is checked by the static test of lot 3c.
  const attente = h5 ? undefined : fiche.waitShares;

  // R-20261108-08: a fixed sentence of the catalogue, shown on EVERY hypothesis 1 page whatever the verdict (confirmed, refuted, not settled,
  // masked, insufficient sample, or a verdict the front does not know), never on hypothesis 5, so that a gap with the dashboard is not taken
  // for an error. Chosen by the hypothesis of the method (h1_first_half), never by the data.
  // R-20261114-49, design D7 and D8: the label of the grouped row and this note are chosen by the window limit code the sheet carries (a frozen sheet:
  // the former ones; a new sheet: « Last three quarters »), never by the data. A sheet with neither code or both is a caller error: no grouped row.
  const cles = clesAnneeGroupee(methode.limits);
  const noteAnneeGroupee =
    methode.hypothesis !== "h1_first_half" || cles === null ? null : h("p", { className: "fiche-note", "data-note": cles.marque }, intl.formatMessage({ id: cles.note }));
  const sansEtiquette = !h5 && cles === null;

  const preuve =
    sansEtiquette
      ? h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: "tableau.panel.mentionMissing" }))
      : composition === undefined || etat === undefined
      ? (noteAnneeGroupee ?? undefined)
      : h5
        ? h(PreuveH5, { fiche, etat, trimestreJuge })
        : h(
          Fragment,
          null,
          avecChiffres
            ? h(
                Fragment,
                null,
                h("p", { className: "preuve-periode" }, intl.formatMessage({ id: (cles ?? CLES_ANNEE_FIGEE).libelle })),
                noteAnneeGroupee,
                h(ChiffresCles, { fiche, reduite, mesuree: composition.measured, libelleAnnee: (cles ?? CLES_ANNEE_FIGEE).libelle }),
                attente === undefined ? h(Rapports, { fiche }) : h(Barres, { attente, fiche, avecChiffres: true }),
                // The chart in days is a difference of two medians: the complete form only (D4), and only with the bars (fallback of D4).
                attente !== undefined && !reduite ? h(CompositionTrimestres, { quarters: composition.quarters }) : null,
                h("p", { className: "fiche-note" }, h(Mentions, { codes: MENTIONS_CYCLE_TIME })),
              )
            : h(
                Fragment,
                null,
                h("p", { className: "preuve-constat" }, intl.formatMessage({ id: etat === "masked" ? "conviction.finding.masked" : "conviction.finding.insufficient_sample" })),
                noteAnneeGroupee,
                attente === undefined ? null : h(Barres, { attente, fiche, avecChiffres: false }),
              ),
        );

  const encarts = h(
    Fragment,
    null,
    h(
      "section",
      { className: "carte encart", "data-encart": "question" },
      // The headings are h2: the page holds the h1 of the statement, then the insets and the competing explanations at the same level.
      h("h2", { className: "encart-titre" }, intl.formatMessage({ id: "conviction.inset.managementQuestion" })),
      h("p", { className: "encart-texte encart-question" }, intl.formatMessage({ id: question !== undefined && Object.hasOwn(CLES_QUESTION, question) ? CLES_QUESTION[question] : "fiche.form.question.none" })),
    ),
    h(
      "section",
      { className: "carte encart", "data-encart": "effet" },
      h("h2", { className: "encart-titre" }, intl.formatMessage({ id: "conviction.inset.effect" })),
      h("p", { className: "encart-texte" }, h(TexteLangue, { texte: fiche.effect })),
    ),
    h(
      "section",
      { className: "carte encart", "data-encart": "cause" },
      h("h2", { className: "encart-titre" }, intl.formatMessage({ id: "conviction.inset.cause" })),
      h("p", { className: "encart-texte" }, h(TexteLangue, { texte: fiche.cause })),
    ),
  );

  const explications = h(
    Fragment,
    null,
    h(ExplicationsConcurrentes, { explications: fiche.explanations, signalMontre: fiche.attachmentSignalShown, motifsSignal: fiche.attachmentSignalReasons }),
    // The detail by quarter is in days: it is offered on the complete form only (R-20261101-126, Q7 (a)).
    // A-04: a sheet in progress links to its life cycle screen, where a reviewer reviews it and its author publishes it.
    adresseCycle === undefined ? null : h("a", { className: "lien", href: adresseCycle }, intl.formatMessage({ id: "fiche.cycle.open" })),
    // A-03: the link keeps the team and the period of the sheet, so the dashboard opens on them.
    avecTableau && !reduite ? h("a", { className: "lien", href: adresseTableauDeFiche(methode) }, intl.formatMessage({ id: "conviction.detail" })) : null,
    h(
      "button",
      { type: "button", className: "fiche-bouton", "aria-expanded": ouverte, "aria-controls": ouverte ? idMethode : undefined, onClick: () => setOuverte(!ouverte) },
      intl.formatMessage({ id: ouverte ? "fiche.method.hide" : "fiche.method.show" }),
    ),
    ouverte ? h(FicheMethode, { methode, id: idMethode, graphique: fiche.chart, tableau }) : null,
  );

  const pied = h(
    Fragment,
    null,
    masquage === undefined ? null : h("p", null, intl.formatMessage({ id: "conviction.footer.masking" }, { threshold: intl.formatNumber(masquage) })),
    montreAttente ? h("p", null, intl.formatMessage({ id: "conviction.footer.waitDefinition" })) : null,
    montreAttente ? h("p", null, intl.formatMessage({ id: "conviction.footer.cycleScope" })) : null,
    // R-20261109-08 Q2 (a): the footer holds no "hypothesis served" line; the number of the hypothesis stays on the method face.
    // A-16 (a): the thresholds are on the method face only; the footer repeats none of them.
  );

  // The slots of the template: the order of the page is its own (statement, badge and status, evidence, insets, explanations, footer).
  return h(GabaritFiche, {
    enonce: CLES_CONVICTION[h5 ? "lead_cycle_h5" : "lead_cycle_h1"].enonce,
    // The badge and, beside it, the reminder that the verdict is computed, never typed (Q6 (a), `fiche.verdict.computed`). On hypothesis 5 the
    // reasons of the verdict come under the badge (D4: `fiche.reason.throughput_masked`).
    badge: h(
      Fragment,
      null,
      h(BadgeVerdict, { etat: etat ?? "unknown" }),
      h("span", { className: "verdict-calcule" }, intl.formatMessage({ id: "fiche.verdict.computed" })),
      // A-01 (Q6): the sentence that says why the verdict is what it is, from the codes the contract gives; none for a version that holds none.
      // A code the table does not know is told by the fallback sentence and marked "unknown": the raw code is never written into the page.
      constats.map((code, rang) =>
        Object.hasOwn(CLES_CONSTAT, code)
          ? h("p", { key: code, className: "fiche-constat", "data-constat": code }, intl.formatMessage({ id: CLES_CONSTAT[code as CodeConstatDeVerdict] }))
          : h("p", { key: rang, className: "fiche-constat", "data-constat": "unknown" }, intl.formatMessage({ id: "fiche.finding.unknown" })),
      ),
      // A-02: the attachment signal stands next to the verdict, on the management face; the block of the explanations keeps its row.
      fiche.attachmentSignalShown ? h("p", { className: "fiche-signal", "data-signal-verdict": "shown" }, intl.formatMessage({ id: "fiche.attachmentSignal" })) : null,
      motifsH5.map((motif) =>
        h("p", { key: motif, className: "fiche-raison", "data-raison": motif }, intl.formatMessage({ id: Object.hasOwn(CLES_MOTIF, motif) ? CLES_MOTIF[motif as MotifDeFiche] : "fiche.reason.unknown" })),
      ),
    ),
    statut: h(StatutFiche, { etat: fiche.state, publieLe: fiche.publishedOn, version: methode.version }),
    contexte: message(intl, "conviction.context", { scope: perimetre, from: trimestre(intl, debut), to: trimestre(intl, fin), date: dateCourte(intl, methode.dataDate) }),
    etat,
    preuve,
    encarts,
    explications,
    pied,
  });
}
