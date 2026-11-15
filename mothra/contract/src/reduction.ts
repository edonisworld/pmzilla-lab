// The reduced form of an answer on real data (mothra-slices D34, tasks 19.5 and 19.6): statistics and states, no count. One pure function,
// called by the service layer of the server whenever the dataset is real and REAL_DATA_COUNTS_ALLOWED is false; never by a route's
// formatting nor a component. The verdict is computed from the counts BEFORE the reduction (D30), so the reduced verdict is the full one.
// The reduced answer is built field by field from a whitelist: a field the function does not name does not come out.
// Replaces: nothing. Removal: with the end of the exception (D34 point 6, the merge of masking-sums D15 and its group 7), when
// REAL_DATA_COUNTS_ALLOWED becomes true.
import type { CorpsDepuisVues } from "./corps-fiche.ts";
import type { PointDeFiche } from "./fiche.ts";
import type { CodeJeuDeDonnees } from "./listes-fiche.ts";
import type { ReponseLeadCycle, ReponseLeadCycleReduite } from "./lead-cycle.ts";
import type { PointTrimestre } from "./lead-cycle.ts";
import { reduirePanneau } from "./panneaux.ts";
import { identifiantEquipe, LIBELLE_PRODUIT, LIBELLE_SANS_EQUIPE } from "./equipe.ts";
import type { GenreDeLigne, ReponseVue } from "./reponse.ts";
import type { PanneauComplet, PanneauReduit } from "./panneaux.ts";
import { coverageState } from "./verdict.ts";

const sansEffectif = (p: PointDeFiche | PointTrimestre): PointTrimestre => ({ quarter: p.quarter, lead: p.lead, cycle: p.cycle });

function reduireCorps(corps: CorpsDepuisVues): CorpsDepuisVues {
  const { method } = corps;
  let etat = method.coverageState;
  if (method.coverage !== undefined) {
    const taille = method.thresholds.find((s) => s.code === "sample_p85_min_items");
    if (taille === undefined) {
      throw new Error("seuil absent : sample_p85_min_items");
    }
    etat = coverageState(method.coverage, taille.value);
  }
  if (etat === undefined) {
    throw new Error("état de couverture absent");
  }
  return {
    verdict: corps.verdict,
    verdictReasons: corps.verdictReasons,
    h1Reasons: corps.h1Reasons,
    h5Reasons: corps.h5Reasons,
    // The findings of the verdict are codes: they hold no count, the reduced form keeps them.
    ...(corps.verdictFindings === undefined ? {} : { verdictFindings: corps.verdictFindings }),
    // The state and the reason of each explanation; the measure it rests on (a count or a share of a count) is dropped.
    explanations: corps.explanations.map((e) => ({ name: e.name, state: e.state, ...(e.reason === undefined ? {} : { reason: e.reason }) })),
    ...(corps.chart === undefined
      ? {}
      : {
          chart: {
            quarters: corps.chart.quarters.map(sansEffectif),
            ...(corps.chart.pooledYear === undefined ? {} : { pooledYear: sansEffectif(corps.chart.pooledYear) }),
          },
        }),
    attachmentSignal: corps.attachmentSignal,
    attachmentSignalReasons: corps.attachmentSignalReasons,
    attachmentSignalShown: corps.attachmentSignalShown,
    ...(corps.p85 === undefined ? {} : { p85: corps.p85 }),
    ...(corps.throughputPositions === undefined ? {} : { throughputPositions: corps.throughputPositions }),
    ...(corps.ratios === undefined ? {} : { ratios: corps.ratios }),
    ...(corps.dataset === undefined ? {} : { dataset: corps.dataset }),
    method: {
      method: method.method,
      scope: method.scope,
      period: method.period,
      thresholds: method.thresholds,
      thresholdsFixedOn: method.thresholdsFixedOn,
      dataDate: method.dataDate,
      fingerprint: method.fingerprint,
      coverageState: etat,
      maskedCells: method.maskedCells,
      insufficientSamples: method.insufficientSamples,
      excluded: method.excluded,
      limits: method.limits.includes("reduced_form") ? method.limits : [...method.limits, "reduced_form"],
      authorRole: method.authorRole,
      version: method.version,
      hypothesis: method.hypothesis,
    },
  };
}

