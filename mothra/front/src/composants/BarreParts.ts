// The parts bar with threshold markers (mothra-demo-habillage D4, D17) and the composition of the median lead time by quarter. One SVG per bar:
// waiting on the left, work on the right (a row of the chart: work, then waiting), the share of each part labelled, and the two thresholds of
// hypothesis 1 as vertical markers labelled with their ratio. The component draws what it is given and computes nothing: the shares, the
// positions of the markers and the lengths on the common axis are the numbers the contract serves (`waitShares`, `axisShare`), passed to the
// drawing as attribute values (a percentage of the width). It sets no style, no colour and no size: the classes are defined by the stylesheet from
// role-named tokens, so a change of brand does not touch it.
// States: values (markers applicable, or not applicable and then dotted and grey), a marker out of scale (its ratio told as text), masked (a dashed
// empty band holding the masked word), insufficient sample (the faded band, its markers dotted and grey, no number), not comparable (the bar is
// replaced by the catalogue sentence), and without markers (the rows of the chart).
// Replaces: the text list of the thresholds of lot 3b phase A (`Reperes` of `FicheConviction`), now drawn on the bars. Removal: permanent while the
// bar in parts measures hypothesis 1.
import { createElement as h, Fragment, useId } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";
import type { IntlShape } from "react-intl";

import type { Mesure, PartsDAttente } from "@mothra/contract";
import type { Jours, PeriodeComposition } from "@mothra/contract/composition";

import { jours } from "./ChiffreCle.ts";
import { ECHANTILLON_INSUFFISANT, Icone } from "./FicheEtats.ts";
import { libelleTrimestre } from "./trimestre.ts";

export const ETATS_BARRE = ["value", "masked", "insufficient_sample", "not_comparable"] as const;

// What a bar draws: the two shares when it has a value, otherwise its state alone. A bar of `waitShares` is assignable to it.
export type PartsBarre =
  | { state: "value"; waitShare: number; workShare: number }
  | { state: "masked" }
  | { state: "insufficient_sample" }
  | { state: "not_comparable" };

export type MarqueursBarre = PartsDAttente["markers"];

export interface PropsBarreParts {
  // `barre`: the bar of the share of waiting, with its markers and its labelled parts. `ligne`: a row of the chart, work then waiting, no marker.
  forme: "barre" | "ligne";
  parts: PartsBarre;
  // The bar of the sheet: `median` or `p85`. Absent on a row.
  code?: string;
  // The catalogue key of the short label drawn above the bar ("median", "P85"); the title is common to the two bars and drawn by the sheet
  // (R-20261103-5, replaces the per-bar `titre`).
  etiquette?: string;
  marqueurs?: MarqueursBarre;
  // Drawn under the bar (the ratio of the bar).
  rapport?: ReactNode;
  // A row: its length on the common axis (the `axisShare` of the quarter, a percentage), and the days written in its two parts.
  longueur?: number;
  libelleAttente?: string;
  libelleTravail?: string;
}

// Positions in the user space of the drawing (unitless): the labels of the markers above the band, the band, the markers across it.
const HAUTEUR_BARRE = 56;
const Y_TITRE_REPERE = 12;
const Y_REPERE_HAUT = 16;
const Y_BANDE = 20;
const H_BANDE = 24;
const Y_REPERE_BAS = 48;
const Y_ETIQUETTE = 36;
const HAUTEUR_LIGNE = 28;
const Y_ETIQUETTE_LIGNE = 19;
const DX_DEBUT = 8;
const DX_FIN = -8;

// A share as the catalogue writes it, whole percent: the rounding is display only, the width of the part is the number as served.
function partFormatee(intl: IntlShape, valeur: number): string {
  return intl.formatMessage({ id: "fiche.share.value" }, { value: Number(intl.formatNumber(valeur, { maximumFractionDigits: 0, useGrouping: false })) });
}

function pourcent(valeur: number): string {
  return `${valeur}%`;
}

// A number of days, a masked cell, an insufficient sample or the sentence of two medians that cannot be compared: as one text.
export function texteJours(intl: IntlShape, mesure: Mesure | Jours): string {
  if (mesure.state === "value") return jours(intl)(mesure.value);
  if (mesure.state === "masked") return intl.formatMessage({ id: "cellState.masked" });
  if (mesure.state === "insufficient_sample") return intl.formatMessage({ id: ECHANTILLON_INSUFFISANT.cle });
  return intl.formatMessage({ id: "conviction.notComparable" });
}

