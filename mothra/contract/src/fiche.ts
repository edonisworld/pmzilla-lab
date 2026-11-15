// The answer of an argument sheet (design D20, D21, D22, D29, D33) as the verdict service gives it. One data layer (D30, task 18.0):
// the server and the front import these types from the contract package only. The verdict, the states of the explanations, the signal
// and the shares are computed by the verdict service, never in a route or a component; there is no field to send a verdict.
import type { Cellule } from "./cellule.ts";
import type { QuestionDeDirection } from "./fiche-schema.ts";
import type { Mesure, PointTrimestre } from "./lead-cycle.ts";
import type { CodeJeuDeDonnees } from "./listes-fiche.ts";
import type { PartsDAttente } from "./parts-attente.ts";
import type {
  ConstatDeVerdict,
  EtatCouverture,
  EtatSignal,
  ExclusionsH5,
  Explication,
  LienId,
  MotifH1,
  MotifH5,
  MotifSignal,
  PositionDebit,
  RaisonVerdict,
  VerdictOuEchantillon,
} from "./verdict.ts";

// The masked cell of the contract: a state and a threshold, no value, no reason.
export type CelluleMasqueeContrat = Extract<Cellule, { state: "masked" }>;

export type EtatDeLaFiche ="draft" | "reviewed" | "published";

// Free text written by an Agile Lead, with the language it was written in (never guessed, never translated).
export interface TexteLibre {
  text: string;
  lang: "fr" | "en";
}

// A share is a percentage from 0 to 100, a masked cell of the contract, or an insufficient sample.
export type Part = { state: "value"; value: number } | CelluleMasqueeContrat | { state: "insufficient_sample" };

// An explanation with the measure it rests on (task 18.4, R-20261030-58 Q4): a cell or a share, masked as the view gave it.
export type ExplicationFiche = Explication & { measure?: Part };

// The figures of the chart, taken from the dashboard function (tableauLeadCycle): the quarters of the sheet and the pooled year.
// The count of items (`items`) is present in the full form only; the reduced form of D34 (reduceToStatistics) leaves it out.
export type PointDeFiche = PointTrimestre & { items?: Cellule };

export interface GraphiqueFiche {
  quarters: PointDeFiche[];
  pooledYear?: PointDeFiche;
}

// Task 19.5 (D34): the P85 of lead time and cycle time of the quarters of the sheet and of the pooled year, with their states, read as the
// dashboard reads the medians (mesureDeStatistique).
export interface StatistiquesP85 {
  quarters: PointTrimestre[];
  pooledYear?: PointTrimestre;
}

// Task 19.5 (D34): the ratios of the first half of hypothesis 1 (lead time over cycle time), median and P85, per quarter and for the pooled
// year, each a measure with its masked and insufficient states. A ratio is shown only when both of its terms are.
export interface RapportsTrimestre {
  quarter: string;
  median: Mesure;
  p85: Mesure;
}

export interface RapportsH1 {
  quarters: RapportsTrimestre[];
  pooledYear?: RapportsTrimestre;
}

export interface Seuil {
  code: string;
  value: number;
  fixedOn: string; // ISO date
  fixedBy: "author_alone";
  modifiedAfterReading?: { formerValue: number; formerDate: string };
}

export interface Trimestre {
  year: number;
  quarter: 1 | 2 | 3 | 4;
}

export interface MethodeFiche {
  method: string; // a method code, translated by the front
  scope: { level: "team" | "product"; id: string }; // an identifier, never a free text
  period: { quarters: Trimestre[] }; // the quarters of the sheet; the exclusions point into this list
  thresholds: Seuil[];
  thresholdsFixedOn: string; // ISO date
  dataDate: string; // ISO date
  fingerprint: string;
  // The coverage count: the full form only. The reduced form (D34) holds the coverage state instead, computed by the verdict service.
  coverage?: Cellule;
  coverageState?: EtatCouverture;
  maskedCells: Array<{ measure: string; cell: CelluleMasqueeContrat }>;
  insufficientSamples: string[]; // measure codes
  excluded: ExclusionsH5; // positions in `period.quarters`, as the service lists them
  limits: string[]; // limit codes, translated by the front
  authorRole: string; // a role code, never a name
  version: number;
  hypothesis: LienId;
}

export interface CorpsFiche {
  id: string;
  // As SchemaReponseFiche: a draft may be created without them and completed later (design D29).
  managementQuestion?: QuestionDeDirection;
  effect?: TexteLibre;
  cause?: TexteLibre;
  verdict: VerdictOuEchantillon;
  verdictReasons: RaisonVerdict[];
  h1Reasons: MotifH1[];
  h5Reasons: MotifH5[];
  // Audit #629, A-01 (Q6): why the verdict is what it is, as codes (the sentence under the badge). Given by the verdict functions at each
  // computation. Optional: a version frozen before this field holds none, and the page then tells nothing rather than guess.
  verdictFindings?: ConstatDeVerdict[];
  explanations: ExplicationFiche[];
  // Optional so that a body without chart figures stays valid; the computed body always carries it.
  chart?: GraphiqueFiche;
  // Context only, never the team's measure: the product share of unplanned work, labelled "product level".
  unplannedProductShare?: Part;
  attachmentSignal: EtatSignal;
  attachmentSignalReasons: MotifSignal[];
  attachmentSignalShown: boolean;
  tasksWithoutTeamShare?: Part; // product level, attributed to no team
  // Task 19.5: the P85 of the quarters, the position of each quarter's throughput (F-H5 only, kept in the reduced form), the ratios of
  // the first half of hypothesis 1 (F-H1 only).
  p85?: StatistiquesP85;
  throughputPositions?: Array<{ quarter: string; position: PositionDebit }>;
  ratios?: RapportsH1;
  // mothra-demo-habillage D3b (R-20261101-20): the bars of the share of waiting, given by `partsDAttente` in the server's service layer at each
  // reading, never stored. Absent on a hypothesis 5 answer and on any answer built without the service layer (a frozen version holds none).
  waitShares?: PartsDAttente;
  // Task 19.5/19.6: `real` or `synthetic`, set by the service layer on every answer; the front shows `synthetic_dataset_notice` from it.
  dataset?: CodeJeuDeDonnees;
  method: MethodeFiche;
}

// A published sheet carries its publication date (ISO date); a draft or a reviewed sheet carries none.
export type EtatEtDatePublication = { state: "draft" | "reviewed"; publishedOn?: undefined } | { state: "published"; publishedOn: string };

export type ReponseFiche = CorpsFiche & EtatEtDatePublication;

// What a review or a publication gives back: success, or the code of the refusal (SELF_REVIEW_REFUSED, NOT_REVIEWED, VERSION_FROZEN, D29).
export type ResultatAction = { ok: true } | { ok: false; code: string };
