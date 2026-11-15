// Cells of a table (design D3): a masked cell shows the catalogue label of the masked state with the masked-cell token, distinct from an
// empty cell and from a zero. Nothing is computed from a cell: a value is shown as received, a masked cell carries no value at all.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { Cellule } from "@mothra/contract";

import type { Valeur } from "../api/vue.ts";
import { GLYPHES_ICONES } from "./glyphes.ts";

// The catalogue key of each state of a count cell (the API sends the state code, the front translates it).
export const CLES_ETAT: Record<Cellule["state"], string> = {
  value: "cellState.value",
  masked: "cellState.masked",
};

export function estCellule(valeur: Valeur): valeur is Cellule {
  return typeof valeur === "object" && valeur !== null && "state" in valeur;
}

export function CelluleMasquee(): ReactElement {
  const intl = useIntl();
  return h("td", { className: "cellule cellule-masquee", "data-state": "masked" }, intl.formatMessage({ id: CLES_ETAT.masked }));
}

// An insufficient sample (design D22) is not a masked cell: its own dotted outline with no fill, its own icon and its own label. It
// carries no value at all.
export function CelluleInsuffisante(): ReactElement {
  const intl = useIntl();
  return h(
    "td",
    { className: "cellule cellule-insuffisante", "data-state": "insufficient_sample" },
    // The icon has its own shape (a dotted outline) and spacing, so it does not read as a truncation of the label (A-13).
    h("span", { className: "icone-etat", "aria-hidden": "true" }, GLYPHES_ICONES.ellipsis),
    " ",
    intl.formatMessage({ id: "state.insufficient_sample" }),
  );
}

export function CelluleSimple({ valeur }: { valeur: Valeur }): ReactElement {
  const intl = useIntl();
  if (valeur === null) return h("td", { className: "cellule cellule-vide", "data-state": "empty" });
  if (typeof valeur === "number") {
    return h("td", { className: "cellule cellule-valeur", "data-state": "value" }, intl.formatNumber(valeur));
  }
  return h("td", { className: "cellule" }, String(valeur));
}

export function CelluleDeTableau({ valeur }: { valeur: Valeur }): ReactElement {
  if (!estCellule(valeur)) return h(CelluleSimple, { valeur });
  if (valeur.state === "masked") return h(CelluleMasquee);
  return h(CelluleSimple, { valeur: valeur.value });
}
