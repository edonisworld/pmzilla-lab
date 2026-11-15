// The home (mothra-demo-habillage D7), named `squelette` by the address chain: the indicators template with one card per served conviction.
// The status by team section of slice 0 is no longer mounted (Q145 (c), R-20261101-28): it returns, in the form of one scope, with the
// dashboard of the next release. The cards show the statements and the links only (Q158 (b), R-20261101-42). No count of verdicts, no ranking.
// The error messages of the API codes stay here: other screens use `cleErreur`.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { CLES_ERREUR, cleErreur } from "../api/vue.ts";
import type { ReponseVue } from "../api/vue.ts";
import { CarteConviction } from "../composants/CarteConviction.ts";
import { Tableau } from "../composants/Tableau.ts";
import { GabaritIndicateurs } from "../gabarits/GabaritIndicateurs.ts";

// The catalogue keys of the API error codes live in api/vue.ts (shared by every screen); they are re-exported here for the tests that
// import them from the home.
export { CLES_ERREUR, cleErreur };

export type EtatVue =
  | { genre: "chargement" }
  | { genre: "erreur"; code: string }
  | { genre: "donnees"; reponse: ReponseVue };

export function ContenuVue({ etat }: { etat: EtatVue }): ReactElement {
  const intl = useIntl();
  if (etat.genre === "chargement") {
    return h("p", { role: "status" }, intl.formatMessage({ id: "page.loading" }));
  }
  if (etat.genre === "erreur") {
    return h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cleErreur(etat.code) }));
  }
  return h(Tableau, { colonnes: etat.reponse.columns, lignes: etat.reponse.rows, seuil: etat.reponse.threshold });
}

export function PageSquelette({ convictions = [] }: { convictions?: readonly GraphiqueDeFiche[] }): ReactElement {
  const intl = useIntl();
  return h(GabaritIndicateurs, {
    titre: "home.title",
    introduction: "home.intro",
    cartes: convictions.map((genre) => h(CarteConviction, { key: genre, genre })),
    pied: h("p", null, intl.formatMessage({ id: "home.footer.thresholds" })),
  });
}
