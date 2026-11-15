// Verdict service of Mothra (mothra-slices D30, task 17.1): pure functions, no I/O, no clock. Routes and front call them; no verdict,
// cap or colour is computed anywhere else. Every threshold and rule parameter comes from the caller (the adopted thresholds, D21):
// this module holds no starting value. The starting values of the synthetic runs live with the tests (test/depart.ts).

export type Verdict = "refuted" | "not_settled" | "confirmed";
export type VerdictOuEchantillon = Verdict | "insufficient_sample";
export type EtatExplication = "ruled_out" | "not_ruled_out" | "not_measurable";

// Links of the home chain. The first half of hypothesis 1 and hypothesis 5 are computed in slice 1; the second half of hypothesis 1
// stays "not tested" until its slice; hypothesis 4 never gets a verdict.
export type LienId = "h1_first_half" | "h1_second_half" | "h2" | "h3" | "h4" | "h5";

// Relative or percentage-point gaps are compared after rounding, so that a gap equal to its threshold is never read above it.
const arrondi = (x: number): number => Math.round(x * 1e9) / 1e9;

// Two thresholds and a grey zone: under the lower one refuted, from the lower to the upper one (both included) not settled, above
// the upper one confirmed. Measure and thresholds are rounded as everywhere else in the service.
export function twoThresholds(entree: { measure: number; lower: number; upper: number }): Verdict {
  const measure = arrondi(entree.measure);
  const lower = arrondi(entree.lower);
  const upper = arrondi(entree.upper);
  if (!(lower < upper)) {
    throw new RangeError("seuils : le seuil bas doit être inférieur au seuil haut");
  }
  if (measure < lower) {
    return "refuted";
  }
  return measure > upper ? "confirmed" : "not_settled";
}

// Reliability of a statistic (D22): a median or a P85 computed on fewer items than its size is "insufficient sample".
export interface ConfigEchantillon {
  medianMinItems: number;
  p85MinItems: number;
}

export function echantillonSuffisant(n: number, statistic: "median" | "p85", config: ConfigEchantillon): boolean {
  return n >= (statistic === "median" ? config.medianMinItems : config.p85MinItems);
}

// Whether the verdict of a link reads throughput (D20, D33): hypothesis 5 does; the first half of hypothesis 1 does not unless the
// configuration says so (open question of the review of slice 1); no other link does.
export function litLeDebit(hypothesis: LienId, config?: { h1FirstHalfReadsThroughput?: boolean }): boolean {
  if (hypothesis === "h5") {
    return true;
  }
  return hypothesis === "h1_first_half" && config?.h1FirstHalfReadsThroughput === true;
}

export type MotifH1 = "median_masked" | "median_insufficient_sample" | "p85_masked" | "p85_insufficient_sample";

// The finding of a verdict (audit #629, A-01, Q6): the reason why the verdict is what it is, as a code the sheet tells in one sentence under
// the badge. It is given by the function that decides the verdict, in the same branch, never by a second computation. A verdict that is an
// insufficient sample has none: its sentence is the page's own. Replaces: nothing. Removal: permanent while the badge tells its reason.
export type ConstatH1 = "h1_median_under_lower" | "h1_median_in_grey_zone" | "h1_p85_not_above_upper" | "h1_p85_not_readable" | "h1_above_upper";
export type ConstatH5 = "h5_double_band" | "h5_rising_run" | "h5_under_low_floor" | "h5_out_of_band" | "h5_under_floor" | "h5_within_band";
// A confirmation that the figures give and a competing explanation forbids (the ban of D20): said in place of the finding of the figures.
export type ConstatDeVerdict = ConstatH1 | ConstatH5 | "confirmation_barred";

interface EntreeH1 {
  medianRatio: number | null;
  p85Ratio: number | null;
  lower: number;
  upper: number;
  medianSampleSufficient: boolean;
  p85SampleSufficient: boolean;
}

