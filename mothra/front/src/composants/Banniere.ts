// The information banner (mothra-demo-habillage D1, D17): one note, once per screen, above the main column. Its text follows the dataset code
// of the answer the screen reads: `banner.synthetic` for `synthetic`, `banner.realReduced` for `real` (the reduced form of real data). The
// shell shows it only for a known code (an answer without one shows no banner); the label carries one bold lead, written in the catalogue as
// a rich-text tag.
// Replaces: the rule "no banner on real data". Removal: `banner.realReduced` falls with the reduced form (D34 point 6 of mothra-slices).
import { createElement as h } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";

export type JeuDeDonnees = "synthetic" | "real";

// The catalogue key of each dataset code, written in full so that the catalogue test finds it.
export const CLES_BANNIERE: Record<JeuDeDonnees, string> = {
  synthetic: "banner.synthetic",
  real: "banner.realReduced",
};

// The code is required: no default, so that an answer without a known code can never show the banner of the other one.
export function Banniere({ jeu }: { jeu: JeuDeDonnees }): ReactElement {
  const intl = useIntl();
  return h(
    "div",
    { role: "note", className: "banniere", "data-jeu": jeu },
    intl.formatMessage({ id: CLES_BANNIERE[jeu] }, { b: (morceaux: ReactNode[]) => h("strong", null, ...morceaux) }),
    // The mention of D34 of the synthetic dataset, one line more in the same note (R-20261101-129, Q268 (a)): the dashboard holds no note of its own.
    jeu === "synthetic" ? h("span", { className: "banniere-ligne" }, intl.formatMessage({ id: "fiche.syntheticNotice" })) : null,
  );
}
