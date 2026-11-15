// The side navigation (mothra-demo-habillage D1, D17): the mark and the name at the top, the home, one entry per served conviction, the
// dashboard, and at the bottom what the shell puts there (identifier field, language selector). The current entry is lighter and carries
// `aria-current="page"`. The convictions are the contract's closed list, given by the caller after its filter; none is written here. For the
// demonstration the entries show the statements and the links only: no verdict, no state marker, nothing read from the browser memory
// (author's answer Q158 (b), R-20261101-42).
import { createElement as h } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";

import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { ADRESSE_FICHES, adresseConviction } from "../api/adresse.ts";
import { CLES_CONVICTION } from "../convictions.ts";
import { MARQUE } from "../marque.ts";

export interface EntreeConviction {
  genre: GraphiqueDeFiche;
  courante: boolean;
}

export interface PropsNavigationLaterale {
  accueilCourant: boolean;
  convictions: readonly EntreeConviction[];
  // Present when the dashboard source is given; absent otherwise (the entry is not offered).
  tableau?: { courant: boolean };
  // Present when the source of the life cycle of the sheets is given (audit #629, A-04); absent otherwise (the entry is not offered). It is
  // current on the list and on the screen of a sheet.
  fiches?: { courant: boolean };
  bas?: ReactNode;
}

export const ADRESSE_ACCUEIL = "#/";
export const ADRESSE_TABLEAU_NAV = "#/tableau";

function Entree({ adresse, courante, children }: { adresse: string; courante: boolean; children?: ReactNode }): ReactElement {
  return h("a", { href: adresse, className: courante ? "nav-entree nav-entree-courante" : "nav-entree", "aria-current": courante ? "page" : undefined }, children);
}

export function NavigationLaterale({ accueilCourant, convictions, tableau, fiches, bas }: PropsNavigationLaterale): ReactElement {
  const intl = useIntl();
  return h(
    "aside",
    { className: "nav-laterale" },
    h(
      "header",
      { className: "nav-marque" },
      h("a", { href: ADRESSE_ACCUEIL, className: "nav-logo" }, h("img", { className: "logo", src: MARQUE.logo, alt: intl.formatMessage({ id: "logo.mothra.alt" }) })),
    ),
    h(
      "nav",
      { className: "nav-liste", "aria-label": intl.formatMessage({ id: "nav.label" }) },
      h(Entree, { adresse: ADRESSE_ACCUEIL, courante: accueilCourant }, intl.formatMessage({ id: "nav.home" })),
      convictions.length === 0 ? null : h("p", { className: "nav-titre" }, intl.formatMessage({ id: "nav.convictions" })),
      convictions.map((c) => h(Entree, { key: c.genre, adresse: adresseConviction(c.genre), courante: c.courante }, intl.formatMessage({ id: CLES_CONVICTION[c.genre].nav }))),
      tableau === undefined && fiches === undefined ? null : h("p", { className: "nav-titre" }, intl.formatMessage({ id: "nav.tools" })),
      tableau === undefined ? null : h(Entree, { adresse: ADRESSE_TABLEAU_NAV, courante: tableau.courant }, intl.formatMessage({ id: "nav.dashboard" })),
      fiches === undefined ? null : h(Entree, { adresse: ADRESSE_FICHES, courante: fiches.courant }, intl.formatMessage({ id: "nav.sheets" })),
    ),
    bas === undefined ? null : h("div", { className: "nav-bas" }, bas),
  );
}