// Hypothesis 1, first half, with the finding of its verdict. "Confirmed" only when the P85 ratio points the same way as the median ratio,
// and never when the P85 is masked or the pooled year is under the P85 reliability size (cap at "not settled", D22, with its reason). A
// masked median ratio and an insufficient median sample are both out of the verdict, with distinct reasons.
export function h1Evaluer(entree: EntreeH1): { verdict: VerdictOuEchantillon; reasons: MotifH1[]; findings: ConstatH1[] } {
  const { medianRatio, p85Ratio, lower, upper } = entree;
  if (medianRatio === null) {
    return { verdict: "insufficient_sample", reasons: ["median_masked"], findings: [] };
  }
  if (!entree.medianSampleSufficient) {
    return { verdict: "insufficient_sample", reasons: ["median_insufficient_sample"], findings: [] };
  }
  const surMediane = twoThresholds({ measure: medianRatio, lower, upper });
  if (surMediane !== "confirmed") {
    return { verdict: surMediane, reasons: [], findings: [surMediane === "refuted" ? "h1_median_under_lower" : "h1_median_in_grey_zone"] };
  }
  if (p85Ratio === null) {
    return { verdict: "not_settled", reasons: ["p85_masked"], findings: ["h1_p85_not_readable"] };
  }
  if (!entree.p85SampleSufficient) {
    return { verdict: "not_settled", reasons: ["p85_insufficient_sample"], findings: ["h1_p85_not_readable"] };
  }
  const p85Confirme = twoThresholds({ measure: p85Ratio, lower, upper }) === "confirmed";
  return p85Confirme ? { verdict: "confirmed", reasons: [], findings: ["h1_above_upper"] } : { verdict: "not_settled", reasons: [], findings: ["h1_p85_not_above_upper"] };
}

// Hypothesis 1, first half: the verdict and its reasons (the finding is `h1Evaluer`'s).
export function h1Verdict(entree: EntreeH1): { verdict: VerdictOuEchantillon; reasons: MotifH1[] } {
  const { verdict, reasons } = h1Evaluer(entree);
  return { verdict, reasons };
}

// A quarter of hypothesis 5. The two sufficiency flags are separate: an insufficient P85 leaves only the P85 out of the band
// comparison. Throughput is a count: null only when the count is masked.
export interface TrimestreH5 {
  median: number;
  p85: number;
  throughput: number | null;
  medianSufficient: boolean;
  p85Sufficient: boolean;
}

// Rising series (author's decision of 2026-10-27): `runRises` consecutive rises of the median (each quarter above the previous one;
// 2 rises span 3 quarters) AND a cumulative rise of at least `runMinCumulativeRise` (0.10 = 10 %: the last median at least 1.10 times
// the first of the series). A quarter with an insufficient median sample breaks the series.
export interface ConfigH5 {
  band: number;
  doubleBand: number;
  runRises: number;
  runMinCumulativeRise: number;
  floor: number;
  lowFloor: number;
}

export type MotifH5 = "throughput_masked";

export interface ExclusionsH5 {
  median: number[];
  p85: number[];
  throughput: number[];
}

// Hypothesis 5: each quarter against the team's reference (given by the caller, see referenceH5). Refuted: two quarters out of the
// double band (median or P85), a rising run of the median (runRises consecutive rises, even inside the band) or a quarter under the
// low floor. Confirmed: every compared quarter in the band, no rising run, every quarter at or above the floor, and at least one
// band comparison made. Else not settled. Throughput is a count: it always goes through the floors, whatever the median and P85
// samples; only a masked count leaves it out. A quarter whose median sample is insufficient is out of the median comparison and breaks
// a run; one whose P85 sample is insufficient is out of the P85 comparison only; each exclusion is listed apart. With nothing left to
// compare, or with no reference (null), the verdict is "insufficient_sample", the floors included; with a reference but no band
// comparison possible and no throughput refutation it cannot confirm. `h5Evaluer` also gives the findings of the verdict (A-01): every cause
// of a refutation, in the order double band, rising run, low floor; the conditions of a "not settled" (out of the band, under the floor); the
// band for a confirmation; none for an insufficient sample or for the masked throughput, whose reason is its own.
export function h5Verdict(entree: {
  quarters: TrimestreH5[];
  reference: { median: number; p85: number; throughput: number } | null;
  config: ConfigH5;
}): { verdict: VerdictOuEchantillon; excluded: ExclusionsH5; reasons: MotifH5[] } {
  const { verdict, excluded, reasons } = h5Evaluer(entree);
  return { verdict, excluded, reasons };
}

