// The status of a sheet in its life cycle (mothra-demo-habillage D6, D17): draft, reviewed, or published. A published sheet is one pill with a
// lock: "Published on {date} · version {number} · frozen", the date in its long form, and the state word is not repeated (R-20261101-126,
// Q3 (a)). A draft and a reviewed sheet keep the word of their state. It draws the state it is given and offers no action: the actions of the
// life cycle (complete, review, publish) stay on the workflow screen of `Fiche`. The classes are defined by the stylesheet from role-named tokens.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { EtatFiche } from "../api/fiche.ts";
import { CLES_ETAT_FICHE } from "./Fiche.ts";
import { Icone } from "./FicheEtats.ts";

export interface PropsStatutFiche {
  etat: EtatFiche;
  // The publication date (ISO), the version number: shown only on a published sheet, and only when the answer carries them.
  publieLe?: string;
  version?: number;
}

export function StatutFiche({ etat, publieLe, version }: PropsStatutFiche): ReactElement {
  const intl = useIntl();
  if (etat === "published" && publieLe !== undefined && version !== undefined) {
    return h(
      "p",
      { className: "statut-fiche statut-publiee", "data-etat-fiche": etat },
      h(Icone, { nom: "lock" }),
      intl.formatMessage({ id: "fiche.status.publishedLine" }, { date: intl.formatDate(publieLe, { dateStyle: "long", timeZone: "UTC" }), number: version }),
    );
  }
  return h(
    "p",
    { className: "statut-fiche", "data-etat-fiche": etat },
    h("span", { className: "statut-etat" }, intl.formatMessage({ id: CLES_ETAT_FICHE[etat] })),
    etat === "published" ? h("span", { className: "statut-detail statut-fige" }, intl.formatMessage({ id: "fiche.frozen" })) : null,
  );
}
