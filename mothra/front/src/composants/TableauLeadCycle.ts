// The table of the lead time / cycle time dashboard: one scope (the product or one team), one row per quarter, in the order received.
// The masking threshold is stated once, from the catalogue. Each measure is a value, a masked cell or an insufficient sample, told
// apart as in the chart; no total, no ratio and no comparison is computed here.
import { createElement as h, useId } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { Mesure, PointDeFiche } from "@mothra/contract";

import type { Effectif } from "../api/leadCycle.ts";
import { CelluleInsuffisante, CelluleMasquee, CelluleSimple } from "./Cellule.ts";
import { libelleTrimestre } from "./trimestre.ts";

const COLONNES = ["tableau.column.quarter", "tableau.column.lead", "tableau.column.cycle"] as const;
const COLONNE_EFFECTIFS = "tableau.column.items";

function CelluleMesure({ mesure }: { mesure: Mesure | Effectif }): ReactElement {
  if (mesure.state === "masked") return h(CelluleMasquee);
  if (mesure.state === "insufficient_sample") return h(CelluleInsuffisante);
  return h(CelluleSimple, { valeur: mesure.value });
}

interface PropsTableau {
  // On real data the points carry no count (D34): the Items column is shown only when a point carries one.
  points: readonly PointDeFiche[];
  seuil: number;
  // The ids shared with the chart (aria-describedby): the table, and the sentence that states the masking threshold.
  id?: string;
  idSeuil?: string;
}

export function TableauLeadCycle({ points, seuil, id, idSeuil: idSeuilDonne }: PropsTableau): ReactElement {
  const intl = useIntl();
  const idPropre = useId();
  const idSeuilPropre = useId();
  const idSeuil = idSeuilDonne ?? idSeuilPropre;
  const formater = (cle: string, valeurs: { year: string; quarter: string }): string => intl.formatMessage({ id: cle }, valeurs);
  const avecEffectifs = points.some((point) => point.items !== undefined);
  const colonnes: readonly string[] = avecEffectifs ? [...COLONNES, COLONNE_EFFECTIFS] : COLONNES;
  const entete = h("tr", null, colonnes.map((cle) => h("th", { key: cle, scope: "col" }, intl.formatMessage({ id: cle }))));
  const corps = points.map((point) =>
    h(
      "tr",
      { key: point.quarter },
      h("td", { className: "cellule" }, libelleTrimestre(point.quarter, formater)),
      h(CelluleMesure, { mesure: point.lead }),
      h(CelluleMesure, { mesure: point.cycle }),
      avecEffectifs && point.items !== undefined ? h(CelluleMesure, { mesure: point.items }) : avecEffectifs ? h("td", { className: "cellule" }) : null,
    ),
  );
  return h(
    "div",
    // The scrolling container is reached by the keyboard (A-85).
    { className: "tableau-conteneur", tabIndex: 0 },
    h("p", { className: "tableau-seuil", id: idSeuil }, intl.formatMessage({ id: "tableau.threshold" }, { threshold: seuil })),
    h("table", { className: "tableau", id: id ?? idPropre, "aria-describedby": idSeuil }, h("thead", null, entete), h("tbody", null, corps)),
  );
}
