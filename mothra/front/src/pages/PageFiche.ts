// The life cycle screen of one sheet (audit #629, A-04; task 19.3, `Fiche`): the sheet is read through the existing reader (one cache key per sheet,
// shared with the conviction page), shown by the `Fiche` component with the action its state offers (review a draft, publish a reviewed sheet), and the
// refusals of the service are told in the catalogue's words by the component. After a successful action the sheet and the lists are read again.
// Beside it, two links: back to the sheets in progress, and to the reading page of the sheet (its conviction page). The page computes nothing.
// Not wired here: the completion of a draft (the component offers it to the author, `estAuteur`, which the answer does not tell: see the report).
// Replaces: nothing. Removal: with the merge of `Fiche` and `FicheConviction` into one sheet screen (design D6 of mothra-demo-habillage).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";

import { adresseConviction, ADRESSE_FICHES } from "../api/adresse.ts";
import { CLE_LISTES_FICHES } from "../api/cycleFiche.ts";
import type { SourceCycleFiche } from "../api/cycleFiche.ts";
import type { ResultatAction } from "../api/fiche.ts";
import { optionsFiche } from "../api/ficheLecture.ts";
import type { LecteurFiche } from "../api/ficheLecture.ts";
import { ErreurApi } from "../api/vue.ts";
import { Fiche } from "../composants/Fiche.ts";
import { HYPOTHESE_DU_GENRE } from "../convictions.ts";
import { cleErreur } from "./PageSquelette.ts";

// A reader that is never called (the query is not enabled without a reader).
const SANS_LECTEUR: LecteurFiche = () => Promise.reject(new ErreurApi("INTERNAL"));

export interface PropsPageFiche {
  id: string;
  lire?: LecteurFiche;
  cycle: SourceCycleFiche;
}

export function PageFiche({ id, lire, cycle }: PropsPageFiche): ReactElement {
  const intl = useIntl();
  const client = useQueryClient();
  const requete = useQuery({ ...optionsFiche(lire ?? SANS_LECTEUR, id), enabled: lire !== undefined });
  const retour = h("a", { className: "lien", href: ADRESSE_FICHES }, intl.formatMessage({ id: "fiche.cycle.back" }));
  if (requete.isError || lire === undefined) {
    const code = requete.error instanceof ErreurApi ? requete.error.code : "INTERNAL";
    return h(
      "section",
      { className: "page" },
      h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cleErreur(code) })),
      h("p", null, retour),
    );
  }
  const fiche = requete.data;
  if (fiche === undefined) return h("section", { className: "page" }, h("p", { role: "status" }, intl.formatMessage({ id: "page.loading" })));
  // After a success the sheet and the lists are read again: the screen then offers the next action of the new state.
  const apres = async (resultat: Promise<ResultatAction>): Promise<ResultatAction> => {
    const issue = await resultat;
    if (issue.ok) await Promise.all([client.invalidateQueries({ queryKey: ["sheet", id] }), client.invalidateQueries({ queryKey: [...CLE_LISTES_FICHES] })]);
    return issue;
  };
  const genre = GRAPHIQUES_DE_FICHE.find((g) => HYPOTHESE_DU_GENRE[g] === fiche.method.hypothesis);
  return h(
    "section",
    { className: "page" },
    h(Fiche, { fiche, onRelire: () => apres(cycle.relire(id)), onPublier: () => apres(cycle.publier(id)) }),
    h("p", null, retour),
    genre === undefined ? null : h("p", null, h("a", { className: "lien", href: adresseConviction(genre, id) }, intl.formatMessage({ id: "fiche.cycle.read" }))),
  );
}