// The markers across the band. Labelled with their ratio when they apply; dotted and grey, without a label, when they do not (insufficient sample).
// A threshold out of scale has no share and is not drawn here (its ratio is told as text under the bar).
function Reperes({ intl, marqueurs, etiquettes }: { intl: IntlShape; marqueurs: MarqueursBarre; etiquettes: boolean }): ReactElement {
  const liste = [
    { code: "refutation", repere: marqueurs.refutation, cle: "conviction.marker.refutation", trait: "repere-trait repere-refutation" },
    { code: "confirmation", repere: marqueurs.confirmation, cle: "conviction.marker.confirmation", trait: "repere-trait repere-confirmation" },
  ] as const;
  return h(
    Fragment,
    null,
    liste.map(({ code, repere, cle, trait }) => {
      if (!repere.inScale || repere.share === undefined) return null;
      const x = pourcent(repere.share);
      return h(
        Fragment,
        { key: code },
        h("line", { className: etiquettes ? trait : "repere-trait repere-pointille", "data-marqueur": code, x1: x, x2: x, y1: Y_REPERE_HAUT, y2: Y_REPERE_BAS }),
        etiquettes ? h("text", { className: "repere-etiquette etiquette-milieu", x, y: Y_TITRE_REPERE }, intl.formatMessage({ id: cle }, { ratio: repere.ratio })) : null,
      );
    }),
  );
}

// The thresholds that fall outside the bar: their ratio is told as text, nothing is drawn. R-20261103-4 (1): the sheet draws this once, under the
// block of its two bars (`FicheConviction`), never under each bar: the bar itself no longer tells it.
export function HorsEchelle({ intl, marqueurs }: { intl: IntlShape; marqueurs: MarqueursBarre }): ReactElement | null {
  const horsEchelle = [
    { code: "refutation", repere: marqueurs.refutation },
    { code: "confirmation", repere: marqueurs.confirmation },
  ].filter(({ repere }) => !repere.inScale);
  if (horsEchelle.length === 0) return null;
  return h(
    Fragment,
    null,
    horsEchelle.map(({ code, repere }) =>
      h("p", { key: code, className: "barre-hors-echelle", "data-hors-echelle": code }, intl.formatMessage({ id: "conviction.marker.outOfScale" }, { threshold: intl.formatNumber(repere.ratio) })),
    ),
  );
}

function BarreAttenteSvg({ intl, parts, marqueurs, idEtiquette, idSvg }: { intl: IntlShape; parts: PartsBarre; marqueurs: MarqueursBarre | undefined; idEtiquette: string | undefined; idSvg: string }): ReactElement {
  const appliques = marqueurs !== undefined && marqueurs.applicable;
  let corps: ReactNode;
  let alternative: string;
  if (parts.state === "value") {
    const attente = pourcent(parts.waitShare);
    alternative = intl.formatMessage({ id: "conviction.bar.alt" }, { share: partFormatee(intl, parts.waitShare), work: partFormatee(intl, parts.workShare) });
    corps = h(
      Fragment,
      null,
      h("rect", { className: "part-attente", x: "0%", y: Y_BANDE, width: attente, height: H_BANDE }),
      h("rect", { className: "part-travail", x: attente, y: Y_BANDE, width: pourcent(parts.workShare), height: H_BANDE }),
      h("text", { className: "part-etiquette part-etiquette-attente etiquette-debut", x: "0%", dx: DX_DEBUT, y: Y_ETIQUETTE }, intl.formatMessage({ id: "conviction.bar.wait" }, { share: partFormatee(intl, parts.waitShare) })),
      h("text", { className: "part-etiquette part-etiquette-travail etiquette-fin", x: "100%", dx: DX_FIN, y: Y_ETIQUETTE }, intl.formatMessage({ id: "conviction.bar.work" }, { share: partFormatee(intl, parts.workShare) })),
      marqueurs === undefined ? null : h(Reperes, { intl, marqueurs, etiquettes: appliques }),
    );
  } else if (parts.state === "masked") {
    alternative = intl.formatMessage({ id: "conviction.bar.altNone" });
    corps = h(
      Fragment,
      null,
      h("rect", { className: "bande-masquee", x: "0%", y: Y_BANDE, width: "100%", height: H_BANDE }),
      h("text", { className: "bande-etiquette etiquette-milieu", x: "50%", y: Y_ETIQUETTE }, intl.formatMessage({ id: "cellState.masked" })),
    );
  } else {
    // Insufficient sample: the faded band and the markers that do not apply.
    alternative = intl.formatMessage({ id: "conviction.bar.altNone" });
    corps = h(
      Fragment,
      null,
      h("rect", { className: "bande-insuffisante", x: "0%", y: Y_BANDE, width: "100%", height: H_BANDE }),
      marqueurs === undefined ? null : h(Reperes, { intl, marqueurs, etiquettes: false }),
    );
  }
  // R-20261103-5 (3): the visible label of the bar names it for assistive technology: the drawing is named by that text, then by its own alternative
  // (an element that points at itself is read through its `aria-label`).
  const nomme = idEtiquette === undefined ? {} : { id: idSvg, "aria-labelledby": [idEtiquette, idSvg].join(" ") };
  return h("svg", { className: "barre-svg", role: "img", "aria-label": alternative, ...nomme, width: "100%", height: HAUTEUR_BARRE, focusable: "false" }, corps);
}

