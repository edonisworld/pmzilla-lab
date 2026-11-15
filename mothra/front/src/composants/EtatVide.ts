// The explained empty state (mothra-demo-habillage D17): a sentence of the catalogue that says why nothing is shown, and the link that
// leads to what to do about it. No verdict, no figure.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

export interface PropsEtatVide {
  // The catalogue key of the sentence, and of the label and address of the action.
  phrase: string;
  action?: { cle: string; adresse: string };
}

export function EtatVide({ phrase, action }: PropsEtatVide): ReactElement {
  const intl = useIntl();
  return h(
    "div",
    { className: "etat-vide", role: "status" },
    h("p", null, intl.formatMessage({ id: phrase })),
    action === undefined ? null : h("a", { className: "lien", href: action.adresse }, intl.formatMessage({ id: action.cle })),
  );
}
