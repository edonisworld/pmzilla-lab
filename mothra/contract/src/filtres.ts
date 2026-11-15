// The shared filters framework of the second screen (mothra-slices D35, group 31, tasks 31.1 and 31.2): the scope check, the range
// check and the range total, as pure functions. No route, formatting or component computes a total over a range.
// Codes only, no text (invariant 11). No array of teams, no sort parameter, any undeclared field refused.
import Type from "typebox";
import type { Static } from "typebox";

import { cellule } from "./cellule.ts";
import type { Cellule } from "./cellule.ts";
import { MOTIF_IDENTIFIANT_EQUIPE } from "./equipe.ts";
import { PLANCHER } from "./plancher.ts";

export type CodeFiltre = "SCOPE_INVALID" | "RANGE_INVALID";

// The window of the views, in whole closed quarters: the last three, which always fit inside the retained year (ADR 0004: retention clock of one
// year; change of three closed quarters, R-20261114-49). Replaces: four. Removal: permanent while the views show three closed quarters.
export const TRIMESTRES_RETENUS = 3;

// The querystring schema of the routes with filters, the one source (no second schema): any undeclared field is refused (no sort
// parameter), from and to are required strings. The team is read as unknown so that a repeated team (array) reaches `verifierFiltres`
// and answers 422 SCOPE_INVALID instead of a schema error. Its absence means the whole product.
export const SchemaFiltres = Type.Object(
  { team: Type.Optional(Type.Unknown()), from: Type.String(), to: Type.String() },
  { additionalProperties: false },
);
export type Filtres = Static<typeof SchemaFiltres>;

export type Portee = { kind: "product" } | { kind: "team"; team: string };

export type ResultatFiltres =
  | { ok: true; scope: Portee; from: string; to: string; periods: string[] }
  | { ok: false; status: 422; code: CodeFiltre };

export interface OptionsFiltres {
  // The date of the reading, `YYYY-MM-DD`: only quarters that ended before it are closed (author's decision M5).
  today: string;
}

const MOTIF_TRIMESTRE = /^([0-9]{4})-Q([1-4])$/;
const MOTIF_DATE = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/;

// The opaque team identifier lives in equipe.ts (the browser-safe subpath); re-exported here so that the tests and the server have one name.
export { MOTIF_IDENTIFIANT_EQUIPE, identifiantEquipe, scopeFiche } from "./equipe.ts";

// A quarter as a sortable index (year * 4 + quarter - 1), or null when the string is not a quarter.
function indexTrimestre(valeur: string): number | null {
  const m = MOTIF_TRIMESTRE.exec(valeur);
  if (m === null) return null;
  return Number(m[1]) * 4 + Number(m[2]) - 1;
}

function libelleTrimestre(index: number): string {
  return `${Math.floor(index / 4)}-Q${(index % 4) + 1}`;
}

// The index of the last quarter closed at `today`: the quarter that contains `today` is running, so the one before it is the last closed.
function dernierFerme(today: string): number {
  const m = MOTIF_DATE.exec(today);
  if (m === null) throw new TypeError("today : AAAA-MM-JJ attendu");
  const mois = Number(m[2]);
  if (mois < 1 || mois > 12) throw new TypeError("today : mois invalide");
  const courant = Number(m[1]) * 4 + Math.floor((mois - 1) / 3);
  return courant - 1;
}

const refus = (code: CodeFiltre): ResultatFiltres => ({ ok: false, status: 422, code });

// The scope and the range of a request, as the query holds them (values unknown: an array, an object or a number is refused here).
// The query has already passed `SchemaFiltres` (400 INVALID_REQUEST for an undeclared field, a missing from or to, a wrong type).
// - an array, a list or a malformed identifier for the team: 422 SCOPE_INVALID (no team = the whole product);
// - a malformed, inverted, running, future or out-of-the-window quarter, or a range longer than three quarters: 422 RANGE_INVALID.
// The scope is checked before the range.
export function verifierFiltres(entree: unknown, options: OptionsFiltres): ResultatFiltres {
  if (entree === null || typeof entree !== "object" || Array.isArray(entree)) return refus("SCOPE_INVALID");
  const champs = entree as Record<string, unknown>;
  const equipe = champs.team;
  let portee: Portee;
  if (equipe === undefined) {
    portee = { kind: "product" };
  } else if (typeof equipe === "string" && MOTIF_IDENTIFIANT_EQUIPE.test(equipe)) {
    portee = { kind: "team", team: equipe };
  } else {
    return refus("SCOPE_INVALID");
  }
  const { from, to } = champs;
  if (typeof from !== "string" || typeof to !== "string") return refus("RANGE_INVALID");
  const debut = indexTrimestre(from);
  const fin = indexTrimestre(to);
  if (debut === null || fin === null || debut > fin) return refus("RANGE_INVALID");
  if (fin > dernierFerme(options.today)) return refus("RANGE_INVALID");
  if (fin - debut + 1 > TRIMESTRES_RETENUS) return refus("RANGE_INVALID");
  // Inside the window: the last three closed quarters.
  if (debut < dernierFerme(options.today) - (TRIMESTRES_RETENUS - 1)) return refus("RANGE_INVALID");
  const periodes: string[] = [];
  for (let i = debut; i <= fin; i += 1) periodes.push(libelleTrimestre(i));
  return { ok: true, scope: portee, from, to, periods: periodes };
}

export interface PeriodeCompte {
  period: string;
  count: Cellule;
}

// The total of a range of closed periods (task 31.2, D3): the sum of the counts when no period of the range is masked, otherwise a
// structured masked cell. Nothing of a masked period is estimated: the masked total carries the highest threshold met. A period of the
// range absent from the data is a caller error (TypeError), not a masked cell. The periods outside the range are ignored.
// PRECONDITION: the input cells are the output of the masking function of 15.3 (primary and complementary masking, R-144), never the raw
// counts of a view: the rule "no total when a period is masked" closes the difference attack only on cells masked that way.
// Wiring (group 37): input = that function's output.
export function totalDePlage(periodes: readonly PeriodeCompte[], from: string, to: string): Cellule {
  const debut = indexTrimestre(from);
  const fin = indexTrimestre(to);
  if (debut === null || fin === null || debut > fin) throw new TypeError("plage : trimestres attendus, dans l'ordre");
  const parPeriode = new Map<string, Cellule>();
  for (const p of periodes) {
    if (parPeriode.has(p.period)) throw new TypeError("plage : période en double");
    parPeriode.set(p.period, p.count);
  }
  let somme = 0;
  let masque = false;
  let seuil = PLANCHER;
  for (let i = debut; i <= fin; i += 1) {
    const c = parPeriode.get(libelleTrimestre(i));
    if (c === undefined) throw new TypeError("plage : période manquante");
    if (c.state === "masked") {
      masque = true;
      seuil = Math.max(seuil, c.threshold);
    } else {
      somme += c.value;
    }
  }
  // The raised-to-floor rule of the cell builder applies to the masked total; a sum of unmasked cells is never under a threshold.
  return masque ? cellule(null, seuil) : { state: "value", value: somme };
}
