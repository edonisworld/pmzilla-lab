// The stability table of hypothesis 5 (mothra-demo-habillage D4, D17): one row per quarter of the sheet, in their order, with the median and the
// P85 of the cycle time in days and the position of the throughput against the team's own reference. It is a table, not a chart in days: the
// contract serves no common axis for these measures and no reference value (Q147, Q148). The component draws what it is given and computes
// nothing: each figure is a measure of the answer drawn by its state (a value, the masked cell, the insufficient sample), each position a
// catalogue sentence of its code. The judged quarter is marked (a thicker line, bold, `aria-current`), with no text of its own.
// States: values; a masked measure; an insufficient measure; each position code (within the band, under the floor, under the low floor, masked);
// a missing position (a quarter the answer holds no position for) and a missing P85; the judged quarter marked or not.
// No waiting, no bar, no reference value: nothing of hypothesis 1 is read here.
// Replaces: nothing. Removal: permanent while the sheet of hypothesis 5 shows its quarters (the reference and the positions against the band
// come as columns of the same table after the demonstration, Q147 (a)).
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { Mesure, PositionDebit } from "@mothra/contract";

import { CelluleInsuffisante, CelluleMasquee, CelluleSimple } from "./Cellule.ts";
import { libelleTrimestre } from "./trimestre.ts";

// The catalogue key of each throughput position the service sends (D29, D34); a position the table does not know has a fallback key.
const CLES_POSITION: Record<PositionDebit, string> = {
  throughput_within_band: "fiche.position.throughput_within_band",
  throughput_under_floor: "fiche.position.throughput_under_floor",
  throughput_under_low_floor: "fiche.position.throughput_under_low_floor",
  masked: "fiche.position.masked",
};

// The key of a position's sentence; a position that is absent or that the catalogue does not know has the fallback key, never the raw code.
export function clePosition(position: string | undefined): string {
  return position !== undefined && Object.hasOwn(CLES_POSITION, position) ? CLES_POSITION[position as PositionDebit] : "fiche.position.unknown";
}

export interface PropsTableauStabilite {
  // The median cycle time of each quarter of the sheet (`chart.quarters`), in their order; they give the rows.
  trimestres: ReadonlyArray<{ quarter: string; cycle: Mesure }>;
  // The P85 of the cycle time of each quarter (`p85.quarters`), matched to a row by the quarter label.
  p85: ReadonlyArray<{ quarter: string; cycle: Mesure }>;
  // The position of each quarter's throughput (`throughputPositions`), matched to a row by the quarter label.
  positions: ReadonlyArray<{ quarter: string; position: string }>;
  // The label of the judged quarter, marked in the table (absent: no row is marked).
  juge?: string;
}

function CelluleCycle({ mesure }: { mesure: Mesure | undefined }): ReactElement {
  const intl = useIntl();
  if (mesure === undefined) return h(CelluleSimple, { valeur: null });
  if (mesure.state === "masked") return h(CelluleMasquee);
  if (mesure.state === "insufficient_sample") return h(CelluleInsuffisante);
  return h(
    "td",
    { className: "cellule cellule-valeur", "data-state": "value" },
    intl.formatMessage({ id: "conviction.chart.days" }, { days: intl.formatNumber(mesure.value, { maximumFractionDigits: 1 }) }),
  );
}

export function TableauStabilite({ trimestres, p85, positions, juge }: PropsTableauStabilite): ReactElement | null {
  const intl = useIntl();
  if (trimestres.length === 0) return null;
  const formater = (id: string, valeurs: { year: string; quarter: string }): string => intl.formatMessage({ id }, valeurs);
  const colonne = (id: string): ReactElement => h("th", { scope: "col" }, intl.formatMessage({ id }));
  return h(
    "div",
    { className: "tableau-conteneur", tabIndex: 0 },
    h(
      "table",
      { className: "tableau tableau-stabilite", "data-tableau": "stabilite" },
      h("caption", null, intl.formatMessage({ id: "conviction.h5.table.title" })),
      h("thead", null, h("tr", null, colonne("tableau.column.quarter"), colonne("fiche.measure.cycle_median_days"), colonne("fiche.measure.cycle_p85_days"), colonne("fiche.column.throughputPosition"))),
      h(
        "tbody",
        null,
        trimestres.map((t) => {
          const position = positions.find((p) => p.quarter === t.quarter)?.position;
          const marquee = juge !== undefined && t.quarter === juge;
          return h(
            "tr",
            { key: t.quarter, className: marquee ? "ligne-jugee" : undefined, "data-trimestre": t.quarter, "aria-current": marquee ? "true" : undefined },
            h("th", { scope: "row" }, libelleTrimestre(t.quarter, formater)),
            h(CelluleCycle, { mesure: t.cycle }),
            h(CelluleCycle, { mesure: p85.find((p) => p.quarter === t.quarter)?.cycle }),
            h(
              "td",
              { className: "cellule", "data-position": position ?? "unknown" },
              intl.formatMessage({ id: clePosition(position) }),
            ),
          );
        }),
      ),
    ),
  );
}
