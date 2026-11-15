// The sheet answers of hypothesis 1 that the tests of the conviction page, and the catalogue, hand to the screen (mothra-demo-habillage D15,
// R-20261031-61): each one is produced by `corpsDepuisVues` of the contract on synthetic view rows, reduced by `reduceToStatistics` for the
// real-data case, never written by hand. One case per display state and the case where the two medians cannot be compared. The rows are
// invented: a generic team name, round figures, a sentinel count. Free component inputs (a state, a share) are not made here (rule 4).
import { corpsDepuisVues, partsDAttente, reduceToStatistics } from "@mothra/contract";
import type { LigneReponse, ReponseVue } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import type { ReponseFiche } from "../src/api/fiche.ts";

export type CasH1 = "confirmed" | "refuted" | "not_settled" | "insufficient_sample" | "masked" | "not_comparable";
export const CAS_H1: readonly CasH1[] = ["confirmed", "refuted", "not_settled", "insufficient_sample", "masked", "not_comparable"];

// The invented team name of the rows is the witness name of the tests: the dashboard answer built from the same rows carries it in its `team`
// field, and no rendered page may show it (R-20261101-121, Q238 (a)). The sheet carries only the opaque identifier derived from it.
export const EQUIPE_SYNTHETIQUE = "Equipe Temoin Zeta";
export const IDENTIFIANT_OPAQUE = identifiantEquipe(EQUIPE_SYNTHETIQUE);

const S = 7919; // sentinel count
const v = (x: number) => ({ state: "value" as const, value: x });
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"] as const;      // the three closed quarters (R-20261114-49)
const SCOPE = scopeFiche({ kind: "team", team: IDENTIFIANT_OPAQUE });

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

interface Annee {
  leadMedian: ReturnType<typeof v> | { state: "masked"; threshold: number };
  cycleMedian: number;
  leadP85: number;
  cycleP85: number;
  effectif: number;
}

function ligne(debut: string | null, debit: number, annee: Annee): LigneReponse {
  return {
    team: EQUIPE_SYNTHETIQUE,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: v(debit),
    items_lt: v(annee.effectif),
    items_ct: v(annee.effectif),
    items_old: v(0), // R-20261106-66 : valait l'effectif (S), donc une taille de H1 nulle ; 0 comme l'équipe sans ancien
    items_without_commitment: v(S),
    lead_median_days: annee.leadMedian,
    lead_p85_days: v(annee.leadP85),
    cycle_median_days: v(annee.cycleMedian),
    cycle_p85_days: v(annee.cycleP85),
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: annee.leadMedian,
    lead_p85_days_excl_old: v(annee.leadP85),
    cycle_median_days_excl_old: v(annee.cycleMedian),
    cycle_p85_days_excl_old: v(annee.cycleP85),
  };
}

// The pooled year of each case: the medians and the P85 that give the ratio, and the number of items behind them.
const ANNEES: Record<CasH1, Annee> = {
  confirmed: { leadMedian: v(40), cycleMedian: 10, leadP85: 80, cycleP85: 20, effectif: S },
  refuted: { leadMedian: v(12), cycleMedian: 10, leadP85: 24, cycleP85: 20, effectif: S },
  not_settled: { leadMedian: v(25), cycleMedian: 10, leadP85: 50, cycleP85: 20, effectif: S },
  insufficient_sample: { leadMedian: v(40), cycleMedian: 10, leadP85: 80, cycleP85: 20, effectif: 6 },
  masked: { leadMedian: { state: "masked", threshold: 5 }, cycleMedian: 10, leadP85: 80, cycleP85: 20, effectif: S },
  not_comparable: { leadMedian: v(8), cycleMedian: 10, leadP85: 16, cycleP85: 20, effectif: S },
};

const TRIMESTRE: Annee = { leadMedian: v(40), cycleMedian: 10, leadP85: 80, cycleP85: 20, effectif: S };

export interface OptionsFicheH1 {
  // `real`: the contract's reduction of the answer (statistics and states only, no count); `synthetic`: the complete answer.
  jeu?: "synthetic" | "real";
  etat?: "draft" | "reviewed" | "published";
  // Whether the effect and the cause are written (a draft may hold neither).
  texte?: boolean;
  // The verdict as the contract computes it. By default the case "confirmed" carries the verdict "confirmed" that its ratios would give: the
  // contract cannot give it to a team sheet (unplanned work is not measurable for a team, D33, and the ban of D20 turns "confirmed" into "not
  // settled"), so the display state is exercised by setting the verdict on those rows, and nothing else of the answer is touched.
  verdictDuContrat?: boolean;
  // The window limit the sheet carries (R-20261114-49, design D8). `figee` (the default): a sheet frozen before the change, carrying
  // `views_last_four_quarters`, so that the tests of the frozen sheets read their former label and note; `neuve`: the code the contract writes today,
  // `views_last_three_closed_quarters`.
  limite?: "figee" | "neuve";
}

export function ficheH1(cas: CasH1, options: OptionsFicheH1 = {}): ReponseFiche {
  const { jeu = "synthetic", etat = "published", texte = true, verdictDuContrat = false, limite = "figee" } = options;
  const parts = (n: number) => reponse("x", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: v(S), share_percent: v(n) })));
  const corpsNeuf = corpsDepuisVues({
    chart: "lead_cycle_h1",
    scope: SCOPE,
    dataDate: "2026-10-05",
    premiereLecture: null,
    historique: SEUILS.map(([code, value]) => ({ code, value, setOn: "2026-10-27" })),
    vues: {
      leadCycle: reponse("v_team_lead_time_throughput", [...DEBUTS.map((d) => ligne(d, S, TRIMESTRE)), ligne(null, S * 3, ANNEES[cas])]),
      sansEquipe: parts(10),
      nonPlanifie: parts(12),
      fileEnAttente: reponse("v_team_ready_queue", [{ team: EQUIPE_SYNTHETIQUE, quarter_start: DEBUTS[2], ready: v(6007) }]),
      bloque: reponse("v_team_blocked_share", [{ team: EQUIPE_SYNTHETIQUE, quarter_start: DEBUTS[2], blocked_n: v(S), blocked: v(6007), share_percent: v(30) }]),
    },
    identifiantEquipe,
    empreinte: "f".repeat(64),
  });
  // A frozen sheet: the former window limit in place of the new one, nothing else of the answer touched (design D8).
  const corps =
    limite === "neuve"
      ? corpsNeuf
      : { ...corpsNeuf, method: { ...corpsNeuf.method, limits: corpsNeuf.method.limits.map((l) => (l === "views_last_three_closed_quarters" ? ("views_last_four_quarters" as const) : l)) } };
  const confirme = cas === "confirmed" && !verdictDuContrat;
  const avecJeu = { ...corps, dataset: jeu, ...(confirme ? { verdict: "confirmed" as const, verdictReasons: [], verdictFindings: ["h1_above_upper" as const] } : {}) };
  const base = jeu === "real" ? reduceToStatistics(avecJeu) : avecJeu;
  // The bars and the markers of the share of waiting, as the server serves them (`waitShares`, D3b, D15): made by the contract's function
  // on the answer, full or reduced, never written by hand.
  const attente = partsDAttente(base);
  return {
    ...base,
    ...(attente === undefined ? {} : { waitShares: attente }),
    id: "fiche-h1-1",
    state: etat,
    ...(etat === "published" ? { publishedOn: "2026-11-02" } : {}),
    managementQuestion: "predictability",
    ...(texte ? { effect: { text: "Invented effect.", lang: "en" as const }, cause: { text: "Invented cause.", lang: "en" as const } } : {}),
  } as ReponseFiche;
}
