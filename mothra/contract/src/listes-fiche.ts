// Replaces: nothing (new lists). Removal condition: permanent, they are the closed lists of D29 for the computed body.
// The closed lists of the computed body of a sheet (mothra-slices D29, D30, task 18.4). Codes only: the front translates them, the server
// refuses anything outside them. Each list is the single source of its kind; a test (contract/test/corps-fiche.test.ts) plays every code.
// None of them holds a threshold value: the adopted values come from the threshold history (D21), never from this package.
import type { ConstatDeVerdict, EtatCouverture, Explication, LienId, MotifH1, MotifH5, MotifSignal, PositionDebit, VerdictOuEchantillon } from "./verdict.ts";

// The charts a sheet can be made from (author's decision R-20261030-58, Q3): a chart carries one hypothesis, so the lead time against
// cycle time dashboard gives two sheet kinds, one per verdict. Any other chart is refused at creation (400 INVALID_REQUEST, D29).
export const GRAPHIQUES_DE_FICHE = ["lead_cycle_h5", "lead_cycle_h1"] as const;
export type GraphiqueDeFiche = (typeof GRAPHIQUES_DE_FICHE)[number];

// The panel codes, hypotheses and mentions of the product-scope dashboard (task 37.2), re-exported so that the front takes them through this
// browser-safe subpath (it admits no other); their source is `codes-panneaux.ts`, which imports nothing.
export { CODES_PANNEAUX, HYPOTHESES_PANNEAUX, MENTIONS_PANNEAUX } from "./codes-panneaux.ts";
export type { CodePanneau } from "./codes-panneaux.ts";

export function estGraphiqueDeFiche(valeur: string): valeur is GraphiqueDeFiche {
  return (GRAPHIQUES_DE_FICHE as readonly string[]).includes(valeur);
}

// The codes of the threshold history that the sheet reads (author's decision R-20261030-58, Q5). A code missing from the history gives
// no verdict (THRESHOLDS_NOT_SET); the codes of the capacity and dependencies explanations (`capacity_ready_queue_max`,
// `dependencies_blocked_share_max`) are not read yet: until the author freezes them those explanations are "not ruled out" (Q2).
export const CODES_SEUILS = {
  h5: ["h5_band", "h5_double_band", "h5_run_rises", "h5_run_min_cumulative_rise", "h5_floor", "h5_low_floor"],
  h1: ["h1_lower", "h1_upper"],
  attachment: ["attachment_threshold_points"],
  sample: ["sample_median_min_items", "sample_p85_min_items"],
} as const;

export function codesRequis(graphique: GraphiqueDeFiche): string[] {
  const propres = graphique === "lead_cycle_h5" ? CODES_SEUILS.h5 : CODES_SEUILS.h1;
  const rattachement = graphique === "lead_cycle_h5" ? CODES_SEUILS.attachment : [];
  return [...propres, ...rattachement, ...CODES_SEUILS.sample];
}

// The limits a sheet states on its method face (codes, translated by the front).
export const CODES_LIMITES = [
  "no_per_team_unplanned_measure", // a team sheet: defects carry no team, the unplanned share is a product measure
  "capacity_dependencies_no_adopted_threshold", // the Ready queue and the blocked share are measured, no adopted threshold rules them out
  "views_last_four_quarters", // FROZEN SHEETS ONLY (R-20261114-49, design D6, D8): the views held the last four closed quarters; never written on a new sheet. Replaces: nothing. Removal: permanent (frozen sheets are kept beyond one year)
  "views_last_three_closed_quarters", // the views hold the last three closed quarters as of the reading, not as of the data date (every new sheet)
  "attachment_signal_product_level", // the share of tasks without a team is a product measure, attributed to no team
  "throughput_own_past_only", // D33 point 2: the throughput of a team is compared with its own past, never with other teams
  "reduced_form", // D34 point 2: on real data the sheet holds statistics and states only, no counts (added by reduceToStatistics)
] as const;
export type CodeLimite = (typeof CODES_LIMITES)[number];

// The position codes of a quarter's throughput and the coverage states of the reduced form (D29, D34), and the dataset code of every
// answer. Source of the types: verdict.ts (a type test keeps both in step); the front takes the lists from here to label them.
export const POSITIONS_DEBIT = ["throughput_within_band", "throughput_under_floor", "throughput_under_low_floor", "masked"] as const satisfies readonly PositionDebit[];
export const ETATS_COUVERTURE = ["coverage_sufficient", "coverage_insufficient", "coverage_masked"] as const satisfies readonly EtatCouverture[];
export const CODES_JEU_DE_DONNEES = ["synthetic", "real"] as const;
export type CodeJeuDeDonnees = (typeof CODES_JEU_DE_DONNEES)[number];

