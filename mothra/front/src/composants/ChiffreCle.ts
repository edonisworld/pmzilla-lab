// A key figure of a sheet (mothra-demo-habillage D4, D17): the value of a measure as the contract serves it, drawn by its state, with its label
// under it. Shared by the hypothesis 1 evidence and the hypothesis 5 evidence: the front draws what it is given and computes nothing.
// Replaces: nothing (moved out of `FicheConviction.ts` so that two faces of the sheet use one drawing). Removal: permanent while a sheet shows key figures.
import { createElement as h } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";
import type { IntlShape } from "react-intl";

import type { Mesure } from "@mothra/contract";
import type { Jours } from "@mothra/contract/composition";

import { ECHANTILLON_INSUFFISANT } from "./FicheEtats.ts";

// A measure as the contract serves it, drawn by its state: a value through the given format, the masked word, or the insufficient sample.
export function ValeurMesure({ mesure, format }: { mesure: Mesure | Jours; format: (valeur: number) => ReactNode }): ReactElement {
  const intl = useIntl();
  if (mesure.state === "value") return h("span", { className: "mesure-valeur", "data-state": "value" }, format(mesure.value));
  if (mesure.state === "masked") return h("span", { className: "mesure-masquee", "data-state": "masked" }, intl.formatMessage({ id: "cellState.masked" }));
  if (mesure.state === "insufficient_sample") return h("span", { className: "mesure-insuffisante", "data-state": "insufficient" }, intl.formatMessage({ id: ECHANTILLON_INSUFFISANT.cle }));
  return h("span", { className: "mesure-non-comparable", "data-state": "not_comparable" }, intl.formatMessage({ id: "conviction.notComparable" }));
}

export function Chiffre({ valeur, libelle, code }: { valeur: ReactElement; libelle: ReactNode; code: string }): ReactElement {
  return h("div", { className: "chiffre", "data-chiffre": code }, h("p", { className: "chiffre-valeur" }, valeur), h("p", { className: "chiffre-libelle" }, libelle));
}

// A number of days, through the catalogue's unit. The one formatting of a number of days (`texteJours` of the parts bar uses it, R-20261103-24
// and R-20261103-20: no duplicate); its type is a string so that both callers share it.
export function jours(intl: IntlShape): (valeur: number) => string {
  return (valeur) => intl.formatMessage({ id: "conviction.chart.days" }, { days: intl.formatNumber(valeur, { maximumFractionDigits: 1 }) });
}
