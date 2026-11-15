// The computed body of an argument sheet from the masked answers of the views (mothra-slices D20, D30, D33, task 18.4). One pure function,
// no I/O, no clock, no hash: the server reads the views through its masking path (service.ts) and the threshold history, computes the
// fingerprint of what it read, and hands them here. The verdict functions of verdict.ts are called here and nowhere else.
//
// Decisions of the author applied here (R-20261030-58): Q2 the capacity and dependencies explanations are "not ruled out" (reason
// `no_adopted_threshold`) when measured and "not measurable" when masked, until the author freezes their thresholds; Q3 the chart gives
// two kinds, one hypothesis each; Q5 a threshold missing from the history gives no verdict (SeuilsNonFixes); Q6 a median, a P85 or a
// throughput masked or on a short sample in a reference quarter gives no reference (so "insufficient sample"); Q7 the ratios of the
// first half of hypothesis 1 are reliable only when both headcounts reach the size; Q8 the first reading is the creation of the sheet;
// Q11 the judged quarter is the last quarter closed as of the data date, the reference is the three quarters ending with it (R-20261114-49: three closed
// quarters, four before). Readings of this file that the decisions leave open: the thresholds in force are the latest of the history (a value recorded after
// the first reading is flagged, not ignored); the quarters of the signal on tasks without a team are the two before the judged one (R-20261114-51, D13).
import type { Cellule } from "./cellule.ts";
import { porteeDeScope, scopeFiche } from "./equipe.ts";
import type { CorpsFiche, ExplicationFiche, Part, RapportsH1, RapportsTrimestre, Seuil, StatistiquesP85 } from "./fiche.ts";
import type { Mesure, PointTrimestre } from "./lead-cycle.ts";
import { couplesIncoherents, seuilDansLesBornes } from "./bornes-seuils.ts";
import { ANNEE_GROUPEE, CODES_LIMITES, CODES_SEUILS, METHODES, ROLE_AUTEUR, codeMesure, codesRequis, estGraphiqueDeFiche } from "./listes-fiche.ts";
import type { GraphiqueDeFiche } from "./listes-fiche.ts";
import { celluleDe, celluleOuMasquee, mesureDeStatistique, texteDe } from "./lecture-vue.ts";
import type { CelluleLue } from "./lecture-vue.ts";
import { tableauLeadCycle } from "./lead-cycle.ts";
import { tailleEchantillonH1 } from "./taille-echantillon.ts";
import type { LigneReponse, ReponseVue } from "./reponse.ts";
import { dernierTrimestreClos, etiquetteTrimestre, fenetreTroisTrimestres, trimestreDe } from "./trimestres.ts";
import {
  attachmentSignal,
  constatsFinaux,
  h1Evaluer,
  h5Evaluer,
  litLeDebit,
  referenceH5,
  thresholdModifiedAfterReading,
  throughputPositions,
  unplannedWorkExplanation,
  verdictFinal,
} from "./verdict.ts";
import type { ConfigEchantillon, ConfigH5, ConstatDeVerdict, EtatSignal, Explication, ExclusionsH5, MotifH1, MotifH5, MotifSignal, TrimestreH5 } from "./verdict.ts";

// A threshold missing from the history: no verdict is computed (THRESHOLDS_NOT_SET, 409). The codes are kept for the log of the server.
export class SeuilsNonFixes extends Error {
  codes: string[];
  constructor(codes: string[]) {
    super("thresholds not set");
    this.name = "SeuilsNonFixes";
    this.codes = codes;
  }
}

// A history already inconsistent (a lower threshold at or above its upper one, audit #629 A-63): the same declared answer as a missing
// threshold (409 THRESHOLDS_NOT_SET, no verdict computed), never a raw RangeError of twoThresholds (a 500 on every sheet of the chart).
// Replaces: the RangeError of twoThresholds reaching the route. Removal: permanent while a history written before the check can hold a pair
// that is not ordered; the write itself refuses such a pair (bornes-seuils.ts).
export class SeuilsIncoherents extends SeuilsNonFixes {
  constructor(codes: string[]) {
    super(codes);
    this.name = "SeuilsIncoherents";
  }
}

// A chart outside the closed list of the sheet kinds (400 INVALID_REQUEST).
export class GraphiqueInconnu extends Error {
  constructor() {
    super("unknown chart");
    this.name = "GraphiqueInconnu";
  }
}

