// The sheets in progress (audit #629, A-04): the drafts that wait for a review and the reviewed sheets that wait for their publication, each a link
// to the life cycle screen of the sheet. It is how a reviewer finds a draft that someone else made. The list comes from the service by state
// (`GET /api/sheets?state=…`); the page shows what it receives: the kind of the sheet by its catalogue name, its team by `libelleEquipe` (the opaque
// identifier unless the dashboard answer in memory holds a name, N2 (a)), its data date. No count, no verdict, no ranking: the order is the service's.
// Made of links only (reachable by the keyboard); every text comes from the catalogue.
// Replaces: nothing. Removal: with the merge of `Fiche` and `FicheConviction` into one sheet screen (design D6 of mothra-demo-habillage), if the list moves.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";
import type { IntlShape } from "react-intl";

import { porteeDeScope } from "@mothra/contract/equipe";

import { adresseFiche } from "../api/adresse.ts";
import { ETATS_EN_COURS, optionsListeFiches } from "../api/cycleFiche.ts";
import type { EtatEnCours, ResumeFiche, SourceCycleFiche } from "../api/cycleFiche.ts";
import { CLE_LEAD_CYCLE } from "../api/leadCycle.ts";
import { ErreurApi } from "../api/vue.ts";
import { libelleEquipe } from "../composants/libelleEquipe.ts";
import type { TableauEnMemoire } from "../composants/libelleEquipe.ts";
import { CLES_CONVICTION } from "../convictions.ts";
import { cleErreur } from "./PageSquelette.ts";

// The catalogue key of the heading and of the empty sentence of each state, written in full so that the catalogue test finds it.
const CLES_ETAT: Record<EtatEnCours, { titre: string; vide: string }> = {
  draft: { titre: "fiche.list.section.draft", vide: "fiche.list.empty.draft" },
  reviewed: { titre: "fiche.list.section.reviewed", vide: "fiche.list.empty.reviewed" },
};

// The line of one sheet: its kind, its team and its data date. A scope that is not `team.<identifier>` shows the unknown-scope label of the sheet.
function ligne(intl: IntlShape, fiche: ResumeFiche, tableau: TableauEnMemoire | undefined): string {
  const portee = porteeDeScope(fiche.scope);
  const equipe = portee !== null && portee.kind === "team" ? libelleEquipe(portee.team, tableau) : intl.formatMessage({ id: "fiche.scope.unknown" });
  return intl.formatMessage(
    { id: "fiche.list.item" },
    {
      conviction: intl.formatMessage({ id: CLES_CONVICTION[fiche.chart].nav }),
      team: equipe,
      date: intl.formatDate(fiche.dataDate, { dateStyle: "medium", timeZone: "UTC" }),
    },
  );
}

function SectionEtat({ etat, cycle, tableau }: { etat: EtatEnCours; cycle: SourceCycleFiche; tableau: TableauEnMemoire | undefined }): ReactElement {
  const intl = useIntl();
  const requete = useQuery(optionsListeFiches(cycle.lister, etat));
  let corps: ReactElement;
  if (requete.isError) {
    const code = requete.error instanceof ErreurApi ? requete.error.code : "INTERNAL";
    corps = h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cleErreur(code) }));
  } else if (requete.data === undefined) {
    corps = h("p", { role: "status" }, intl.formatMessage({ id: "page.loading" }));
  } else if (requete.data.length === 0) {
    corps = h("p", { className: "tableau-date" }, intl.formatMessage({ id: CLES_ETAT[etat].vide }));
  } else {
    corps = h(
      "ul",
      { className: "liste-fiches" },
      requete.data.map((fiche) => h("li", { key: fiche.id }, h("a", { className: "lien", href: adresseFiche(fiche.id) }, ligne(intl, fiche, tableau)))),
    );
  }
  return h("section", { "data-etat-liste": etat }, h("h3", null, intl.formatMessage({ id: CLES_ETAT[etat].titre })), corps);
}

export function PageFiches({ cycle }: { cycle: SourceCycleFiche }): ReactElement {
  const intl = useIntl();
  const tableau = useQueryClient().getQueryData<TableauEnMemoire>(CLE_LEAD_CYCLE);
  return h(
    "section",
    { className: "page", "aria-labelledby": "page-titre" },
    h("h2", { id: "page-titre" }, intl.formatMessage({ id: "fiche.list.title" })),
    h("p", { className: "tableau-date" }, intl.formatMessage({ id: "fiche.list.intro" })),
    ETATS_EN_COURS.map((etat) => h(SectionEtat, { key: etat, etat, cycle, tableau })),
  );
}
