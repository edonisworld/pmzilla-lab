// The composition of the median lead time of a sheet and its display state (mothra-demo-habillage D3, D5; author's decisions
// R-20261031-74 Q120, Q121 and R-20261031-75 Q132). One pure function of the sheet answer, no I/O. Browser-safe subpath
// `@mothra/contract/composition`: no run-time import (the imports below are types, erased).
// Replaces: nothing. Removal: permanent while a sheet shows its composition; if the sheet answer carries these fields one day, this moves into
// the verdict service and the front reads the answer.
// Lot 1b (R-20261101-05, R-20261101-43): adds `axisShare` to each quarter; removes the threshold markers and the shares of the measured period,
// which `partsDAttente` serves as `waitShares`. Replaces: those markers and shares of lot 1. Removal: permanent while `partsDAttente` is the one
// source of the bars.
//
// Rules: work = median cycle time; waiting = median lead time minus median cycle time, served only when both medians are visible (neither
// masked nor an insufficient sample). A negative difference is `not_comparable`, never a corrected number (no clamp). Q132 removed the
// "same population" condition: the cycle time covers the committed items only, which the sheet's footer says (a text of the front, not here).
// The verdict is never recomputed: the display state is the service's verdict, except `masked` (D5).
import type { CorpsFiche, PointDeFiche } from "./fiche.ts";
import type { Mesure } from "./lead-cycle.ts";
import { ANNEE_GROUPEE } from "./listes-fiche.ts";

export const ETATS_AFFICHAGE = ["confirmed", "refuted", "not_settled", "insufficient_sample", "masked"] as const;
export type EtatAffichage = (typeof ETATS_AFFICHAGE)[number];

// A number of days: a measure of the contract, or `not_comparable` (a negative difference).
export type Jours = Mesure | { state: "not_comparable" };

export type EtatPeriode = "value" | "masked" | "insufficient_sample" | "not_comparable";

// The period the verdict reads: days only. Lot 1b (R-20261101-43) removed its shares and the threshold markers: the bar in parts has one
// source, `partsDAttente` (parts-attente.ts), served by the server as `waitShares`.
export interface PeriodeMesuree {
  quarter: string; // `2026-Q3` or `pooled_year`
  state: EtatPeriode;
  waitDays: Jours;
  workDays: Jours;
  leadDays: Mesure;
}

// A quarter of the chart: the days of PeriodeMesuree, plus its shares and its length on the common axis.
export interface PeriodeComposition extends PeriodeMesuree {
  // Given only when waiting, work and lead time are values and the lead time is above zero; the sum is 100.
  waitShare?: number;
  workShare?: number;
  // Lot 1b (R-20261101-05, Q140): the lead time of the quarter as a share of the largest lead time among the quarters whose lead time is a
  // value, 100 x leadDays / max, so that the rows of the composition chart have comparable lengths with no computation in the front. Given
  // only when the lead time is a value and the largest is above zero.
  axisShare?: number;
}

export interface CompositionConviction {
  state: EtatAffichage;
  measured: PeriodeMesuree;
  quarters: PeriodeComposition[];
}

export function verifierEtatAffichage(etat: string): EtatAffichage {
  if (!(ETATS_AFFICHAGE as readonly string[]).includes(etat)) {
    throw new Error(`état d'affichage inconnu : ${etat}`);
  }
  return etat as EtatAffichage;
}

// D5: the verdict of the service, except `masked` when the verdict is "insufficient sample" and a term of the measured period is masked.
export function etatAffichage(verdict: string, termeMasque: boolean): EtatAffichage {
  return verifierEtatAffichage(verdict === "insufficient_sample" && termeMasque ? "masked" : verdict);
}

// The label of a quarter as the filters of the address write it (`2026-Q3`); exported so that the front does not repeat the format.
export function libelle(t: { year: number; quarter: number }): string {
  return `${String(t.year)}-Q${String(t.quarter)}`;
}

function periode(quarter: string, point: Pick<PointDeFiche, "lead" | "cycle"> | undefined): PeriodeMesuree {
  const lead: Mesure = point === undefined ? { state: "insufficient_sample" } : point.lead;
  const cycle: Mesure = point === undefined ? { state: "insufficient_sample" } : point.cycle;
  let wait: Jours;
  if (lead.state === "masked") {
    wait = { state: "masked", threshold: lead.threshold };
  } else if (cycle.state === "masked") {
    wait = { state: "masked", threshold: cycle.threshold };
  } else if (lead.state === "insufficient_sample" || cycle.state === "insufficient_sample") {
    wait = { state: "insufficient_sample" };
  } else {
    const difference = lead.value - cycle.value;
    wait = difference < 0 ? { state: "not_comparable" } : { state: "value", value: difference };
  }
  return { quarter, state: wait.state, waitDays: wait, workDays: cycle, leadDays: lead };
}

// The shares of a quarter, given when waiting, work and lead time are values and the lead time is above zero.
function avecParts(p: PeriodeMesuree): PeriodeComposition {
  const { waitDays: wait, workDays: cycle, leadDays: lead } = p;
  if (wait.state === "value" && cycle.state === "value" && lead.state === "value" && lead.value > 0) {
    const waitShare = (100 * wait.value) / lead.value;
    return { ...p, waitShare, workShare: 100 - waitShare };
  }
  return p;
}

// Lot 1b (Q140): the common axis of the quarters, 100 for the largest lead time among the visible ones.
function surAxeCommun(quarters: PeriodeComposition[]): PeriodeComposition[] {
  let plus = 0;
  for (const q of quarters) {
    if (q.leadDays.state === "value" && q.leadDays.value > plus) plus = q.leadDays.value;
  }
  if (!(plus > 0)) return quarters;
  return quarters.map((q) => (q.leadDays.state === "value" ? { ...q, axisShare: (100 * q.leadDays.value) / plus } : q));
}

// Q121 (voie a): on a display state of insufficient sample or masked, the measured period serves no figure at all (no days, no waiting, no
// share), even when a median is visible (a P85 too short gives the verdict). A masked state keeps the masked cell and its threshold.
function sansChiffres(p: PeriodeMesuree, etat: "insufficient_sample" | "masked"): PeriodeMesuree {
  const cellule = [p.leadDays, p.workDays].find((m) => m.state === "masked");
  const vide: Mesure = etat === "masked" && cellule !== undefined && cellule.state === "masked" ? { state: "masked", threshold: cellule.threshold } : { state: "insufficient_sample" };
  return { quarter: p.quarter, state: vide.state, waitDays: vide, workDays: vide, leadDays: vide };
}

export function compositionConviction(fiche: CorpsFiche): CompositionConviction {
  const h1 = fiche.method.hypothesis !== "h5";
  const points = fiche.chart?.quarters ?? [];
  const quarters = surAxeCommun(points.map((p) => avecParts(periode(p.quarter, p))));
  let mesure: PeriodeMesuree;
  if (h1) {
    mesure = periode(ANNEE_GROUPEE, fiche.chart?.pooledYear);
  } else {
    const jugee = fiche.method.period.quarters[fiche.method.period.quarters.length - 1];
    const etiquette = jugee === undefined ? "" : libelle(jugee);
    mesure = periode(etiquette, points.find((p) => p.quarter === etiquette));
  }
  const termeMasque = h1 ? mesure.leadDays.state === "masked" || mesure.workDays.state === "masked" : mesure.workDays.state === "masked";
  const state = etatAffichage(fiche.verdict, termeMasque);
  if (state === "insufficient_sample" || state === "masked") {
    mesure = sansChiffres(mesure, state);
  }
  return { state, measured: mesure, quarters };
}