// One line of the dated threshold history (insertion only, D21).
export interface EntreeHistorique {
  code: string;
  value: number;
  setOn: string; // ISO date
}

// A scope that is not `team.<identifier>`: a team name, an unknown text, or the product level (no product line exists in the lead time
// view, so no sheet of these two kinds is served: 400 INVALID_REQUEST, review of 18.4, A1).
export class PorteeNonServie extends Error {
  constructor() {
    super("scope not served");
    this.name = "PorteeNonServie";
  }
}

function equipeDeLaPortee(scope: string): void {
  const portee = porteeDeScope(scope);
  if (portee === null || portee.kind !== "team") {
    throw new PorteeNonServie();
  }
}

// The thresholds in force for the given codes: the latest value of each code in the history, with its date; flagged when a value was
// recorded after the first reading of the sheet and a value existed before it. A missing code gives SeuilsNonFixes naming every
// missing code.
export function lireSeuils(historique: readonly EntreeHistorique[], codes: readonly string[], premiereLecture: string | null): Seuil[] {
  const manquants: string[] = [];
  const seuils: Seuil[] = [];
  for (const code of codes) {
    const propres = historique.filter((h) => h.code === code).sort((a, b) => (a.setOn < b.setOn ? -1 : a.setOn > b.setOn ? 1 : 0));
    if (propres.length === 0) {
      manquants.push(code);
      continue;
    }
    const dernier = propres[propres.length - 1];
    const seuil: Seuil = { code, value: dernier.value, fixedOn: dernier.setOn, fixedBy: "author_alone" };
    const modifie = thresholdModifiedAfterReading({
      history: propres.map((h) => ({ value: h.value, setOn: h.setOn })),
      firstReadOn: premiereLecture,
    });
    if (modifie.modified && modifie.former !== undefined) {
      seuil.modifiedAfterReading = { formerValue: modifie.former.value, formerDate: modifie.former.setOn };
    }
    seuils.push(seuil);
  }
  if (manquants.length > 0) {
    throw new SeuilsNonFixes(manquants);
  }
  // A latest value outside the bounds of its code (a size of 0 written before the bounds existed) is as inconsistent as an unordered pair:
  // declared error (409), never a guard removed. Replaces: the reading without bound check. Removal: permanent (bornes-seuils.ts).
  const horsBornes = seuils.filter((s) => !seuilDansLesBornes(s.code, s.value)).map((s) => s.code);
  const incoherents = [...new Set([...couplesIncoherents(historique).filter((code) => codes.includes(code)), ...horsBornes])];
  if (incoherents.length > 0) {
    throw new SeuilsIncoherents(incoherents);
  }
  return seuils;
}

// Checks that a chart can give a sheet now: the chart is in the closed list, the scope is `team.<identifier>` and every threshold the
// chart reads is in the history.
export function verifierCreation(chart: string, historique: readonly EntreeHistorique[], scope: string): void {
  if (!estGraphiqueDeFiche(chart)) {
    throw new GraphiqueInconnu();
  }
  equipeDeLaPortee(scope);
  lireSeuils(historique, codesRequis(chart), null);
}

export interface VuesDeLaFiche {
  leadCycle: ReponseVue; // v_team_lead_time_throughput
  sansEquipe: ReponseVue; // v_task_without_team_share
  nonPlanifie: ReponseVue; // v_unplanned_share
  fileEnAttente: ReponseVue; // v_team_ready_queue
  bloque: ReponseVue; // v_team_blocked_share
}

export interface EntreeCorps {
  chart: string;
  scope: string;
  dataDate: string;
  premiereLecture: string | null; // the day the sheet was created (Q8)
  historique: readonly EntreeHistorique[];
  vues: VuesDeLaFiche; // the masked answers, as the server serves them
  identifiantEquipe: (nom: string) => string; // the opaque team identifier of the contract (R-20261030-61), given by the caller
  empreinte: string; // the fingerprint of the answers read, computed by the server
}

export type CorpsDepuisVues = Omit<CorpsFiche, "id" | "effect" | "cause">;

function valeurDe(seuils: readonly Seuil[], code: string): number {
  const s = seuils.find((x) => x.code === code);
  if (s === undefined) {
    throw new Error(`seuil absent : ${code}`);
  }
  return s.value;
}

function ligneDuTrimestre(reponse: ReponseVue, debut: string, equipe: string | null): LigneReponse | undefined {
  return reponse.rows.find((r) => texteDe(r, "quarter_start") === debut && (equipe === null || texteDe(r, "team") === equipe) && texteDe(r, "period") !== "pooled_year");
}