export const METHODES = ["lead_time_against_cycle_time"] as const;
export type CodeMethode = (typeof METHODES)[number];

// The reasons of the capacity and dependencies explanations (Q2): a measured explanation is not ruled out for lack of an adopted
// threshold, a masked or absent one is not measurable.
export const RAISONS_EXPLICATION = ["no_adopted_threshold", "masked", "no_data"] as const;

// The measure code of a masked cell or an insufficient sample of a body: `<column>@<quarter start>` or `<column>@pooled_year`. One
// builder and one reader, so that the front (task 19.3) never parses the text by hand.
export const ANNEE_GROUPEE = "pooled_year";

export function codeMesure(colonne: string, quand: string): string {
  return `${colonne}@${quand}`;
}

export function lireCodeMesure(code: string): { column: string; when: string } | null {
  const m = /^([a-z0-9_]+)@(\d{4}-\d{2}-\d{2}|pooled_year)$/.exec(code);
  return m === null ? null : { column: m[1], when: m[2] };
}

// The roles written on a sheet are role codes, never names.
export const ROLE_AUTEUR = "agile_lead";

// ---- lists the front reads (task 19.3, review B1) ----------------------------------------------------------------------------------
// This module is the browser-safe subpath `@mothra/contract/listes-fiche`: it imports nothing at run time (the imports above the lists are
// types, erased), so the front can take these lists without the package entry's node-only loaders. A static test checks it.
// Replaces: the lists the front copied (GRAPHIQUES_FICHE, EXPLICATIONS, LIENS, VERDICTS_AFFICHES). Removal condition: permanent.

// The four management questions of design D19 (the table of that design): the codes of the column `mothra.sheets.management_question`.
export const QUESTIONS_DE_DIRECTION = ["scope_growth", "scope_reachability", "predictability", "next_version_quality"] as const;
export type QuestionDeDirection = (typeof QUESTIONS_DE_DIRECTION)[number];

export type CodeSeuil = (typeof CODES_SEUILS)[keyof typeof CODES_SEUILS][number];

// The columns of the measure codes `<column>@<quarter start>` that the body notes (masked cells, insufficient samples).
export const COLONNES_MESURE = [
  "unplanned_share",
  "ready",
  "blocked_share",
  "cycle_median_days",
  "cycle_p85_days",
  "throughput",
  "tasks_without_team_share",
  "lead_median_days",
  "lead_p85_days",
  "median_ratio",
  "p85_ratio",
] as const;
export type ColonneMesure = (typeof COLONNES_MESURE)[number];

export const EXPLICATIONS_DE_FICHE = ["unplanned_work", "capacity", "dependencies"] as const satisfies readonly Explication["name"][];

export const LIENS_DE_FICHE = ["h1_first_half", "h1_second_half", "h2", "h3", "h4", "h5"] as const satisfies readonly LienId[];

export const VERDICTS_DE_FICHE = ["confirmed", "refuted", "not_settled", "insufficient_sample"] as const satisfies readonly VerdictOuEchantillon[];

// The reason codes of a body: the reasons of the competing explanations (D33 and Q2), of hypothesis 1, of hypothesis 5 and of the signal.
export const MOTIFS_DE_FICHE = [
  "defects_without_team",
  ...RAISONS_EXPLICATION,
  "median_masked",
  "median_insufficient_sample",
  "p85_masked",
  "p85_insufficient_sample",
  "throughput_masked",
  "tasks_without_team_share_masked",
] as const satisfies readonly (MotifH1 | MotifH5 | MotifSignal | "defects_without_team" | (typeof RAISONS_EXPLICATION)[number])[];
export type MotifDeFiche = (typeof MOTIFS_DE_FICHE)[number];

// The findings of a verdict (audit #629, A-01, Q6): the codes of the sentence under the badge that says why the verdict is what it is. The
// source of the type is verdict.ts (the functions that give them); the front takes the list from here to label them.
// Replaces: nothing. Removal: permanent while the badge tells its reason.
export const CONSTATS_DE_VERDICT = [
  "h1_above_upper",
  "h1_median_under_lower",
  "h1_median_in_grey_zone",
  "h1_p85_not_above_upper",
  "h1_p85_not_readable",
  "h5_within_band",
  "h5_double_band",
  "h5_rising_run",
  "h5_under_low_floor",
  "h5_out_of_band",
  "h5_under_floor",
  "confirmation_barred",
] as const satisfies readonly ConstatDeVerdict[];
export type CodeConstatDeVerdict = (typeof CONSTATS_DE_VERDICT)[number];
