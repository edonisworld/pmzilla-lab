// A table of one view (design D3 and D8): the threshold is stated once per table, from the catalogue, never in a cell; the totals,
// when a view has any, come from the server as ordinary rows. No sum and no difference is computed here.
import { createElement as h, useId } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { Valeur } from "../api/vue.ts";
import { CelluleDeTableau } from "./Cellule.ts";

// The catalogue key of each column code of the views the front shows; an unknown code is shown as received (a code, not a sentence).
export const CLES_COLONNE: Record<string, string> = {
  team: "column.team",
  type: "column.type",
  status_category: "column.status_category",
  status: "column.status",
  tickets: "column.tickets",
  period: "column.period",
  quarter_start: "column.quarter_start",
  throughput: "column.throughput",
  items_lt: "column.items_lt",
  lead_median_days: "column.lead_median_days",
  lead_p85_days: "column.lead_p85_days",
  items_ct: "column.items_ct",
  cycle_median_days: "column.cycle_median_days",
  cycle_p85_days: "column.cycle_p85_days",
  items_old: "column.items_old",
  items_without_commitment: "column.items_without_commitment",
  tasks_done: "column.tasks_done",
  tasks_without_team: "column.tasks_without_team",
  share_percent: "column.share_percent",
  ready: "column.ready",
  blocked_n: "column.blocked_n",
  blocked: "column.blocked",
  unplanned_n: "column.unplanned_n",
  unplanned: "column.unplanned",
  type_group: "column.type_group",
  created: "column.created",
  done: "column.done",
};

export interface PropsTableau {
  colonnes: readonly string[];
  lignes: ReadonlyArray<Record<string, Valeur>>;
  seuil: number;
}

export function Tableau({ colonnes, lignes, seuil }: PropsTableau): ReactElement {
  const intl = useIntl();
  const idSeuil = useId();
  const entete = h(
    "tr",
    null,
    colonnes.map((colonne) =>
      h("th", { key: colonne, scope: "col" }, Object.hasOwn(CLES_COLONNE, colonne) ?intl.formatMessage({ id: CLES_COLONNE[colonne] }) : colonne),
    ),
  );
  const corps =
    lignes.length === 0
      ? [h("tr", { key: "vide" }, h("td", { colSpan: colonnes.length || 1, className: "cellule cellule-vide" }, intl.formatMessage({ id: "table.empty" })))]
      : lignes.map((ligne, rang) =>
          h("tr", { key: rang }, colonnes.map((colonne) => h(CelluleDeTableau, { key: colonne, valeur: ligne[colonne] ?? null }))),
        );
  return h(
    "div",
    // The scrolling container is reached by the keyboard (A-85).
    { className: "tableau-conteneur", tabIndex: 0 },
    h("p", { className: "tableau-seuil", id: idSeuil }, intl.formatMessage({ id: "table.threshold" }, { threshold: seuil })),
    h("table", { className: "tableau", "aria-describedby": idSeuil }, h("thead", null, entete), h("tbody", null, corps)),
  );
}
