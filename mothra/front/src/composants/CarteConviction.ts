// The conviction card of the home (mothra-demo-habillage D7, D17): the theme word and the statement in the serif face. The whole card links to
// the conviction page. For the demonstration the card carries no verdict badge, no figure and nothing read from the browser memory (author's
// answer Q158 (b), R-20261101-42): the statement and the link only. The thin bar and the share sentence of hypothesis 1 are lot 3b.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { adresseConviction } from "../api/adresse.ts";
import { CLES_CONVICTION } from "../convictions.ts";

export function CarteConviction({ genre }: { genre: GraphiqueDeFiche }): ReactElement {
  const intl = useIntl();
  return h(
    "a",
    { className: "carte-conviction", href: adresseConviction(genre), "data-genre": genre },
    h("div", { className: "carte-entete" }, h("span", { className: "carte-theme" }, intl.formatMessage({ id: CLES_CONVICTION[genre].nav }))),
    h("p", { className: "carte-enonce" }, intl.formatMessage({ id: CLES_CONVICTION[genre].enonce })),
    // The text of the link (D7): a span, the whole card being the one link.
    h("span", { className: "carte-lien" }, intl.formatMessage({ id: "conviction.open" })),
  );
}
