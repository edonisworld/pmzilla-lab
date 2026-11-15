// The pure functions of the page "preparation of a cycle" (mothra-slices D35, task 40.2, R-169): the cycle selection, the domain scope, the
// total shown only without a masked cell, and the choice of the state codes. No route, formatting or component computes any of them.
// The input cells are the output of the masking function of task 15.3 (`masquerVue`, reused, never copied: this module holds no masking rule);
// the rules of the views ("Ready", "candidate to Epic Review") are in the views, never recomputed here.
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the page leaves the product.
// Pure: no run-time import of typebox, of a schema or of `cellule.ts` (which holds a schema); types only from them (erased).
import type { Cellule } from "../cellule.ts";
import type { CodeFiltre } from "../filtres.ts";
import { PLANCHER } from "../plancher.ts";
import type { CodeAvis, CodeEtatVide, CodeSourceReady } from "./codes.ts";
import { CODE_COMPTES_REELS_MASQUES, CODE_DOMAINE_TROP_PETIT, MOTIF_CLE_CYCLE } from "./codes.ts";

// A domain of fewer than three teams gets no count (author's decision R-20261031-17, Q46).
export const EQUIPES_MINIMUM_DOMAINE = 3;

// ---- cycle selection ---------------------------------------------------------------------------------------------------------------
export type EtatCycle = "upcoming" | "running" | "ended";
// One row of the cycle key view of task 38.1: the neutral key, the dates, the state. No count.
export interface CycleCle {
  key: string;
  start: string;
  end: string;
  state: EtatCycle;
}
export type ResultatCycle =
  | { ok: true; cycle: CycleCle | null; cycles: CycleCle[] }
  | { ok: false; status: 422; code: "CYCLE_UNKNOWN" };

const ETATS_CYCLE: readonly string[] = ["upcoming", "running", "ended"];
// The dates are compared as text: only the ISO form orders correctly.
const MOTIF_DATE = /^\d{4}-\d{2}-\d{2}$/;

// The cycles the page offers, in the neutral order (start, then key): the upcoming and running ones only. Without a requested key the first of
// them is selected, and none when there is none (the empty-state code is chosen by `choisirEtats`). A requested key outside the offered cycles
// (an ended one, an unknown one) is refused with 422 CYCLE_UNKNOWN. A duplicated key or an unknown state is a caller error.
export function choisirCycle(cycles: readonly CycleCle[], demande: string | undefined): ResultatCycle {
  const vues = new Set<string>();
  for (const x of cycles) {
    if (!MOTIF_DATE.test(x.start) || !MOTIF_DATE.test(x.end)) throw new TypeError("cycle : date AAAA-MM-JJ attendue");
    if (!MOTIF_CLE_CYCLE.test(x.key)) throw new TypeError("cycle : clé hors du motif [a-z0-9-]{1,32}");
    if (!ETATS_CYCLE.includes(x.state)) throw new TypeError("cycle : état inconnu");
    if (vues.has(x.key)) throw new TypeError("cycle : clé en double");
    vues.add(x.key);
  }
  const offerts = cycles
    .filter((x) => x.state !== "ended")
    .map((x) => ({ ...x }))
    .sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  if (demande === undefined) return { ok: true, cycle: offerts[0] ?? null, cycles: offerts };
  const choisi = offerts.find((x) => x.key === demande);
  return choisi === undefined ? { ok: false, status: 422, code: "CYCLE_UNKNOWN" } : { ok: true, cycle: choisi, cycles: offerts };
}

// ---- domain scope ------------------------------------------------------------------------------------------------------------------
// SCOPE_INVALID is the code of the filters framework (task 31.1); the type below ties it to that definition.
const SCOPE_INVALID: Extract<CodeFiltre, "SCOPE_INVALID"> = "SCOPE_INVALID";
export type ResultatPortee =
  | { ok: true; cycle: string | undefined }
  | { ok: false; status: 422; code: typeof SCOPE_INVALID | "CYCLE_UNKNOWN" };

// The page holds the domain line only (M3): any team, whatever its form (an identifier, a list, an empty text, null), is refused with 422
// SCOPE_INVALID, and so is a query that is not an object. The scope is checked before the cycle. A cycle that is not a text is refused
// with 422 CYCLE_UNKNOWN (the schema has already answered 400 for a wrong type; this is the defence of a direct call).
export function verifierPorteeDomaine(entree: unknown): ResultatPortee {
  if (entree === null || typeof entree !== "object" || Array.isArray(entree)) return { ok: false, status: 422, code: SCOPE_INVALID };
  const champs = entree as Record<string, unknown>;
  if (champs.team !== undefined) return { ok: false, status: 422, code: SCOPE_INVALID };
  if (champs.cycle !== undefined && typeof champs.cycle !== "string") return { ok: false, status: 422, code: "CYCLE_UNKNOWN" };
  return { ok: true, cycle: champs.cycle };
}

