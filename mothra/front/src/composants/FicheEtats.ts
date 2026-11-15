// Presentation of the verdicts and of the insufficient sample of the sheet: label key, icon and outline are read from the `states` of the
// token source (design D32, one source), never written again here. Only the class names, which the stylesheet defines, are chosen here.
import { createElement as h } from "react";
import type { ReactElement } from "react";

import jetons from "../styles/tokens.json" with { type: "json" };
import type { VerdictOuEchantillon } from "../api/fiche.ts";

interface EtatJeton {
  label: string;
  icon: string;
  outline: string;
}

const ETATS = jetons.states as Record<string, EtatJeton>;

// The token of each verdict the service can return, and the class that carries its colour.
const JETON_VERDICT: Record<VerdictOuEchantillon, { jeton: string; classe: string }> = {
  confirmed: { jeton: "verdict-confirmed", classe: "fiche-verdict fiche-verdict-confirmed" },
  refuted: { jeton: "verdict-refuted", classe: "fiche-verdict fiche-verdict-refuted" },
  not_settled: { jeton: "verdict-not-settled", classe: "fiche-verdict fiche-verdict-not-settled" },
  insufficient_sample: { jeton: "state-insufficient", classe: "fiche-verdict fiche-verdict-insufficient" },
};

export interface PresentationVerdict {
  cle: string;
  icone: string;
  contour: string;
  classes: string;
}

// A verdict this screen does not know (a service newer than the front): a neutral presentation with a fallback catalogue key, no error.
// It borrows the icon, the outline and the class of the insufficient sample (no colour claim), with its own label.
export function presentationVerdict(verdict: string): PresentationVerdict {
  if (!Object.hasOwn(JETON_VERDICT, verdict)) {
    const neutre = ETATS[JETON_VERDICT.insufficient_sample.jeton];
    return { cle: "fiche.verdict.unknown", icone: neutre.icon, contour: neutre.outline, classes: JETON_VERDICT.insufficient_sample.classe };
  }
  const { jeton, classe } = JETON_VERDICT[verdict as VerdictOuEchantillon];
  const etat = ETATS[jeton];
  return { cle: etat.label, icone: etat.icon, contour: etat.outline, classes: classe };
}

// The label key and the icon of the insufficient sample, for the cells that show it (a share, a measure of the method face).
const ETAT_ECHANTILLON = ETATS[JETON_VERDICT.insufficient_sample.jeton];
export const ECHANTILLON_INSUFFISANT = { cle: ETAT_ECHANTILLON.label, icone: ETAT_ECHANTILLON.icon };

// The one inline vector icon of the module: the lock of a published sheet (R-20261101-127). Monochrome: it is filled with `currentColor`
// by the stylesheet, so it takes the colour of the text token around it; it is hidden from assistive technology, the word "frozen" carries the
// meaning. The other icons stay glyphs drawn by the stylesheet.
const TRACE_CADENAS = "M3,7h10v7H3zM4.5,7V5a3.5,3.5,0,0,1,7,0v2H10V5a2,2,0,0,0-4,0v2z";

export function Icone({ nom }: { nom: string }): ReactElement {
  if (nom === "lock") {
    return h("svg", { className: "fiche-icone fiche-icone-vecteur", "data-icone": nom, "aria-hidden": "true", focusable: "false", viewBox: "0 0 16 16" }, h("path", { d: TRACE_CADENAS }));
  }
  return h("span", { className: "fiche-icone", "data-icone": nom, "aria-hidden": "true" });
}
