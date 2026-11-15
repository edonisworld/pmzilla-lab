// The sheet answers of hypothesis 5 that the tests of the conviction page, and the catalogue, hand to the screen (mothra-demo-habillage D15,
// R-20261031-61): each one is produced by `corpsDepuisVues` of the contract on synthetic view rows, reduced by `reduceToStatistics` for the
// real-data case, never written by hand. One case per display state (the five states of D5), then the cases the page must tell apart: a
// masked throughput (reason `throughput_masked`), a quarter whose P85 is an insufficient sample, a quarter whose P85 is masked. The rows are
// invented: a generic team name, round figures, a sentinel count. Free component inputs (a state, a position) are not made here (rule 4).
import { corpsDepuisVues, reduceToStatistics } from "@mothra/contract";
import type { LigneReponse, ReponseVue } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import type { ReponseFiche } from "../src/api/fiche.ts";
import { EQUIPE_SYNTHETIQUE } from "./fiches-h1.ts";

export type CasH5 = "confirmed" | "refuted" | "not_settled" | "insufficient_sample" | "masked" | "throughput_masked" | "p85_insufficient" | "p85_masked";
export const CAS_H5: readonly CasH5[] = ["confirmed", "refuted", "not_settled", "insufficient_sample", "masked", "throughput_masked", "p85_insufficient", "p85_masked"];

// The display state each case must give (the fixture is checked, not trusted) and the verdict of the service it comes from.
export const ATTENDU_H5: Record<CasH5, { verdict: string; etat: string }> = {
  confirmed: { verdict: "confirmed", etat: "confirmed" },
  refuted: { verdict: "refuted", etat: "refuted" },
  not_settled: { verdict: "not_settled", etat: "not_settled" },
  insufficient_sample: { verdict: "insufficient_sample", etat: "insufficient_sample" },
  masked: { verdict: "insufficient_sample", etat: "masked" },
  // R-20261114-83: with three closed quarters, a judged quarter that is incomplete (masked throughput, insufficient or masked P85) leaves two complete
  // quarters: no reference for hypothesis 5, so the verdict is "insufficient_sample" (before: four quarters, three complete ones, "not_settled").
  throughput_masked: { verdict: "insufficient_sample", etat: "insufficient_sample" },
  p85_insufficient: { verdict: "insufficient_sample", etat: "insufficient_sample" },
  p85_masked: { verdict: "insufficient_sample", etat: "insufficient_sample" },
};

const S = 7919; // sentinel count
const v = (x: number) => ({ state: "value" as const, value: x });
const masquee = { state: "masked" as const, threshold: 5 };
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe(EQUIPE_SYNTHETIQUE) });

const SEUILS: Array<[string, number]> = [
  ["h5_band", 0.2],
  ["h5_double_band", 0.4],
  ["h5_run_rises", 2],
  ["h5_run_min_cumulative_rise", 0.1],
  ["h5_floor", 0.8],
  ["h5_low_floor", 0.6],
  ["h1_lower", 1.5],
  ["h1_upper", 3],
  ["attachment_threshold_points", 10],
  ["sample_median_min_items", 10],
  ["sample_p85_min_items", 20],
];

function reponse(view: string, rows: LigneReponse[]): ReponseVue {
  return { view, threshold: 5, columns: [], rows, sources: ["flow"] };
}

// A quarter of the rows: its throughput, its median and P85 cycle time (a value or the masked cell), and the number of items behind them.
interface Trimestre {
  debit: number | "masked";
  mediane: number | "masked";
  p85: number | "masked";
  effectif: number;
}

const cellule = (x: number | "masked") => (x === "masked" ? masquee : v(x));

function ligne(debut: string | null, t: Trimestre): LigneReponse {
  return {
    team: EQUIPE_SYNTHETIQUE,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: cellule(t.debit),
    items_lt: v(t.effectif),
    items_ct: v(t.effectif),
    items_old: v(S),
    items_without_commitment: v(S),
    lead_median_days: v(40),
    lead_p85_days: v(80),
    cycle_median_days: cellule(t.mediane),
    cycle_p85_days: cellule(t.p85),
  };
}

const BASE: Trimestre = { debit: 100, mediane: 10, p85: 20, effectif: S };

