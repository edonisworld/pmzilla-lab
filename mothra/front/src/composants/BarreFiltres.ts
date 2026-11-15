// The filter bar of the second screen (mothra-slices D35, task 31.3): one team at a time (a single choice, never a list), in a neutral order
// that depends on no figure, shown by its opaque identifier (author's decision of 2026-10-27, for the demonstration), and a range of closed
// quarters taken from the answer. No product option (R-20261031-61, Q110 a): no view has a product row. No colour per team, no rank, no side-by-side view. The filters are the address's: the bar only says what
// the person chose, the page writes it back. Labels come from the catalogues.
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the filters leave the dashboard.
import { createElement as h } from "react";
import type { ChangeEvent, FormEvent, ReactElement } from "react";
import { useIntl } from "react-intl";

import type { FiltresEcran } from "../api/filtres.ts";
import { libelleEquipe, ordreEquipes } from "./libelleEquipe.ts";
import type { TableauEnMemoire } from "./libelleEquipe.ts";
import { libelleTrimestre } from "./trimestre.ts";

interface PropsBarre {
  // The opaque identifiers of the teams of the answer, in any order: the bar orders them.
  equipes: readonly string[];
  // The closed quarters of the answer, oldest first.
  trimestres: readonly string[];
  filtres: FiltresEcran;
  surFiltres: (filtres: FiltresEcran) => void;
  // The dashboard answer in memory: the label and the order of the teams come from `libelleEquipe` and `ordreEquipes` (D35, R-20261104-62). The
  // option value stays the opaque identifier. Absent: identifiers, in the order of the identifiers.
  tableau?: TableauEnMemoire;
}

export function BarreFiltres({ equipes, trimestres, filtres, surFiltres, tableau }: PropsBarre): ReactElement {
  const intl = useIntl();
  // The order of every selector (setting off: the identifiers; setting on: the names): an order that depends on no figure, so the bar ranks no team.
  const ordonnees = ordreEquipes(equipes, tableau);
  const formater = (cle: string, valeurs: { year: string; quarter: string }): string => intl.formatMessage({ id: cle }, valeurs);
  const choisirEquipe = (evenement: ChangeEvent<HTMLSelectElement>): void =>
    surFiltres({ ...filtres, team: evenement.target.value });
  // A range is never put the wrong way round (A-82): a start chosen after the end brings the end to it, an end chosen before the start brings
  // the start to it. Quarter labels sort as text.
  const debutCourant = filtres.from ?? trimestres.at(0);
  const finCourante = filtres.to ?? trimestres.at(-1);
  const choisirDebut = (evenement: ChangeEvent<HTMLSelectElement>): void => {
    const debut = evenement.target.value;
    surFiltres({ ...filtres, from: debut, to: finCourante !== undefined && debut > finCourante ? debut : filtres.to });
  };
  const choisirFin = (evenement: ChangeEvent<HTMLSelectElement>): void => {
    const fin = evenement.target.value;
    surFiltres({ ...filtres, from: debutCourant !== undefined && fin < debutCourant ? fin : filtres.from, to: fin });
  };
  const options = trimestres.map((trimestre) => h("option", { key: trimestre, value: trimestre }, libelleTrimestre(trimestre, formater)));
  return h(
    "form",
    { className: "barre-filtres", onSubmit: (evenement: FormEvent<HTMLFormElement>) => evenement.preventDefault() },
    h(
      "fieldset",
      null,
      h("legend", null, intl.formatMessage({ id: "tableau.filters.legend" })),
      h(
        "label",
        { className: "portee" },
        intl.formatMessage({ id: "tableau.filters.team" }),
        h(
          "select",
          { name: "team", value: filtres.team ?? "", onChange: choisirEquipe },
          ordonnees.map((identifiant) => h("option", { key: identifiant, value: identifiant }, libelleEquipe(identifiant, tableau))),
        ),
      ),
      h(
        "label",
        { className: "portee" },
        intl.formatMessage({ id: "tableau.filters.from" }),
        h("select", { name: "from", value: filtres.from ?? trimestres.at(0), onChange: choisirDebut }, options),
      ),
      h(
        "label",
        { className: "portee" },
        intl.formatMessage({ id: "tableau.filters.to" }),
        h("select", { name: "to", value: filtres.to ?? trimestres.at(-1), onChange: choisirFin }, options),
      ),
    ),
  );
}
