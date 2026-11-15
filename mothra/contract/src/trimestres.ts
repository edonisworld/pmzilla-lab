// Calendar quarters and team codes, as text (task 18.4). Pure: no clock, no time zone. A quarter is named by its first day (ISO date),
// the way the views give `quarter_start`.
import type { Trimestre } from "./fiche.ts";

function parties(date: string): { annee: number; mois: number } {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (m === null) {
    throw new RangeError("date ISO attendue (AAAA-MM-JJ)");
  }
  return { annee: Number(m[1]), mois: Number(m[2]) };
}

function iso(annee: number, mois: number): string {
  return `${String(annee).padStart(4, "0")}-${String(mois).padStart(2, "0")}-01`;
}

// The first day of the quarter that contains the date.
export function debutTrimestreContenant(date: string): string {
  const { annee, mois } = parties(date);
  return iso(annee, 3 * Math.floor((mois - 1) / 3) + 1);
}

// The first day of the quarter `n` quarters after (n > 0) or before (n < 0) the quarter that starts on `debut`.
export function decalerTrimestres(debut: string, n: number): string {
  const { annee, mois } = parties(debut);
  const indice = annee * 4 + Math.floor((mois - 1) / 3) + n;
  return iso(Math.floor(indice / 4), 3 * (((indice % 4) + 4) % 4) + 1);
}

export function trimestreDe(debut: string): Trimestre {
  const { annee, mois } = parties(debut);
  return { year: annee, quarter: (Math.floor((mois - 1) / 3) + 1) as Trimestre["quarter"] };
}

// The label of a quarter in the dashboard: `2026-Q3`.
export function etiquetteTrimestre(debut: string): string {
  const t = trimestreDe(debut);
  return `${String(t.year)}-Q${String(t.quarter)}`;
}

// The last quarter closed as of the data date: the quarter before the one that contains it (a quarter is closed from the day after its
// last day). Reading of the author's decision R-20261030-58, Q11.
export function dernierTrimestreClos(dataDate: string): string {
  return decalerTrimestres(debutTrimestreContenant(dataDate), -1);
}

// The data date of a sheet (audit #629, A-66, R-20261112-30, design D29): the three pure functions below take the UTC day as text, never a clock.
// A data date a sheet can be created on: not after the UTC day (`aujourdhui`, `YYYY-MM-DD`) and in the same UTC quarter as that day.
// Replaces: « date réelle seulement ». Removal: permanent (R-20261112-30).
export function dateDonneesAdmise(dataDate: string, aujourdhui: string): boolean {
  return dataDate <= aujourdhui && debutTrimestreContenant(dataDate) === debutTrimestreContenant(aujourdhui);
}

// A draft or reviewed sheet is stale when the UTC quarter of its data date is not the current one any more (the views then give another window).
export function fichePerimee(dataDate: string, aujourdhui: string): boolean {
  return debutTrimestreContenant(dataDate) !== debutTrimestreContenant(aujourdhui);
}

// The three closed quarters of a data date (change of three closed quarters, R-20261114-49, design D2), the most recent first: the last closed
// quarter, then the two before it. The running quarter is never part of it. Same window, same order as `flow.closed_quarter_starts` in SQL and
// `trois_trimestres_clos` in tools/flow_views.py: a test compares the two functions on every UTC day of 2027 to 2030.
// Replaces: the four offsets written inline in `fenetreConforme`. Removal: permanent, as long as the views show three closed quarters.
export function fenetreTroisTrimestres(dataDate: string): [string, string, string] {
  const dernier = dernierTrimestreClos(dataDate);
  return [dernier, decalerTrimestres(dernier, -1), decalerTrimestres(dernier, -2)];
}

// The three quarters of the window of a data date: every `quarter_start` a view gave must be one of them. A row without a `quarter_start` (the
// pooled year) is not concerned, so the caller passes only the quarters it found.
export function fenetreConforme(debutsLus: readonly string[], dataDate: string): boolean {
  const fenetre = fenetreTroisTrimestres(dataDate);
  return debutsLus.every((debut) => fenetre.includes(debut));
}