// The three closed quarters of the window (the oldest first, the judged quarter last); `null` is a quarter with no row (the team did not exist yet).
// R-20261114-49: the reference is the mean of the three quarters, the judged one included. By hand: the judged throughput of "refuted" goes from 50 (mean of
// 100, 100, 100, 50 = 87.5, ratio 0.571) to 40 (mean of 100, 100, 40 = 80, ratio 0.5, under the low floor 0.6; 50 gives 0.6, which is not under it); that of
// "not_settled" stays 70 (mean of 100, 100, 70 = 90, ratio 0.778, under the floor 0.8 and over the low floor 0.6).
const TRIMESTRES: Record<CasH5, ReadonlyArray<Trimestre | null>> = {
  // Every quarter equals the reference: in the band, at the floor.
  confirmed: [BASE, BASE, BASE],
  // The judged throughput is under the low floor (0.6 of the reference).
  refuted: [BASE, BASE, { ...BASE, debit: 40 }],
  // The judged throughput is under the floor (0.8) and over the low floor.
  not_settled: [BASE, BASE, { ...BASE, debit: 70 }],
  // Fewer than three complete quarters: no reference, no verdict.
  insufficient_sample: [null, BASE, BASE],
  // The same, and the median cycle time of the judged quarter is masked.
  masked: [null, BASE, { ...BASE, mediane: "masked" }],
  // The judged throughput is masked: with three quarters only two complete ones remain, so no H5 reference and "insufficient sample" (D14).
  throughput_masked: [BASE, BASE, { ...BASE, debit: "masked" }],
  // The judged quarter holds 15 items: enough for a median (10), not for a P85 (20).
  p85_insufficient: [BASE, BASE, { ...BASE, effectif: 15 }],
  // The P85 of the judged quarter is a masked cell.
  p85_masked: [BASE, BASE, { ...BASE, p85: "masked" }],
};

export interface OptionsFicheH5 {
  // `real`: the contract's reduction of the answer (statistics and states only, no count); `synthetic`: the complete answer.
  jeu?: "synthetic" | "real";
  etat?: "draft" | "reviewed" | "published";
  // Whether the effect and the cause are written (a draft may hold neither).
  texte?: boolean;
  // The verdict as the contract computes it. By default the case "confirmed" carries the verdict "confirmed" that its figures would give: the
  // contract cannot give it to a team sheet (unplanned work is not measurable for a team, D33, and the ban of D20 turns "confirmed" into "not
  // settled"), so the display state is exercised by setting the verdict on those rows, and nothing else of the answer is touched.
  verdictDuContrat?: boolean;
}

export function ficheH5(cas: CasH5, options: OptionsFicheH5 = {}): ReponseFiche {
  const { jeu = "synthetic", etat = "published", texte = true, verdictDuContrat = false } = options;
  const parts = (n: number) => reponse("x", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: v(S), share_percent: v(n) })));
  const lignesTrimestre = TRIMESTRES[cas].flatMap((t, rang) => (t === null ? [] : [ligne(DEBUTS[rang], t)]));
  const corps = corpsDepuisVues({
    chart: "lead_cycle_h5",
    scope: SCOPE,
    dataDate: "2026-10-05",
    premiereLecture: null,
    historique: SEUILS.map(([code, value]) => ({ code, value, setOn: "2026-10-27" })),
    vues: {
      leadCycle: reponse("v_team_lead_time_throughput", [...lignesTrimestre, ligne(null, { ...BASE, debit: S * 3 })]),
      sansEquipe: parts(10),
      nonPlanifie: parts(12),
      fileEnAttente: reponse("v_team_ready_queue", [{ team: EQUIPE_SYNTHETIQUE, quarter_start: DEBUTS[2], ready: v(6007) }]),
      bloque: reponse("v_team_blocked_share", [{ team: EQUIPE_SYNTHETIQUE, quarter_start: DEBUTS[2], blocked_n: v(S), blocked: v(6007), share_percent: v(30) }]),
    },
    identifiantEquipe,
    empreinte: "f".repeat(64),
  });
  // HAND-WRITTEN CASE, kept on purpose (R-20261103-24 Q5, D20 and D33): the "confirmed" verdict is set by hand on rows the contract gives "not
  // settled" for a team sheet; it is the one exception to "never written by hand" at the head of this file, and the test that documents it is unchanged.
  const confirme = cas === "confirmed" && !verdictDuContrat;
  const avecJeu = { ...corps, dataset: jeu, ...(confirme ? { verdict: "confirmed" as const, verdictReasons: [], verdictFindings: ["h5_within_band" as const] } : {}) };
  const base = jeu === "real" ? reduceToStatistics(avecJeu) : avecJeu;
  // No `waitShares`: the bars measure hypothesis 1 only (D3b), the service layer adds none to a hypothesis 5 answer.
  return {
    ...base,
    id: "fiche-h5-1",
    state: etat,
    ...(etat === "published" ? { publishedOn: "2026-11-02" } : {}),
    managementQuestion: "predictability",
    ...(texte ? { effect: { text: "Invented effect.", lang: "en" as const }, cause: { text: "Invented cause.", lang: "en" as const } } : {}),
  } as ReponseFiche;
}