export function h5Evaluer(entree: {
  quarters: TrimestreH5[];
  reference: { median: number; p85: number; throughput: number } | null;
  config: ConfigH5;
}): { verdict: VerdictOuEchantillon; excluded: ExclusionsH5; reasons: MotifH5[]; findings: ConstatH5[] } {
  const cfg = entree.config;
  if (
    cfg === undefined ||
    cfg === null ||
    !(["band", "doubleBand", "runRises", "runMinCumulativeRise", "floor", "lowFloor"] as const).every((k) => typeof cfg[k] === "number")
  ) {
    throw new Error("configuration de l'hypothèse 5 obligatoire et complète");
  }
  const ref = entree.reference;
  const exclus: ExclusionsH5 = { median: [], p85: [], throughput: [] };
  entree.quarters.forEach((q, i) => {
    if (!q.medianSufficient) {
      exclus.median.push(i);
    }
    if (!q.p85Sufficient) {
      exclus.p85.push(i);
    }
    if (q.throughput === null) {
      exclus.throughput.push(i);
    }
  });
  // No reference (under three full quarters, see referenceH5): nothing to compare with, so no band, no floor and no verdict.
  if (ref === null) {
    return { verdict: "insufficient_sample", excluded: exclus, reasons: [], findings: [] };
  }
  const rienAComparer = entree.quarters.every((q) => !q.medianSufficient && !q.p85Sufficient && q.throughput === null);
  if (rienAComparer) {
    return { verdict: "insufficient_sample", excluded: exclus, reasons: [], findings: [] };
  }
  const ecart = (x: number, r: number): number => arrondi(Math.abs(x - r) / r);
  // A reference of 0 gives no band to compare with (a division by zero reads as NaN, and a NaN is never out of the band, so it would confirm): the
  // comparison is left out and the verdict cannot be "confirmed" (audit #629, H-06). Replaces: nothing. Removal: permanent while the band is relative.
  let referenceNulle = false;
  let comparaisons = 0;
  let horsDoubleBande = 0;
  let toutDansLaBande = true;
  let sousPlancherBas = false;
  let sousPlancher = false;
  let serie: number[] = [];
  let serieAtteinte = false;
  for (const q of entree.quarters) {
    const ecarts: number[] = [];
    if (q.medianSufficient) {
      if (ref.median === 0) referenceNulle = true;
      else ecarts.push(ecart(q.median, ref.median));
    }
    if (q.p85Sufficient) {
      if (ref.p85 === 0) referenceNulle = true;
      else ecarts.push(ecart(q.p85, ref.p85));
    }
    if (ecarts.length > 0) {
      comparaisons += 1;
      const e = Math.max(...ecarts);
      if (e > cfg.doubleBand) {
        horsDoubleBande += 1;
      }
      if (e > cfg.band) {
        toutDansLaBande = false;
      }
    }
    if (q.throughput !== null) {
      const rapport = rapportDebit(q.throughput, ref.throughput);
      if (rapport < cfg.lowFloor) {
        sousPlancherBas = true;
      }
      if (rapport < cfg.floor) {
        sousPlancher = true;
      }
    }
    if (!q.medianSufficient) {
      serie = [];
      continue;
    }
    serie = serie.length > 0 && q.median > serie[serie.length - 1] ? [...serie, q.median] : [q.median];
    if (serie.length - 1 >= cfg.runRises) {
      const depart = serie[serie.length - 1 - cfg.runRises];
      if (arrondi(q.median / depart) >= arrondi(1 + cfg.runMinCumulativeRise)) {
        serieAtteinte = true;
      }
    }
  }
  if (horsDoubleBande >= 2 || serieAtteinte || sousPlancherBas) {
    const causes: ConstatH5[] = [];
    if (horsDoubleBande >= 2) causes.push("h5_double_band");
    if (serieAtteinte) causes.push("h5_rising_run");
    if (sousPlancherBas) causes.push("h5_under_low_floor");
    return { verdict: "refuted", excluded: exclus, reasons: [], findings: causes };
  }
  if (referenceNulle) {
    // H-06 (S3) after A-01 (F1): no band to compare against, so no finding of its own; the sheet shows the verdict without a finding phrase.
    return { verdict: "not_settled", excluded: exclus, reasons: [], findings: [] };
  }
  if (comparaisons === 0) {
    return sousPlancher
      ? { verdict: "not_settled", excluded: exclus, reasons: [], findings: ["h5_under_floor"] }
      : { verdict: "insufficient_sample", excluded: exclus, reasons: [], findings: [] };
  }
  if (toutDansLaBande && !sousPlancher) {
    // A masked throughput cannot be checked against the floors: the data that would confirm give "not settled" with its reason.
    if (exclus.throughput.length > 0) {
      return { verdict: "not_settled", excluded: exclus, reasons: ["throughput_masked"], findings: [] };
    }
    return { verdict: "confirmed", excluded: exclus, reasons: [], findings: ["h5_within_band"] };
  }
  const conditions: ConstatH5[] = [];
  if (!toutDansLaBande) conditions.push("h5_out_of_band");
  if (sousPlancher) conditions.push("h5_under_floor");
  return { verdict: "not_settled", excluded: exclus, reasons: [], findings: conditions };
}

