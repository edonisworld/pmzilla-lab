// The indicators page template (mothra-demo-habillage D7, D17): the serif title, the introduction, the context line, a grid of cards, then
// the footer. It serves the home; it holds no `section`.
import { createElement as h } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";

export interface PropsGabaritIndicateurs {
  // The catalogue keys of the title and of the introduction.
  titre: string;
  introduction: string;
  contexte?: ReactNode;
  cartes: ReactNode;
  pied?: ReactNode;
}

export function GabaritIndicateurs({ titre, introduction, contexte, cartes, pied }: PropsGabaritIndicateurs): ReactElement {
  const intl = useIntl();
  return h(
    "div",
    { className: "gabarit-indicateurs" },
    h(
      "div",
      { className: "indicateurs-tete" },
      h("h1", { className: "enonce" }, intl.formatMessage({ id: titre })),
      h("p", { className: "indicateurs-introduction" }, intl.formatMessage({ id: introduction })),
      contexte === undefined ? null : h("p", { className: "fiche-contexte" }, contexte),
    ),
    h("div", { className: "grille-cartes" }, cartes),
    pied === undefined ? null : h("footer", { className: "pied-de-fiche" }, pied),
  );
}