function enPart(cellule: CelluleLue | null): Part | undefined {
  if (cellule === null) {
    return undefined;
  }
  return cellule.state === "value" ? { state: "value", value: cellule.value } : { state: "masked", threshold: cellule.threshold };
}

function explicationMesuree(name: Explication["name"], cellule: CelluleLue | null): ExplicationFiche {
  if (cellule === null) {
    return { name, state: "not_measurable", reason: "no_data" };
  }
  if (cellule.state === "masked") {
    return { name, state: "not_measurable", reason: "masked", measure: { state: "masked", threshold: cellule.threshold } };
  }
  return { name, state: "not_ruled_out", reason: "no_adopted_threshold", measure: { state: "value", value: cellule.value } };
}

// The ratio of two measures (lead time over cycle time): masked when a term is, insufficient when a term is or when the divisor is not
// above zero, a value otherwise. Nothing is estimated.
function rapportDeMesures(a: Mesure, b: Mesure): Mesure {
  if (a.state === "masked") {
    return { state: "masked", threshold: a.threshold };
  }
  if (b.state === "masked") {
    return { state: "masked", threshold: b.threshold };
  }
  if (a.state === "insufficient_sample" || b.state === "insufficient_sample" || !(b.value > 0)) {
    return { state: "insufficient_sample" };
  }
  return { state: "value", value: a.value / b.value };
}

function maxDate(dates: string[]): string {
  return dates.reduce((a, b) => (a > b ? a : b));
}

