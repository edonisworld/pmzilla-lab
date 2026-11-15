// The structured masked cell (mothra-slices D3): one TypeBox schema, published as contrats/schemas/cellule.schema.json.
// A count cell is a value cell or a masked cell; a masked cell has no value property at all.
import Type from "typebox";
import type { Static } from "typebox";

import { PLANCHER } from "./plancher.ts";

// `Type.Literal` so that `Static<>` gives a union discriminated by `state`: testing `state === "masked"` narrows to the cell
// without any `value` property.
export const SchemaCelluleValeur = Type.Object(
  {
    state: Type.Literal("value"),
    value: Type.Integer({ minimum: PLANCHER }),
  },
  { additionalProperties: false },
);

export const SchemaCelluleMasquee = Type.Object(
  {
    state: Type.Literal("masked"),
    threshold: Type.Integer({ minimum: PLANCHER }),
  },
  { additionalProperties: false },
);

export const SchemaCellule = Type.Union([SchemaCelluleValeur, SchemaCelluleMasquee]);

// The shown zero (R-20261106-39, R-20261106-43, Q2 (a)): accepted on one column only, items_old of v_team_lead_time_throughput. Not part of
// SchemaCellule: every other cell of the contract keeps the floor of five.
// Replaces: the masking of the zero of items_old (R-20261106-39). Removal: permanent while the view publishes items_old (SchemaCelluleAnciens and colonneAvecZero).
export const SchemaCelluleZero = Type.Object({ state: Type.Literal("value"), value: Type.Literal(0) }, { additionalProperties: false });
export const SchemaCelluleAnciens = Type.Union([SchemaCelluleValeur, SchemaCelluleZero, SchemaCelluleMasquee]);

export function colonneAvecZero(vue: string, colonne: string): boolean {
  return vue === "v_team_lead_time_throughput" && colonne === "items_old";
}

export type Cellule = Static<typeof SchemaCellule>;

// A maskable measure (a statistic or a share, R-20261030-49): the value cell of a measure holds any number (a median of 3.5 days is not
// a count at or above the floor); its masked form is the masked cell of D3. Declared per view by `maskableColumns` of the contract.
export const SchemaCelluleMesure = Type.Object(
  {
    state: Type.Literal("value"),
    value: Type.Number(),
  },
  { additionalProperties: false },
);

export const SchemaCelluleMesuree = Type.Union([SchemaCelluleMesure, SchemaCelluleMasquee]);

// The cell of a measure: shown only when the rules of its view say so and the view gave a number; otherwise the masked cell, with nothing
// of the measure kept.
export function celluleMesure(valeur: number | null, visible: boolean, seuil: number): Cellule {
  if (!Number.isInteger(seuil) || seuil < 0) {
    throw new TypeError("seuil : entier positif attendu");
  }
  if (valeur !== null && !Number.isFinite(valeur)) {
    throw new TypeError("mesure : nombre fini ou NULL attendu");
  }
  if (!visible || valeur === null) {
    return { state: "masked", threshold: Math.max(PLANCHER, seuil) };
  }
  return { state: "value", value: valeur };
}

// A count from a view (NULL when the database masked it) and the effective threshold give the cell. Nothing of a masked count
// is kept: no value, no estimate, no range. A threshold under the floor is raised to it.
//
// `zeroAutorise` (R-20261106-39, R-20261106-43, Q2 (a)): true only for items_old of v_team_lead_time_throughput (see `colonneAvecZero`), whose
// zero is shown when the rules of the view say so; 1 to 4 stay masked there too.
export function cellule(compte: number | null, seuil: number, zeroAutorise = false): Cellule {
  if (!Number.isInteger(seuil) || seuil < 0) {
    throw new TypeError("seuil : entier positif attendu");
  }
  if (compte !== null && (!Number.isInteger(compte) || compte < 0)) {
    throw new TypeError("compte : entier positif ou NULL attendu");
  }
  const effectif = Math.max(PLANCHER, seuil);
  if (zeroAutorise && compte === 0) {
    return { state: "value", value: 0 };
  }
  if (compte === null || compte < effectif) {
    return { state: "masked", threshold: effectif };
  }
  return { state: "value", value: compte };
}