// ---- total only without a masked cell ----------------------------------------------------------------------------------------------
// The total of cells (the columns of the cycle): the sum when no cell is masked, otherwise the masked cell of the highest threshold met.
// Nothing of a visible cell is kept by a masked total. No cell at all is a caller error, never a zero.
// PRECONDITION: the cells are the output of the masking function of 15.3 (primary and complementary masking), never raw counts.
export function totalDesCellules(cellules: readonly Cellule[]): Cellule {
  if (cellules.length === 0) throw new TypeError("total : au moins une cellule attendue");
  let somme = 0;
  let masque = false;
  let seuil = PLANCHER;
  for (const x of cellules) {
    if (x.state === "masked") {
      masque = true;
      seuil = Math.max(seuil, x.threshold);
    } else {
      somme += x.value;
    }
  }
  // The masked cell of D3, built here so that this module imports no schema; `seuil` is at least the floor.
  return masque ? { state: "masked", threshold: seuil } : { state: "value", value: somme };
}

// ---- state codes -------------------------------------------------------------------------------------------------------------------
// What the choice reads: the referential's state and the row counts of the view answers; no cell, no count of epics.
export interface EntreeEtats {
  // Teams of the domain served, from the referential. Under three: the explained empty state.
  domainTeamCount: number;
  // Upcoming and running cycles offered by `choisirCycle`.
  offeredCycles: number;
  // The summary view has a row for the selected cycle (a zero count never is a row, a masked count is a row).
  summaryRowPresent: boolean;
  // The label history has been collected for the domain.
  labelHistoryCollected: boolean;
  // The Discovery Workflow mapping has a validation date.
  mappingValidated: boolean;
  // Real data whose counts are not shown (D34 point 7): the service of task 40.3 decides it from the dataset; the contract only reads it.
  realCountsHidden: boolean;
  // The source of the Ready count, as the referential states it.
  readySource: "label" | "column";
}
export interface ResultatEtats {
  emptyState: CodeEtatVide | null;
  notices: CodeAvis[];
  readySource: CodeSourceReady;
}

function compte(valeur: number): number {
  if (!Number.isInteger(valeur) || valeur < 0) throw new TypeError("compte : entier positif attendu");
  return valeur;
}

// The explained empty state, in this order (author's answers R-20261031-17 and R-20261031-58): a domain of fewer than three teams; real data
// with counts not shown (explicit input, chosen by the service of task 40.3 from the dataset); no cycle to offer; no label history collected
// (an empty state in every case); a cycle without a summary row ("no epic for the cycle"). The position of the two last ones is mine: without
// a history nothing can be said about the labels, so "no epic" is not claimed.
// The only notice of a page that is shown is the mapping not validated (columns not computed).
// With an explained empty state the notices are empty (the answer schema says so). While the mapping is not validated the Ready source is the
// label (spec mothra-workshops, scenario "Mapping not validated"), whatever the referential says.
export function choisirEtats(entree: EntreeEtats): ResultatEtats {
  const equipes = compte(entree.domainTeamCount);
  const cycles = compte(entree.offeredCycles);
  if (typeof entree.summaryRowPresent !== "boolean") throw new TypeError("résumé : booléen attendu");
  const ligne = entree.summaryRowPresent;
  if (typeof entree.realCountsHidden !== "boolean") throw new TypeError("données réelles : booléen attendu");
  let emptyState: CodeEtatVide | null = null;
  if (equipes < EQUIPES_MINIMUM_DOMAINE) emptyState = CODE_DOMAINE_TROP_PETIT;
  else if (entree.realCountsHidden) emptyState = CODE_COMPTES_REELS_MASQUES;
  else if (cycles === 0) emptyState = "no_cycle_configured";
  else if (!entree.labelHistoryCollected) emptyState = "no_label_history";
  else if (!ligne) emptyState = "no_epic_for_cycle";
  const notices: CodeAvis[] = [];
  if (emptyState === null && !entree.mappingValidated) notices.push("mapping_not_validated");
  const source = entree.mappingValidated ? entree.readySource : "label";
  return { emptyState, notices, readySource: source === "label" ? "ready_source_label" : "ready_source_column" };
}

// What the notice "mapping not validated" ties together: the columns are not computed, so the columns, their total and the Epic Review
// candidates (a count within a column) are absent. Applied by the service layer to the answer; with a validated mapping it changes nothing.
export function cadrerSelonMapping<C, T, K>(
  avis: readonly CodeAvis[],
  colonnes: C[],
  total: T | null,
  parColonne: K | null,
): { columns: C[]; columnsTotal: T | null; candidates: K | null } {
  if (avis.includes("mapping_not_validated")) return { columns: [], columnsTotal: null, candidates: null };
  return { columns: colonnes, columnsTotal: total, candidates: parColonne };
}
