// The verdict badge of a conviction, one shape for every state (mothra-demo-habillage D5, D8, D17): the label from the catalogue, the icon and
// the outline from the `states` of the token source (one source), the colours from the stylesheet by role. Colour never stands alone: each
// state has its label, its icon and its outline. The display state is given by the caller; the badge only draws it.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { EtatAffichage } from "@mothra/contract/composition";

import jetons from "../styles/tokens.json" with { type: "json" };
import { Icone } from "./FicheEtats.ts";

// The five display states of the contract, plus the fallback of a verdict the front does not know. The states "in progress" and "not tested"
// are not drawn by the badge: a conviction without a published sheet shows no badge at all (D8, D17).
export type EtatBadge = EtatAffichage | "unknown";

interface EtatJeton {
  label: string;
  icon: string;
  outline: string;
}

const ETATS = jetons.states as Record<string, EtatJeton>;

interface PresentationBadge {
  // The catalogue key of the label, written in full so that the catalogue test finds it.
  cle: string;
  // The token of the `states` section that holds the icon and the outline.
  jeton: string;
  classe: string;
}

export const PRESENTATION_BADGE: Record<EtatBadge, PresentationBadge> = {
  confirmed: { cle: "conviction.badge.confirmed", jeton: "verdict-confirmed", classe: "badge badge-confirmee" },
  refuted: { cle: "conviction.badge.refuted", jeton: "verdict-refuted", classe: "badge badge-refutee" },
  not_settled: { cle: "conviction.badge.not_settled", jeton: "verdict-not-settled", classe: "badge badge-non-tranchee" },
  insufficient_sample: { cle: "conviction.badge.insufficient_sample", jeton: "state-insufficient", classe: "badge badge-insuffisante" },
  masked: { cle: "conviction.badge.masked", jeton: "state-masked", classe: "badge badge-masquee" },
  // A verdict the front does not know: the look of the insufficient sample (no colour claim), with its own label.
  unknown: { cle: "fiche.verdict.unknown", jeton: "state-insufficient", classe: "badge badge-insuffisante" },
};

export const ETATS_BADGE = Object.keys(PRESENTATION_BADGE) as EtatBadge[];

export function BadgeVerdict({ etat, discret = false }: { etat: EtatBadge; discret?: boolean }): ReactElement {
  const intl = useIntl();
  const { cle, jeton, classe } = PRESENTATION_BADGE[etat];
  const etatJeton = ETATS[jeton];
  return h(
    "span",
    { className: discret ? [classe, "badge-discret"].join(" ") : classe, "data-etat": etat, "data-contour": etatJeton.outline },
    h(Icone, { nom: etatJeton.icon }),
    intl.formatMessage({ id: cle }),
  );
}