// The findings of the verdict the sheet gives (A-01): those of the function that decided the raw verdict, except when the ban of D20 turned a
// confirmation into "not settled": then the one finding is that the confirmation is barred. The raw verdict is the function's, the final one
// is `verdictFinal`'s; nothing is recomputed here.
export function constatsFinaux(entree: { raw: VerdictOuEchantillon; findings: ConstatDeVerdict[]; final: VerdictOuEchantillon }): ConstatDeVerdict[] {
  if (entree.raw === "confirmed" && entree.final !== "confirmed") {
    return ["confirmation_barred"];
  }
  return entree.findings;
}

// The ratio of a quarter's throughput to the reference, rounded: the one comparison both h5Verdict and throughputPositions make, so a
// position never contradicts the verdict (D34).
function rapportDebit(debit: number, reference: number): number {
  return arrondi(debit / reference);
}

// Position of a quarter's throughput against the floors (D34, D29): a code, never a count nor a percentage.
export type PositionDebit = "throughput_within_band" | "throughput_under_floor" | "throughput_under_low_floor" | "masked";

// Task 19.5: the position of each quarter (judged and reference) against the reference throughput. A masked throughput (null) gives
// `masked`, never an estimate. With no reference (under three full quarters, Q11 (a) of R-20261031-01) there is no position at all: the
// verdict is "insufficient sample" alone. The comparison is that of h5Verdict (at the floor: within the band; at the low floor: under
// the floor, not under the low floor).
export function throughputPositions(entree: {
  quarters: Array<{ quarter: string; throughput: number | null }>;
  reference: number | null;
  floor: number;
  lowFloor: number;
}): Array<{ quarter: string; position: PositionDebit }> {
  const { reference } = entree;
  if (reference === null) {
    return [];
  }
  return entree.quarters.map((q) => {
    if (q.throughput === null) {
      return { quarter: q.quarter, position: "masked" as const };
    }
    const rapport = rapportDebit(q.throughput, reference);
    const position: PositionDebit =
      rapport < entree.lowFloor ? "throughput_under_low_floor" : rapport < entree.floor ? "throughput_under_floor" : "throughput_within_band";
    return { quarter: q.quarter, position };
  });
}

export type EtatCouverture = "coverage_sufficient" | "coverage_insufficient" | "coverage_masked";

// Task 19.5: the coverage state of the reduced method face (D34): the coverage cell against the P85 reliability size of D22. No new threshold.
export function coverageState(cellule: { state: "value"; value: number } | { state: "masked"; threshold?: number }, p85MinItems: number): EtatCouverture {
  if (cellule.state === "masked") {
    return "coverage_masked";
  }
  return cellule.value >= p85MinItems ? "coverage_sufficient" : "coverage_insufficient";
}

// Reference of hypothesis 5 (design D14 of flow-three-closed-quarters, R-20261114-83): the caller gives the full quarters of the window, which holds
// three closed quarters at most; the reference is the mean of those three, the judged quarter included (the last one given). Fewer than three full
// quarters give no reference (null): h5Verdict then reads "insufficient_sample", with no two-quarter rule. `slice(-4)` is kept as it was: with a window
// of three it never cuts anything, and a pure-function case of the shared file `test-data/cas-verdict.json` (five quarters given, the last four taken)
// plays it, a case outside the list of design D10 that this change does not touch.
// Replaces: "the mean of the available ones among the last four" (annex of 2026-10-27, mothra-slices D22). Removal: permanent while the views show three
// closed quarters; `slice(-4)` goes, with that shared case, when a change of the verdict contract is decided by the author (mothra-slices D21).
export function referenceH5(
  quarters: Array<{ median: number; p85: number; throughput: number }>,
): { median: number; p85: number; throughput: number } | null {
  if (quarters.length < 3) {
    return null;
  }
  const derniers = quarters.slice(-4);
  const moyenne = (cle: "median" | "p85" | "throughput"): number => derniers.reduce((s, q) => s + q[cle], 0) / derniers.length;
  return { median: moyenne("median"), p85: moyenne("p85"), throughput: moyenne("throughput") };
}

