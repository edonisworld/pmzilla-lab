// The evidence of a hypothesis 5 sheet (mothra-demo-habillage D4, D13, D17): cycle time and throughput by quarter, never waiting. It is built only
// from the fields of the sheet answer that D4 lists, with no arithmetic and no estimate; a figure the answer does not carry is not shown.
// - Key figures of the judged quarter: the median and the P85 of the cycle time in days, and the position of its throughput (no count, Q148).
// - The stability table (`TableauStabilite`), then the adopted band and floors as `method.thresholds` holds them (no band in days, no bound and
//   no reference value, Q147), then the cycle time mention and, when the limits hold it, the line of the throughput's own past.
// - On an insufficient sample or a masked sheet: the finding sentence and the band and floors only, no key figure and no figure in the table (D5, Q121).
// It reads no bar, no `waitShares`, no composition and none of the labels that D13 marks "hypothesis 1 only" (R-20261101-14).
// Replaces: the hypothesis 5 bar and chart without markers of Q129. Removal: permanent while the bar in parts measures hypothesis 1.
import { createElement as h, Fragment } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { EtatAffichage } from "@mothra/contract/composition";

import type { ReponseFiche } from "../api/fiche.ts";
import { Chiffre, jours, ValeurMesure } from "./ChiffreCle.ts";
import { Mentions, MENTIONS_CYCLE_TIME } from "./FicheMentions.ts";
import { clePosition, TableauStabilite } from "./TableauStabilite.ts";
import { libelleTrimestre } from "./trimestre.ts";
import { valeurSeuil } from "./valeurSeuil.ts";

// The adopted values of the band and of the floors, each formatted as the method face formats a threshold value (`valeurSeuil`). A pair with a missing value is left
// out rather than invented.
function Seuils({ fiche }: { fiche: ReponseFiche }): ReactElement {
  const intl = useIntl();
  const valeur = (code: string): string | undefined => {
    const seuil = fiche.method.thresholds.find((s) => s.code === code);
    return seuil === undefined ? undefined : valeurSeuil(intl, seuil.code, seuil.value);
  };
  const bande = valeur("h5_band");
  const doubleBande = valeur("h5_double_band");
  const plancher = valeur("h5_floor");
  const plancherBas = valeur("h5_low_floor");
  return h(
    Fragment,
    null,
    bande === undefined || doubleBande === undefined
      ? null
      : h("p", { className: "preuve-seuil", "data-seuil-h5": "band" }, intl.formatMessage({ id: "conviction.h5.band" }, { band: bande, doubleBand: doubleBande })),
    plancher === undefined || plancherBas === undefined
      ? null
      : h("p", { className: "preuve-seuil", "data-seuil-h5": "floor" }, intl.formatMessage({ id: "conviction.h5.floor" }, { floor: plancher, lowFloor: plancherBas })),
  );
}

export interface PropsPreuveH5 {
  fiche: ReponseFiche;
  // The display state of the sheet (the contract's `state`) and the label of the judged quarter (`measured.quarter`).
  etat: EtatAffichage;
  trimestreJuge: string;
}

export function PreuveH5({ fiche, etat, trimestreJuge }: PropsPreuveH5): ReactElement {
  const intl = useIntl();
  if (etat !== "confirmed" && etat !== "refuted" && etat !== "not_settled") {
    return h(
      Fragment,
      null,
      h("p", { className: "preuve-constat" }, intl.formatMessage({ id: etat === "masked" ? "conviction.finding.masked" : "conviction.finding.insufficient_sample" })),
      h(Seuils, { fiche }),
    );
  }
  const periode = libelleTrimestre(trimestreJuge, (id, valeurs) => intl.formatMessage({ id }, valeurs));
  const enJours = jours(intl);
  const mediane = fiche.chart?.quarters.find((p) => p.quarter === trimestreJuge)?.cycle;
  const p85 = fiche.p85?.quarters.find((p) => p.quarter === trimestreJuge)?.cycle;
  const position = fiche.throughputPositions?.find((p) => p.quarter === trimestreJuge)?.position;
  return h(
    Fragment,
    null,
    h(
      "div",
      { className: "chiffres" },
      mediane === undefined
        ? null
        : h(Chiffre, { code: "cycle_median", valeur: h(ValeurMesure, { mesure: mediane, format: enJours }), libelle: intl.formatMessage({ id: "conviction.h5.figure.median" }, { period: periode }) }),
      p85 === undefined
        ? null
        : h(Chiffre, { code: "cycle_p85", valeur: h(ValeurMesure, { mesure: p85, format: enJours }), libelle: intl.formatMessage({ id: "conviction.h5.figure.p85" }, { period: periode }) }),
    ),
    h(
      "p",
      { className: "chiffre-debit", "data-chiffre": "throughput" },
      intl.formatMessage({ id: "conviction.h5.figure.throughput" }, { period: periode, position: intl.formatMessage({ id: clePosition(position) }) }),
    ),
    h(TableauStabilite, { trimestres: fiche.chart?.quarters ?? [], p85: fiche.p85?.quarters ?? [], positions: fiche.throughputPositions ?? [], juge: trimestreJuge }),
    h(Seuils, { fiche }),
    h("p", { className: "fiche-note" }, h(Mentions, { codes: MENTIONS_CYCLE_TIME })),
    fiche.method.limits.includes("throughput_own_past_only") ? h("p", { className: "fiche-note", "data-limite": "throughput_own_past_only" }, intl.formatMessage({ id: "fiche.throughputOwnPastOnly" })) : null,
  );
}
