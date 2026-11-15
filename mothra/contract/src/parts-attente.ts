// The bars of the share of waiting of hypothesis 1, served by the server (mothra-demo-habillage D3b; author's decisions R-20261101-05,
// R-20261101-20, R-20261101-22, R-20261101-32, R-20261101-43). One pure function of the sheet answer, no I/O: the server's service layer calls
// it on a hypothesis 1 answer, full or reduced, and serves its result as `waitShares`; the front reads that field and computes nothing.
// It reads only fields the reduced form keeps (the pooled-year ratios, the thresholds, the verdict), so it stays valid on real data (D34).
//
// Rules: a bar is the share of waiting `100 x (1 - 1/ratio)` of a ratio lead time over cycle time. A ratio under 1 is `not_comparable`, never
// a corrected number; a masked ratio keeps its threshold and has no number; an insufficient ratio has none either; on the verdict
// "insufficient sample" no share is served (each bar takes `insufficient_sample`, or `masked` when its ratio is masked). A threshold of 1
// or under is out of scale: its ratio is given, its share is not (it would be zero or negative).
// `waitShares` is computed at each reading from the frozen ratios and thresholds and never stored (Q151): a change of this formula changes the
// reading of sheets already published, so it is an author's decision (written in D34 point 5 of mothra-slices) and the test that fixes its
// result changes in the same reviewed commit, citing it.
// Replaces: for the bar, the markers and the shares of the measured period of `compositionConviction` (lot 1, removed by R-20261101-43).
// Removal: permanent while the bar in parts measures hypothesis 1.
import type { CorpsFiche } from "./fiche.ts";
import type { Mesure } from "./lead-cycle.ts";

export type BarreAttente =
  | { state: "value"; ratio: number; waitShare: number; workShare: number }
  | { state: "masked"; threshold: number }
  | { state: "insufficient_sample" }
  | { state: "not_comparable" };

// A threshold turned into a ratio and a share of waiting. Out of scale (threshold of 1 or under): no share, shown as text only.
export interface RepereAttente {
  ratio: number;
  inScale: boolean;
  share?: number;
}

export interface PartsDAttente {
  median: BarreAttente;
  p85: BarreAttente;
  markers: { refutation: RepereAttente; confirmation: RepereAttente; applicable: boolean };
}

// What the function reads of a sheet answer.
export type EntreePartsDAttente = Pick<CorpsFiche, "verdict" | "ratios" | "method">;

function barre(rapport: Mesure | undefined, verdictInsuffisant: boolean): BarreAttente {
  if (rapport === undefined) {
    return { state: "insufficient_sample" };
  }
  if (rapport.state === "masked") {
    return { state: "masked", threshold: rapport.threshold };
  }
  if (verdictInsuffisant || rapport.state === "insufficient_sample") {
    return { state: "insufficient_sample" };
  }
  if (!(rapport.value >= 1)) {
    return { state: "not_comparable" };
  }
  const attente = 100 - 100 / rapport.value;
  return { state: "value", ratio: rapport.value, waitShare: attente, workShare: 100 - attente };
}

function repere(valeur: number): RepereAttente {
  if (!(valeur > 1)) {
    return { ratio: valeur, inScale: false };
  }
  return { ratio: valeur, inScale: true, share: 100 - 100 / valeur };
}

function seuil(corps: EntreePartsDAttente, code: string): number {
  const s = corps.method.thresholds.find((x) => x.code === code);
  if (s === undefined) {
    throw new Error(`seuil absent : ${code}`);
  }
  return s.value;
}

// Absent (undefined) on a hypothesis 5 answer and on an answer without ratios: no bar.
export function partsDAttente(corps: EntreePartsDAttente): PartsDAttente | undefined {
  if (corps.method.hypothesis !== "h1_first_half" || corps.ratios === undefined) {
    return undefined;
  }
  const insuffisant = corps.verdict === "insufficient_sample";
  const annee = corps.ratios.pooledYear;
  return {
    median: barre(annee?.median, insuffisant),
    p85: barre(annee?.p85, insuffisant),
    markers: {
      refutation: repere(seuil(corps, "h1_lower")),
      confirmation: repere(seuil(corps, "h1_upper")),
      applicable: corps.verdict === "confirmed" || corps.verdict === "refuted" || corps.verdict === "not_settled",
    },
  };
}