function LigneSvg({ parts, longueur, libelleAttente, libelleTravail }: { parts: PartsBarre; longueur: number | undefined; libelleAttente: string | undefined; libelleTravail: string | undefined }): ReactElement | null {
  // R-20261103-4 (2): a length that is absent is never 100; nothing is drawn in its place (no axis rectangle).
  if (parts.state !== "value" || longueur === undefined) return null;
  const travail = pourcent(parts.workShare);
  return h(
    "svg",
    { className: "barre-svg barre-svg-ligne", "aria-hidden": "true", width: "100%", height: HAUTEUR_LIGNE, focusable: "false" },
    // The row is a nested drawing of the length of the axis: the parts take a percentage of it, so no length is computed here.
    h(
      "svg",
      { className: "ligne-axe", x: "0%", y: 0, width: pourcent(longueur), height: HAUTEUR_LIGNE },
      h("rect", { className: "part-travail", x: "0%", y: 0, width: travail, height: HAUTEUR_LIGNE }),
      h("rect", { className: "part-attente", x: travail, y: 0, width: pourcent(parts.waitShare), height: HAUTEUR_LIGNE }),
      libelleTravail === undefined ? null : h("text", { className: "part-etiquette part-etiquette-travail etiquette-debut", x: "0%", dx: DX_DEBUT, y: Y_ETIQUETTE_LIGNE }, libelleTravail),
      libelleAttente === undefined ? null : h("text", { className: "part-etiquette part-etiquette-attente etiquette-fin", x: "100%", dx: DX_FIN, y: Y_ETIQUETTE_LIGNE }, libelleAttente),
    ),
  );
}

export function BarreParts({ forme, parts, code, etiquette, marqueurs, rapport, longueur, libelleAttente, libelleTravail }: PropsBarreParts): ReactElement {
  const intl = useIntl();
  const id = useId();
  const idEtiquette = etiquette === undefined ? undefined : `${id}-etiquette`;
  if (forme === "ligne") {
    return h(
      "div",
      { className: "barre-parts", "data-forme": "ligne", "data-etat": parts.state },
      parts.state === "value" ? h(LigneSvg, { parts, longueur, libelleAttente, libelleTravail }) : null,
      parts.state === "masked" ? h("span", { className: "mesure-masquee" }, intl.formatMessage({ id: "cellState.masked" })) : null,
      parts.state === "insufficient_sample" ? h("span", { className: "mesure-insuffisante" }, h(Icone, { nom: ECHANTILLON_INSUFFISANT.icone }), intl.formatMessage({ id: ECHANTILLON_INSUFFISANT.cle })) : null,
      parts.state === "not_comparable" ? h("span", { className: "mesure-non-comparable" }, intl.formatMessage({ id: "conviction.notComparable" })) : null,
    );
  }
  return h(
    "div",
    // R-20261103-4 (3): the P85 bar is thinner than the median one; the attribute applies the role token of the thickness (stylesheet).
    { className: "barre-parts", "data-forme": "barre", "data-barre": code, "data-etat": parts.state, "data-epaisseur": code === "p85" ? "fine" : undefined },
    // R-20261103-5 (1)(3): the title is common to the two bars (drawn once above them by the sheet); each bar keeps a short visible label.
    etiquette === undefined ? null : h("p", { className: "barre-etiquette", id: idEtiquette }, intl.formatMessage({ id: etiquette })),
    parts.state === "not_comparable"
      ? h("p", { className: "mesure-non-comparable" }, intl.formatMessage({ id: "conviction.notComparable" }))
      : h(BarreAttenteSvg, { intl, parts, marqueurs, idEtiquette, idSvg: `${id}-svg` }),
    rapport,
  );
}