// Signal on the product share of done tasks without a team (D33, Q2). Shares are percentages (0 to 100). Raised when the judged
// quarter's share differs from the mean of the reference quarters by MORE than the threshold in points; a gap equal to it raises
// nothing. Author's decision of 2026-10-27: a masked share raises no signal and does not forbid "confirmed"; the result carries
// the reason `tasks_without_team_share_masked` for the sheet. Masked reference shares are left out of the mean; with a masked judged
// share, or none left in the reference, no signal and the reason.
export type EtatSignal = "raised" | "not_raised";
export type MotifSignal = "tasks_without_team_share_masked";

export function attachmentSignal(entree: {
  judgedShare: number | null;
  referenceShares: Array<number | null>;
  thresholdPoints: number;
}): { signal: EtatSignal; reasons: MotifSignal[] } {
  const { judgedShare, thresholdPoints } = entree;
  const parts = entree.referenceShares.filter((p): p is number => p !== null);
  if (judgedShare === null || parts.length === 0) {
    return { signal: "not_raised", reasons: ["tasks_without_team_share_masked"] };
  }
  const reference = parts.reduce((a, b) => a + b, 0) / parts.length;
  return { signal: arrondi(Math.abs(judgedShare - reference)) > thresholdPoints ? "raised" : "not_raised", reasons: [] };
}

// Unplanned work (D33): no team field on defects, so a team's sheet reads "not measurable" with the reason `defects_without_team`;
// the product-level measure keeps the state its own data gave. Once defects carry a team the caller must give the team's state: a
// team sheet with `defectsCarryTeam` and no `teamState` is an error, never a silent default.
export interface Explication {
  name: "unplanned_work" | "capacity" | "dependencies";
  state: EtatExplication;
  reason?: string;
}

export function unplannedWorkExplanation(entree: {
  scope: "team" | "product";
  defectsCarryTeam: boolean;
  productState: EtatExplication;
  teamState?: EtatExplication;
}): Explication {
  if (entree.scope === "team") {
    if (!entree.defectsCarryTeam) {
      return { name: "unplanned_work", state: "not_measurable", reason: "defects_without_team" };
    }
    if (entree.teamState === undefined) {
      throw new Error("travail non planifié : les défauts portent une équipe, l'état de l'équipe est obligatoire");
    }
    return { name: "unplanned_work", state: entree.teamState };
  }
  return { name: "unplanned_work", state: entree.productState };
}

export interface RaisonVerdict {
  explanation: string;
  state: EtatExplication;
  reason: string;
}

const EXPLICATIONS_ATTENDUES = ["unplanned_work", "capacity", "dependencies"] as const;

// The ban (D20): while a competing explanation is "not ruled out" or "not measurable", data that would confirm give "not settled"
// with the reasons; "refuted" and "not settled" are kept as computed. The three explanations are required, each once: a list that
// leaves one out is refused. The attachment signal is such an explanation only when the verdict reads throughput (hypothesis 5);
// for a verdict that reads no throughput it has no effect. An insufficient sample stays out.
export function verdictFinal(entree: {
  raw: VerdictOuEchantillon;
  explanations: Explication[];
  readsThroughput: boolean;
  attachment: EtatSignal;
}): { verdict: VerdictOuEchantillon; reasons: RaisonVerdict[]; attachmentSignalShown: boolean } {
  const noms = entree.explanations.map((e) => e.name);
  if (noms.length !== EXPLICATIONS_ATTENDUES.length || !EXPLICATIONS_ATTENDUES.every((n) => noms.filter((x) => x === n).length === 1)) {
    throw new Error("explications concurrentes : les trois sont exigées, chacune une fois");
  }
  const raisons: RaisonVerdict[] = [];
  for (const e of entree.explanations) {
    if (e.state !== "ruled_out") {
      raisons.push({ explanation: e.name, state: e.state, reason: e.reason ?? e.name });
    }
  }
  if (entree.readsThroughput && entree.attachment === "raised") {
    raisons.push({ explanation: "tasks_attachment", state: "not_ruled_out", reason: "tasks_attachment_signal" });
  }
  const montre = entree.readsThroughput && entree.attachment === "raised";
  if (entree.raw === "confirmed" && raisons.length > 0) {
    return { verdict: "not_settled", reasons: raisons, attachmentSignalShown: montre };
  }
  return { verdict: entree.raw, reasons: raisons, attachmentSignalShown: montre };
}