function reduireTableau(reponse: ReponseLeadCycle): ReponseLeadCycleReduite {
  return {
    threshold: reponse.threshold,
    dataDate: reponse.dataDate,
    product: reponse.product.map(sansEffectif),
    teams: reponse.teams.map((s) => ({ ...(s.team === undefined ? {} : { team: s.team }), teamId: s.teamId, points: s.points.map(sansEffectif) })),
    ...(reponse.dataset === undefined ? {} : { dataset: reponse.dataset }),
  };
}

// D34 point 2 (sheets) and point 7 (dashboards): from a full answer, the reduced answer. A sheet body keeps its medians, P85, ratios,
// verdict, reasons and codes, position codes, states of the explanations and of the signal, thresholds, dates, fingerprint; it loses every
// count (items, throughput, reference, shares of counts, coverage count) and gains `reduced_form` and the coverage state. A dashboard
// answer keeps the medians with their states and loses `items`.
export function reduceToStatistics(corps: CorpsDepuisVues): CorpsDepuisVues;
export function reduceToStatistics(reponse: ReponseLeadCycle): ReponseLeadCycleReduite;
// Task 37.1: a count panel of the product-scope dashboard keeps its header and the `reduced_form` code, and no count, total or share.
export function reduceToStatistics(panneau: PanneauComplet): PanneauReduit;
export function reduceToStatistics(
  entree: CorpsDepuisVues | ReponseLeadCycle | PanneauComplet,
): CorpsDepuisVues | ReponseLeadCycleReduite | PanneauReduit {
  if ("panel" in entree) return reduirePanneau(entree);
  return "teams" in entree ? reduireTableau(entree) : reduireCorps(entree);
}

// ---- The switch of the reduced form (mothra-slices D34, tasks 19.5, 19.6 and 37.1) ------------------------------------------------------
// Moved here from the service layer of the server (R-20261031-61, Q113): the "dataset, then reduction" gesture has no dependency on the
// server, so the server and the tests of the front call the same functions, without a copy. `jeu` is MOTHRA_DATASET, `comptesAutorises` is
// REAL_DATA_COUNTS_ALLOWED (given by the caller, so that a test can play the day the constant becomes true). Counts are allowed on the
// synthetic dataset always. The server's `service.ts` re-exports these names so that its routes keep one import.
export interface ModeDonnees {
  jeu: CodeJeuDeDonnees;
  comptesAutorises: boolean;
  // MOTHRA_SHOW_TEAM_NAMES (D17, D35, R-20261104-36 N1 (a)): absent or false, `servirTableau` leaves `team` out of every series.
  afficherNoms?: boolean;
}

// Replaces: the guard "sheet routes on the synthetic dataset only" of task 18.4 (R-20261030-58, Q9). Removal: with the end of the exception
// (D34 point 6), when the constant becomes true and every answer is complete again.
export function reduitEnMode(mode: ModeDonnees): boolean {
  return mode.jeu === "real" && !mode.comptesAutorises;
}

// A sheet body: the dataset code on every body, and the reduction on real data (D34 point 2). The verdict was computed from the counts
// before this call, so the reduced verdict is the complete one.
export function servirCorps(corps: CorpsDepuisVues, mode: ModeDonnees): CorpsDepuisVues {
  const avecJeu: CorpsDepuisVues = { ...corps, dataset: mode.jeu };
  return reduitEnMode(mode) ? reduceToStatistics(avecJeu) : avecJeu;
}

// The one entry for the answers of the second screen and of the dashboards (task 19.6, D34 point 7). On real data the answer is reduced to
// medians and P85 with their states.
// The team name is left out of every series, complete or reduced, unless the setting is on (D35, R-20261104-36 N1 (a)): the omission is
// decided here, in the service layer, never in a route's formatting. The identifier `teamId` stays the only key.
// Replaces: nothing. Removal: with single sign-on (D18, slice 5), when the authenticated role decides who sees the names (N3 (a)).
export function servirTableau(reponse: ReponseLeadCycle, mode: ModeDonnees): ReponseLeadCycle | ReponseLeadCycleReduite {
  // Order (Q238, R-20261107-30 1 (b), R-20261104-62 Q2): by identifier when the names are off, by name when they are on.
  // Replaces: the order by identifier alone, whatever the setting. Removal: with single sign-on (D18, slice 5), when the authenticated role
  // decides who sees the names (N3 (a)): the order then follows that decision.
  const parNom = (a: { team?: string }, b: { team?: string }): number => ((a.team ?? "") < (b.team ?? "") ? -1 : (a.team ?? "") > (b.team ?? "") ? 1 : 0);
  const teams =
    mode.afficherNoms === true
      ? [...reponse.teams].sort(parNom)
      : [...reponse.teams.map((s) => ({ teamId: s.teamId, points: s.points }))].sort((a, b) => (a.teamId < b.teamId ? -1 : a.teamId > b.teamId ? 1 : 0));
  const avecJeu: ReponseLeadCycle = { ...reponse, teams, dataset: mode.jeu };
  return reduitEnMode(mode) ? reduceToStatistics(avecJeu) : avecJeu;
}