// ---- the composition of the median lead time by quarter -----------------------------------------------------------------------------------

// The shares of a quarter as the bar draws them: a value needs both shares, which the contract serves when the lead time is above zero.
function partsDeLigne(q: PeriodeComposition): PartsBarre {
  if (q.state === "value") {
    return q.waitShare !== undefined && q.workShare !== undefined ? { state: "value", waitShare: q.waitShare, workShare: q.workShare } : { state: "not_comparable" };
  }
  return { state: q.state };
}

export function CompositionTrimestres({ quarters }: { quarters: PeriodeComposition[] }): ReactElement | null {
  const intl = useIntl();
  if (quarters.length === 0) return null;
  const lignes = quarters.map((q) => ({ q, nom: libelleTrimestre(q.quarter, (id, valeurs) => intl.formatMessage({ id }, valeurs)), parts: partsDeLigne(q) }));
  const alternative = intl.formatMessage(
    { id: "conviction.chart.alt" },
    {
      list: intl.formatList(
        lignes.map(({ q, nom, parts }) =>
          parts.state === "value"
            ? intl.formatMessage({ id: "conviction.chart.altItem" }, { quarter: nom, work: texteJours(intl, q.workDays), wait: texteJours(intl, q.waitDays) })
            : intl.formatMessage({ id: "conviction.chart.altItemNone" }, { quarter: nom }),
        ),
        { type: "conjunction" },
      ),
    },
  );
  return h(
    "figure",
    { className: "composition" },
    h("p", { className: "barre-titre" }, intl.formatMessage({ id: "conviction.chart.title" })),
    h(
      "p",
      { className: "composition-legende" },
      h("span", { className: "legende legende-travail" }, intl.formatMessage({ id: "conviction.chart.work" })),
      h("span", { className: "legende legende-attente" }, intl.formatMessage({ id: "conviction.chart.wait" })),
    ),
    // The rows are one picture for assistive technology: its alternative is the sentence above, its data the hidden table below.
    h(
      "div",
      { className: "composition-lignes", role: "img", "aria-label": alternative },
      lignes.map(({ q, nom, parts }) =>
        h(
          "div",
          { key: q.quarter, className: "composition-ligne", "data-trimestre": q.quarter },
          h("span", { className: "composition-trimestre" }, nom),
          h(BarreParts, {
            forme: "ligne",
            parts,
            longueur: q.axisShare,
            libelleAttente: parts.state === "value" ? texteJours(intl, q.waitDays) : undefined,
            libelleTravail: parts.state === "value" ? texteJours(intl, q.workDays) : undefined,
          }),
          h("span", { className: "composition-total" }, q.leadDays.state === "value" ? texteJours(intl, q.leadDays) : null),
        ),
      ),
    ),
    h(
      "table",
      { className: "cache-visuel" },
      h("caption", null, intl.formatMessage({ id: "conviction.chart.title" })),
      h(
        "thead",
        null,
        h(
          "tr",
          null,
          h("th", { scope: "col" }, intl.formatMessage({ id: "tableau.column.quarter" })),
          h("th", { scope: "col" }, intl.formatMessage({ id: "conviction.chart.work" })),
          h("th", { scope: "col" }, intl.formatMessage({ id: "conviction.chart.wait" })),
          h("th", { scope: "col" }, intl.formatMessage({ id: "conviction.chart.total" })),
        ),
      ),
      h(
        "tbody",
        null,
        lignes.map(({ q, nom }) =>
          h("tr", { key: q.quarter }, h("th", { scope: "row" }, nom), h("td", null, texteJours(intl, q.workDays)), h("td", null, texteJours(intl, q.waitDays)), h("td", null, texteJours(intl, q.leadDays))),
        ),
      ),
    ),
  );
}