// "Threshold modified after reading": a value recorded after the sheet's data was first read. Dates are ISO strings (YYYY-MM-DD),
// compared as text. As a precaution a value recorded on the very day of the first reading counts as after it; a value recorded only
// after (or on) the first reading is flagged too, with no former value. `former` is the value in force before the first reading,
// with its date, when there was one.
export interface EntreeSeuil {
  value: number;
  setOn: string;
}

export function thresholdModifiedAfterReading(entree: {
  history: EntreeSeuil[];
  firstReadOn: string | null;
}): { modified: boolean; former?: EntreeSeuil } {
  if (entree.firstReadOn === null) {
    return { modified: false };
  }
  const lu = entree.firstReadOn;
  const triee = [...entree.history].sort((a, b) => (a.setOn < b.setOn ? -1 : a.setOn > b.setOn ? 1 : 0));
  const avant = triee.filter((h) => h.setOn < lu);
  const apres = triee.some((h) => h.setOn >= lu);
  if (!apres) {
    return { modified: false };
  }
  return avant.length === 0 ? { modified: true } : { modified: true, former: avant[avant.length - 1] };
}

// Link colour (mothra-home, decision of the author of 2026-10-27). "Not tested" with no sheet; "in progress" with only draft or
// reviewed sheets; otherwise the latest published sheet of each team. Only teams with a verdict count (confirmed or refuted): masked,
// insufficient-sample and not-settled teams do not. The colour is the strict majority of those teams, with at least `minTeams` of
// them, else "not settled" (also when no team counts, with zero counts, never "not tested"). The count of teams of the shown colour
// out of the teams with a verdict is always returned beside the colour. The second half of hypothesis 1 stays "not tested";
// hypothesis 4 always reads "partial evidence, signals". A latest published sheet with no verdict is listed, not dropped.
export type EtatLien = "not_tested" | "in_progress" | "partial_evidence_signals" | Verdict;

export interface FeuilleLien {
  team: string;
  state: "draft" | "reviewed" | "published" | "contested" | "replaced";
  verdict: Verdict | null;
  version: number;
  masked?: boolean;
  insufficientSample?: boolean;
}

export interface ResultatLien {
  state: EtatLien;
  counts: Record<Verdict, number>;
  teamsWithVerdict: number;
  colourTeams: number;
  publishedWithoutVerdict: string[];
}

export function linkColour(entree: { link: LienId; sheets: FeuilleLien[]; config: { minTeams: number } }): ResultatLien {
  const comptes: Record<Verdict, number> = { refuted: 0, not_settled: 0, confirmed: 0 };
  const resultat = (state: EtatLien, avecVerdict = 0, couleur = 0, sansVerdict: string[] = []): ResultatLien => ({
    state,
    counts: comptes,
    teamsWithVerdict: avecVerdict,
    colourTeams: couleur,
    publishedWithoutVerdict: sansVerdict,
  });
  if (entree.link === "h4") {
    return resultat("partial_evidence_signals");
  }
  if (entree.link === "h1_second_half" || entree.sheets.length === 0) {
    return resultat("not_tested");
  }
  const publiees = entree.sheets.filter((f) => f.state === "published");
  if (publiees.length === 0) {
    return resultat("in_progress");
  }
  const derniere = new Map<string, FeuilleLien>();
  for (const f of publiees) {
    const cour = derniere.get(f.team);
    if (cour === undefined || f.version > cour.version) {
      derniere.set(f.team, f);
    }
  }
  const sansVerdict: string[] = [];
  for (const f of derniere.values()) {
    if (f.verdict === null) {
      sansVerdict.push(f.team);
      continue;
    }
    if (f.masked === true || f.insufficientSample === true) {
      continue;
    }
    comptes[f.verdict] += 1;
  }
  sansVerdict.sort();
  const avecVerdict = comptes.refuted + comptes.confirmed;
  if (avecVerdict >= entree.config.minTeams && avecVerdict > 0) {
    for (const v of ["refuted", "confirmed"] as const) {
      if (comptes[v] * 2 > avecVerdict) {
        return resultat(v, avecVerdict, comptes[v], sansVerdict);
      }
    }
  }
  return resultat("not_settled", avecVerdict, 0, sansVerdict);
}