// The answer of the generic route `/api/views/:view`: the column `team` is left out of `columns` and of every row unless the setting is on.
// Decided here, at the same point of service as `servirTableau`, never in a route's formatting (R-20261104-69 Q1, author's decision).
// Remplace : rien ; retrait : avec le réglage (N3 (a)).
// `kind` (R-20261109-21): every row of a by-team view (one with a column `team`) carries `kind`, "product", "no_team" or "team", in both
// settings. It holds no name and derives from none: the product row and the row without a team are recognised by their fixed labels, which
// are not team names; a `team` that is not a text (NULL) is "no_team". A view with no column `team` has no notion of team and its rows carry
// no `kind` (the rule "every row carries `kind`" holds for the by-team views, the only ones where a row can be a team).
const genreDeLigne = (team: unknown): GenreDeLigne =>
  team === LIBELLE_PRODUIT ? "product" : team === LIBELLE_SANS_EQUIPE || typeof team !== "string" ? "no_team" : "team";

// Order (Q238, R-20261107-30 1 (b), R-20261109-20, R-20261109-21): names on, the rows keep the order of the database (R-20261104-69 Q2);
// names off, the product row comes first, then the row without a team, then the teams by opaque identifier, as `servirTableau` does, never
// the alphabetical order of the names the column no longer shows. The product row can be masked and absent (H-05): `kind`, not the position,
// tells what a row is. The sort is stable: inside a team the order of the database stays.
// Q238 complétée pour la route des vues (R-20261109-21).
// Pour l'ordre des noms coupés. Remplace : l'ordre de la base. Retrait : avec le réglage (N3 (a)), comme servirTableau.
// Pour `kind`. Remplace : rien. Retrait : permanent tant que la route sert des vues par équipe.
export function servirVue(reponse: ReponseVue, mode: Pick<ModeDonnees, "afficherNoms">): ReponseVue {
  if (!reponse.columns.includes("team")) return reponse;
  const avecGenre = reponse.rows.map((ligne) => ({ ligne, genre: genreDeLigne(ligne.team) }));
  if (mode.afficherNoms === true) {
    return { ...reponse, rows: avecGenre.map(({ ligne, genre }) => ({ ...ligne, kind: genre })) };
  }
  const rang: Record<GenreDeLigne, number> = { product: 0, no_team: 1, team: 2 };
  // The key is computed once per row, then the rows are sorted (stable).
  const cles = avecGenre.map((e) => ({ ...e, id: e.genre === "team" ? identifiantEquipe(e.ligne.team as string) : "" }));
  cles.sort((a, b) => rang[a.genre] - rang[b.genre] || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return {
    ...reponse,
    columns: reponse.columns.filter((c) => c !== "team"),
    rows: cles.map(({ ligne, genre }) => ({ ...Object.fromEntries(Object.entries(ligne).filter(([c]) => c !== "team")), kind: genre })),
  };
}

// The one entry for the answers of the panels of the product-scope dashboard (task 37.1, D34 point 7). The panel already holds the dataset
// code (the panel functions set it); on real data the answer is reduced to its header and the `reduced_form` code: no point, no total, no
// count, no share of a count.
// Replaces: nothing. Removal: with the end of the exception (D34 point 6), when reduitEnMode is always false.
export function servirPanneau(panneau: PanneauComplet, mode: ModeDonnees): PanneauComplet | PanneauReduit {
  return reduitEnMode(mode) ? reduceToStatistics(panneau) : panneau;
}
