// Player of the synthetic verdict parity cases (mothra-slices D30, task 17.1): a data file of the contract package's test data,
// each case naming a pure function of the verdict service, its input and its expected result. It stops at the first differing
// case and names it, as the player of the cell cases does.
import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";

import {
  attachmentSignal,
  constatsFinaux,
  echantillonSuffisant,
  h1Evaluer,
  h1Verdict,
  h5Evaluer,
  h5Verdict,
  linkColour,
  litLeDebit,
  referenceH5,
  thresholdModifiedAfterReading,
  twoThresholds,
  unplannedWorkExplanation,
  verdictFinal,
} from "./verdict.ts";
import type { ConfigEchantillon, LienId } from "./verdict.ts";

export interface CasVerdict {
  name: string;
  fn: string;
  input: unknown;
  expected: unknown;
}

const FONCTIONS: Record<string, (entree: never) => unknown> = {
  twoThresholds,
  h1Verdict,
  h5Verdict,
  // The same functions with the finding of the verdict (audit #629, A-01), and the one that bars a confirmation.
  h1Evaluer,
  h5Evaluer,
  constatsFinaux,
  attachmentSignal,
  unplannedWorkExplanation,
  verdictFinal,
  thresholdModifiedAfterReading,
  linkColour,
  // Positional functions of the service, played with one input object.
  litLeDebit: (e: { hypothesis: LienId; config?: { h1FirstHalfReadsThroughput?: boolean } }) => litLeDebit(e.hypothesis, e.config),
  echantillonSuffisant: (e: { n: number; statistic: "median" | "p85"; config: ConfigEchantillon }) =>
    echantillonSuffisant(e.n, e.statistic, e.config),
  referenceH5: (e: Parameters<typeof referenceH5>[0]) => referenceH5(e),
};

export function chargerCasVerdict(chemin: string | URL): CasVerdict[] {
  const lu: unknown = JSON.parse(readFileSync(chemin, "utf8"));
  if (!Array.isArray(lu)) {
    throw new Error("fichier de cas de verdict invalide : tableau attendu");
  }
  return lu as CasVerdict[];
}

export function jouerCasVerdict(cas: CasVerdict[]): void {
  for (const c of cas) {
    let ok: boolean;
    try {
      const f = FONCTIONS[c.fn];
      ok = f !== undefined && isDeepStrictEqual(f(c.input as never), c.expected);
    } catch {
      ok = false;
    }
    if (!ok) {
      throw new Error(`cas de parité différent : ${c.name}`);
    }
  }
}