export function corpsDepuisVues(entree: EntreeCorps): CorpsDepuisVues {
  if (!estGraphiqueDeFiche(entree.chart)) {
    throw new GraphiqueInconnu();
  }
  const graphique: GraphiqueDeFiche = entree.chart;
  const seuils = lireSeuils(entree.historique, codesRequis(graphique), entree.premiereLecture);
  const val = (code: string): number => valeurDe(seuils, code);
  const echantillon: ConfigEchantillon = { medianMinItems: val("sample_median_min_items"), p85MinItems: val("sample_p85_min_items") };
  const { vues } = entree;
  const seuilVue = vues.leadCycle.threshold;

  // The scope: `team.<identifier>`, matched against the team names of the view through the identifier of the contract. Anything else
  // (the product level, a team name) is refused.
  equipeDeLaPortee(entree.scope);
  const noms = new Set<string>();
  for (const r of vues.leadCycle.rows) {
    const nom = texteDe(r, "team");
    if (nom !== null && scopeFiche({ kind: "team", team: entree.identifiantEquipe(nom) }) === entree.scope) {
      noms.add(nom);
    }
  }
  const equipe: string | null = noms.size === 1 ? [...noms][0] : null;

  const juge = dernierTrimestreClos(entree.dataDate);
  const fenetre = fenetreTroisTrimestres(entree.dataDate).reverse();      // the three closed quarters, the oldest first, the judged one last (R-20261114-49)
  const lignesEquipe: LigneReponse[] = equipe === null ? [] : vues.leadCycle.rows.filter((r) => texteDe(r, "team") === equipe);
  const ligneT = (debut: string): LigneReponse | undefined => lignesEquipe.find((r) => texteDe(r, "quarter_start") === debut && texteDe(r, "period") !== "pooled_year");
  const ligneAnnee = lignesEquipe.find((r) => texteDe(r, "period") === "pooled_year");

  const masquees: Array<{ measure: string; cell: Extract<Cellule, { state: "masked" }> }> = [];
  const insuffisants: string[] = [];
  const noter = (code: string, cellule: CelluleLue | null): void => {
    if (cellule !== null && cellule.state === "masked") {
      masquees.push({ measure: code, cell: { state: "masked", threshold: cellule.threshold } });
    }
  };
  const noterMesure = (code: string, m: { state: string; threshold?: number }): void => {
    if (m.state === "masked" && m.threshold !== undefined) {
      masquees.push({ measure: code, cell: { state: "masked", threshold: m.threshold } });
    } else if (m.state === "insufficient_sample") {
      insuffisants.push(code);
    }
  };

  // The explanations that do not depend on the hypothesis (judged quarter).
  const celluleJuge = (reponse: ReponseVue, colonne: string, parEquipe: boolean): CelluleLue | null => {
    if (parEquipe && equipe === null) {
      return null;
    }
    return celluleDe(ligneDuTrimestre(reponse, juge, parEquipe ? equipe : null), colonne);
  };
  const partNonPlanifiee = celluleJuge(vues.nonPlanifie, "share_percent", false);
  const partSansEquipe = celluleJuge(vues.sansEquipe, "share_percent", false);
  const fileJugee = celluleJuge(vues.fileEnAttente, "ready", true);
  const bloqueJuge = celluleJuge(vues.bloque, "share_percent", true);
  noter(codeMesure("unplanned_share", juge), partNonPlanifiee);
  noter(codeMesure("ready", juge), fileJugee);
  noter(codeMesure("blocked_share", juge), bloqueJuge);

  // A team sheet only: defects carry no team, so the unplanned work of the team is not measurable (D33); the product share is context.
  const nonPlanifie = unplannedWorkExplanation({
    scope: "team",
    defectsCarryTeam: false,
    productState: "not_measurable",
  });
  const explicationNonPlanifie: ExplicationFiche = { ...nonPlanifie, reason: nonPlanifie.reason ?? "defects_without_team" };
  const explications: ExplicationFiche[] = [
    explicationNonPlanifie,
    explicationMesuree("capacity", fileJugee),
    explicationMesuree("dependencies", bloqueJuge),
  ];

  let brut: ReturnType<typeof h5Evaluer>["verdict"];
  let constatsBruts: ConstatDeVerdict[] = [];
  let motifsH1: MotifH1[] = [];
  let motifsH5: MotifH5[] = [];
  let exclus: ExclusionsH5 = { median: [], p85: [], throughput: [] };
  let signal: { signal: EtatSignal; reasons: MotifSignal[] } = { signal: "not_raised", reasons: [] };
  let couverture: CelluleLue;
  let hypothese: CorpsFiche["method"]["hypothesis"];
  let positionsDebit: NonNullable<CorpsFiche["throughputPositions"]> = [];

  if (graphique === "lead_cycle_h5") {
    hypothese = "h5";
    const config: ConfigH5 = {
      band: val("h5_band"),
      doubleBand: val("h5_double_band"),
      runRises: val("h5_run_rises"),
      runMinCumulativeRise: val("h5_run_min_cumulative_rise"),
      floor: val("h5_floor"),
      lowFloor: val("h5_low_floor"),
    };
    const trimestres: TrimestreH5[] = fenetre.map((debut) => {
      const ligne = ligneT(debut);
      const effectif = celluleDe(ligne, "items_ct");
      const mediane = mesureDeStatistique(celluleDe(ligne, "cycle_median_days"), effectif, echantillon.medianMinItems, seuilVue);
      const p85 = mesureDeStatistique(celluleDe(ligne, "cycle_p85_days"), effectif, echantillon.p85MinItems, seuilVue);
      const debit = celluleDe(ligne, "throughput");
      if (ligne !== undefined) {
        noterMesure(codeMesure("cycle_median_days", debut), mediane);
        noterMesure(codeMesure("cycle_p85_days", debut), p85);
        noter(codeMesure("throughput", debut), debit);
      }
      return {
        median: mediane.state === "value" ? mediane.value : 0,
        p85: p85.state === "value" ? p85.value : 0,
        throughput: debit !== null && debit.state === "value" ? debit.value : null,
        medianSufficient: mediane.state === "value",
        p85Sufficient: p85.state === "value",
      };
    });
    // Q6: a reference quarter (the two quarters before the judged one) with a masked or short figure gives no reference. The judged quarter, when one of
    // its figures is missing, is left out of the mean and keeps its own exclusion in the verdict; with three closed quarters only two are then complete, which
    // is no reference either (D14, R-20261114-83): the verdict is "insufficient sample" (before, with four quarters, three were still complete).
    const complet = (q: TrimestreH5): q is TrimestreH5 & { throughput: number } => q.medianSufficient && q.p85Sufficient && q.throughput !== null;
    // The oldest quarters with no row in the view (the team did not exist yet) are not part of the series: the annex allows three
    // complete quarters. A quarter with no row after the first one is a hole: it stands as a quarter with nothing shown (it breaks the
    // series of rises and, being no complete reference quarter, gives no reference). A judged quarter with no row gives no verdict
    // (review of 18.4, C1): the sheet names that quarter.
    const premier = fenetre.findIndex((d) => ligneT(d) !== undefined);
    const dernier = fenetre.length - 1;
    if (ligneT(juge) === undefined || premier < 0) {
      brut = "insufficient_sample";
    } else {
      const positions = fenetre.map((_, i) => i).filter((i) => i >= premier);
      const presents = positions.map((i) => trimestres[i]);
      const autres = presents.filter((_, k) => positions[k] !== dernier);
      const base = autres.every(complet) ? presents.filter(complet) : [];
      const reference = referenceH5(base.map((q) => ({ median: q.median, p85: q.p85, throughput: q.throughput })));
      const resultat = h5Evaluer({ quarters: presents, reference, config });
      brut = resultat.verdict;
      motifsH5 = resultat.reasons;
      constatsBruts = resultat.findings;
      // Task 19.5: the position of each quarter with a row against the reference (no reference, no position: Q11 (a) of R-20261031-01).
      positionsDebit = throughputPositions({
        quarters: fenetre.flatMap<{ quarter: string; throughput: number | null }>((debut, i) => (ligneT(debut) === undefined ? [] : [{ quarter: etiquetteTrimestre(debut), throughput: trimestres[i].throughput }])),
        reference: reference === null ? null : reference.throughput,
        floor: config.floor,
        lowFloor: config.lowFloor,
      });
      // The exclusions point into the quarters of the sheet (`period.quarters`), not into the series without the oldest absent quarters.
      exclus = {
        median: resultat.excluded.median.map((k) => positions[k]),
        p85: resultat.excluded.p85.map((k) => positions[k]),
        throughput: resultat.excluded.throughput.map((k) => positions[k]),
      };
    }

    const partDe = (debut: string): number | null => {
      const c = celluleDe(ligneDuTrimestre(vues.sansEquipe, debut, null), "share_percent");
      return c !== null && c.state === "value" ? c.value : null;
    };
    for (const debut of fenetre) {
      noter(codeMesure("tasks_without_team_share", debut), celluleDe(ligneDuTrimestre(vues.sansEquipe, debut, null), "share_percent"));
    }
    signal = attachmentSignal({
      judgedShare: partDe(juge),
      referenceShares: fenetre.slice(0, -1).map(partDe),
      thresholdPoints: val("attachment_threshold_points"),
    });
    couverture = celluleOuMasquee(celluleDe(ligneT(juge), "items_ct"), seuilVue);
  } else {
    hypothese = "h1_first_half";
    const bas = val("h1_lower");
    const haut = val("h1_upper");
    const nLt = celluleDe(ligneAnnee, "items_lt");
    const nCt = celluleDe(ligneAnnee, "items_ct");
    // Task 22.1 (D16, R-20261105-30, R-20261106-59): the ratios of H1 read the statistics without the old items ("counted apart, out of the ratio"); the codes
    // of the measures noted below stay those of the sheet. A statistic without the old items is shown only with items_old of the same row shown.
    const lm = celluleDe(ligneAnnee, "lead_median_days_excl_old");
    const cm = celluleDe(ligneAnnee, "cycle_median_days_excl_old");
    const lp = celluleDe(ligneAnnee, "lead_p85_days_excl_old");
    const cp = celluleDe(ligneAnnee, "cycle_p85_days_excl_old");
    const cellulesAnnee = { items_lt: nLt, items_ct: nCt, items_old: celluleDe(ligneAnnee, "items_old") };
    if (ligneAnnee !== undefined) {
      noter(codeMesure("lead_median_days", ANNEE_GROUPEE), lm);
      noter(codeMesure("cycle_median_days", ANNEE_GROUPEE), cm);
      noter(codeMesure("lead_p85_days", ANNEE_GROUPEE), lp);
      noter(codeMesure("cycle_p85_days", ANNEE_GROUPEE), cp);
    }
    // A ratio needs both statistics shown and a cycle time above zero (a division by zero would read as an infinite ratio).
    const rapport = (a: CelluleLue | null, b: CelluleLue | null): number | null =>
      a !== null && b !== null && a.state === "value" && b.state === "value" && b.value > 0 ? a.value / b.value : null;
    // Q7, D16 "Sample size of H1": both sizes of the pooled year (items_lt and items_ct minus items_old, from the shown cells only) reach the size; a masked
    // items_old gives no size, so no sample. The size itself is never published.
    const atteint = (taille: number): boolean => {
      const lead = tailleEchantillonH1("lead", cellulesAnnee);
      const cycle = tailleEchantillonH1("cycle", cellulesAnnee);
      return lead !== null && cycle !== null && lead >= taille && cycle >= taille;
    };
    const resultat = h1Evaluer({
      medianRatio: rapport(lm, cm),
      p85Ratio: rapport(lp, cp),
      lower: bas,
      upper: haut,
      medianSampleSufficient: atteint(echantillon.medianMinItems),
      p85SampleSufficient: atteint(echantillon.p85MinItems),
    });
    brut = resultat.verdict;
    motifsH1 = resultat.reasons;
    constatsBruts = resultat.findings;
    if (resultat.reasons.some((m) => m === "median_insufficient_sample")) {
      insuffisants.push(codeMesure("median_ratio", ANNEE_GROUPEE));
    }
    if (resultat.reasons.some((m) => m === "p85_insufficient_sample")) {
      insuffisants.push(codeMesure("p85_ratio", ANNEE_GROUPEE));
    }
    couverture = celluleOuMasquee(nCt, seuilVue);
  }

  const lit = litLeDebit(hypothese);
  const final = verdictFinal({ raw: brut, explanations: explications, readsThroughput: lit, attachment: signal.signal });
  // A-01 (Q6): the finding of the verdict, from the function that decided the raw one; barred when the ban of D20 turned a confirmation down.
  const constats = constatsFinaux({ raw: brut, findings: constatsBruts, final: final.verdict });

  // The chart: the figures of the dashboard function, for the quarters of the sheet and the pooled year of the team.
  const tableau = tableauLeadCycle(vues.leadCycle, echantillon, entree.dataDate, entree.identifiantEquipe);
  const serie = equipe === null ? undefined : tableau.teams.find((s) => s.team === equipe);
  const etiquettes = new Set(fenetre.map(etiquetteTrimestre));
  const anneeDuTableau = serie?.points.find((p) => p.quarter === "pooled_year");
  // Audit #629, H-01: on a sheet of H1 the pooled year (chart, P85 and ratios) reads the statistics WITHOUT the old items, like the verdict and the
  // cells noted in `maskedCells`; a cell the sheet declares masked is never shown by its chart. The sample is that of H1 (items minus old items, from
  // the shown cells only). The quarters keep the statistics with the old items (the verdict of H1 reads the pooled year only).
  // Replaces: nothing. Removal: permanent while the verdict of H1 reads the statistics without the old items.
  const sansAnciens = graphique === "lead_cycle_h1" && ligneAnnee !== undefined;
  // Recomposée par fiches-calcul.test.ts (R-20261108-08) : tout changement ici se reporte dans ce test.
  const mesureSansAnciens = (colonne: string, genre: "lead" | "cycle", taille: number): Mesure => {
    const statistique = celluleDe(ligneAnnee, colonne);
    if (statistique === null) return { state: "masked", threshold: seuilVue };
    if (statistique.state === "masked") return { state: "masked", threshold: statistique.threshold };
    const effectif = tailleEchantillonH1(genre, {
      items_lt: celluleDe(ligneAnnee, "items_lt"),
      items_ct: celluleDe(ligneAnnee, "items_ct"),
      items_old: celluleDe(ligneAnnee, "items_old"),
    });
    if (effectif === null || effectif < taille) return { state: "insufficient_sample" };
    return { state: "value", value: statistique.value };
  };
  const annee: typeof anneeDuTableau =
    anneeDuTableau === undefined || !sansAnciens
      ? anneeDuTableau
      : {
          ...anneeDuTableau,
          lead: mesureSansAnciens("lead_median_days_excl_old", "lead", echantillon.medianMinItems),
          cycle: mesureSansAnciens("cycle_median_days_excl_old", "cycle", echantillon.medianMinItems),
        };
  const graphiqueFiche: NonNullable<CorpsFiche["chart"]> = {
    quarters: (serie?.points ?? []).filter((p) => etiquettes.has(p.quarter)),
    ...(annee === undefined ? {} : { pooledYear: annee }),
  };

  // Task 19.5 (D34): the P85 of the quarters of the sheet and of the pooled year, read as the dashboard reads the medians.
  const pointP85 = (ligne: LigneReponse, etiquette: string): PointTrimestre => ({
    quarter: etiquette,
    lead: mesureDeStatistique(celluleDe(ligne, "lead_p85_days"), celluleDe(ligne, "items_lt"), echantillon.p85MinItems, seuilVue),
    cycle: mesureDeStatistique(celluleDe(ligne, "cycle_p85_days"), celluleDe(ligne, "items_ct"), echantillon.p85MinItems, seuilVue),
  });
  const pointP85Annee: PointTrimestre | undefined =
    ligneAnnee === undefined
      ? undefined
      : sansAnciens
        ? {
            quarter: ANNEE_GROUPEE,
            lead: mesureSansAnciens("lead_p85_days_excl_old", "lead", echantillon.p85MinItems),
            cycle: mesureSansAnciens("cycle_p85_days_excl_old", "cycle", echantillon.p85MinItems),
          }
        : pointP85(ligneAnnee, ANNEE_GROUPEE);
  const p85: StatistiquesP85 = {
    quarters: fenetre.flatMap<PointTrimestre>((debut) => {
      const ligne = ligneT(debut);
      return ligne === undefined ? [] : [pointP85(ligne, etiquetteTrimestre(debut))];
    }),
    ...(pointP85Annee === undefined ? {} : { pooledYear: pointP85Annee }),
  };
  // The ratios of the first half of hypothesis 1 (lead time over cycle time): median and P85, a ratio shown only when both terms are.
  let rapports: RapportsH1 | undefined;
  if (graphique === "lead_cycle_h1") {
    const rapportDe = (mediane: PointTrimestre, p: PointTrimestre | undefined): RapportsTrimestre => ({
      quarter: mediane.quarter,
      median: rapportDeMesures(mediane.lead, mediane.cycle),
      p85: p === undefined ? { state: "masked", threshold: seuilVue } : rapportDeMesures(p.lead, p.cycle),
    });
    rapports = {
      quarters: graphiqueFiche.quarters.map((m) => rapportDe(m, p85.quarters.find((p) => p.quarter === m.quarter))),
      ...(annee === undefined ? {} : { pooledYear: rapportDe(annee, p85.pooledYear) }),
    };
  }

  const limites: CorpsFiche["method"]["limits"] = [];
  const ajouter = (l: (typeof CODES_LIMITES)[number]): void => {
    limites.push(l);
  };
  ajouter("no_per_team_unplanned_measure");
  ajouter("capacity_dependencies_no_adopted_threshold");
  ajouter("views_last_three_closed_quarters");      // every new sheet; `views_last_four_quarters` stays a known code of frozen sheets, never written again (design D6, D8)
  if (graphique === "lead_cycle_h5") {
    ajouter("attachment_signal_product_level");
    ajouter("throughput_own_past_only"); // D33 point 2: the throughput is compared with the team's own past only
  }

  const tasksShare = graphique === "lead_cycle_h5" ? enPart(partSansEquipe) : undefined;
  const produitNonPlanifie = enPart(partNonPlanifiee);

  return {
    verdict: final.verdict,
    verdictReasons: final.reasons,
    h1Reasons: motifsH1,
    h5Reasons: motifsH5,
    verdictFindings: constats,
    explanations: explications,
    chart: graphiqueFiche,
    ...(produitNonPlanifie === undefined ? {} : { unplannedProductShare: produitNonPlanifie }),
    attachmentSignal: signal.signal,
    attachmentSignalReasons: signal.reasons,
    attachmentSignalShown: final.attachmentSignalShown,
    ...(tasksShare === undefined ? {} : { tasksWithoutTeamShare: tasksShare }),
    p85,
    ...(graphique === "lead_cycle_h5" ? { throughputPositions: positionsDebit } : {}),
    ...(rapports === undefined ? {} : { ratios: rapports }),
    method: {
      method: METHODES[0],
      scope: { level: "team", id: entree.scope },
      period: { quarters: fenetre.map(trimestreDe) },
      thresholds: seuils,
      thresholdsFixedOn: maxDate(seuils.map((s) => s.fixedOn)),
      dataDate: entree.dataDate,
      fingerprint: entree.empreinte,
      coverage: couverture,
      maskedCells: masquees,
      insufficientSamples: insuffisants,
      excluded: exclus,
      limits: limites,
      authorRole: ROLE_AUTEUR,
      version: 1,
      hypothesis: hypothese,
    },
  };
}

// The codes of every threshold the sheets read (all kinds together), for the check of the server at start and in the tests.
export const TOUS_LES_CODES_SEUILS: readonly string[] = [...CODES_SEUILS.h5, ...CODES_SEUILS.h1, ...CODES_SEUILS.attachment, ...CODES_SEUILS.sample];
