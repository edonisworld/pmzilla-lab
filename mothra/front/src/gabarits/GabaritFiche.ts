// The sheet page template (mothra-demo-habillage D6, D17): the overline, the statement with the verdict badge, the status and the context line,
// the evidence card, the three insets, the competing explanations, then the footer. The page fills the slots; the template fixes the order and
// the shape. Lot 3a shipped the template; lot 3b adds the slots of the status and of the competing explanations (Q240, R-20261101-121): a page
// that gives neither draws exactly what it drew before.
import { createElement as h } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";

export interface PropsGabaritFiche {
  // The catalogue key of the statement; the badge and the context line are given drawn.
  enonce: string;
  badge?: ReactElement;
  // The status of the sheet in its life cycle, after the badge (lot 3b).
  statut?: ReactNode;
  contexte?: ReactNode;
  // The state of the evidence card (its outline follows the display state); absent for a page with no sheet.
  etat?: string;
  preuve?: ReactNode;
  // The three insets, already drawn.
  encarts?: ReactNode;
  // The block of the competing explanations, after the insets (lot 3b).
  explications?: ReactNode;
  pied?: ReactNode;
}

export function GabaritFiche({ enonce, badge, statut, contexte, etat, preuve, encarts, explications, pied }: PropsGabaritFiche): ReactElement {
  const intl = useIntl();
  return h(
    "article",
    { className: "gabarit-fiche" },
    h(
      "div",
      { className: "fiche-tete" },
      h("p", { className: "surtitre" }, intl.formatMessage({ id: "conviction.overline" })),
      h("h1", { className: "enonce" }, intl.formatMessage({ id: enonce })),
      badge === undefined && statut === undefined && contexte === undefined
        ? null
        : h("div", { className: "fiche-ligne-badge" }, badge, statut, contexte === undefined ? null : h("span", { className: "fiche-contexte" }, contexte)),
    ),
    preuve === undefined ? null : h("section", { className: "carte carte-preuve", "data-etat": etat }, preuve),
    encarts === undefined ? null : h("div", { className: "encarts" }, encarts),
    explications === undefined ? null : h("div", { className: "bloc-explications" }, explications),
    pied === undefined ? null : h("footer", { className: "pied-de-fiche" }, pied),
  );
}
