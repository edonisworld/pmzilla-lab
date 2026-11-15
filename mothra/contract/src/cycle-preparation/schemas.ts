// The answer and the request of the page "preparation of a cycle" (mothra-slices D35, task 40.1, R-169). One data layer (task 18.0): the
// server and the front import these types from the contract package only. Codes only, no text (invariant 11); the labels belong to the
// catalogues of the front (task 41.1).
// Option A: aggregated counts of one cycle, never a list of epics, never a key or a title. The domain line only (M3): the answer holds no
// collection indexed by team, and a team scope is refused with the existing code SCOPE_INVALID of the filters framework (task 31.1).
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the page leaves the product.
import Type from "typebox";
import type { Static } from "typebox";

import { SchemaCellule } from "../cellule.ts";
import { PLANCHER } from "../plancher.ts";

// The codes live in codes.ts (no typebox, reachable by the pure module); re-exported here so that the schemas and their tests keep one name.
import { CODE_COMPTES_REELS_MASQUES, CODE_DOMAINE_TROP_PETIT, MOTIF_CLE_CYCLE } from "./codes.ts";
export {
  CODES_AVIS,
  CODES_ETAT_PAGE,
  CODES_ETAT_VIDE,
  CODES_REFUS_PAGE,
  CODES_SOURCE_READY,
  CODE_COMPTES_REELS_MASQUES,
  CODE_DOMAINE_TROP_PETIT,
  MOTIF_CLE_CYCLE,
} from "./codes.ts";
export type { CodeAvis, CodeEtatPage, CodeEtatVide, CodeRefusPage, CodeSourceReady } from "./codes.ts";

export const SchemaRefusCyclePreparation = Type.Object(
  { error: Type.Union([Type.Literal("CYCLE_UNKNOWN"), Type.Literal("SCOPE_INVALID")]) },
  { additionalProperties: false },
);

// The request: a neutral cycle key and nothing else. Whether a key is offered is decided by `choisirCycle`; the pattern only bounds the
// characters. The team is read as unknown so that a repeated one reaches the scope check and answers 422 SCOPE_INVALID instead of a
// schema error (as in the filters framework).
const PATRON_CLE = MOTIF_CLE_CYCLE.source;
export const SchemaDemandeCyclePreparation = Type.Object(
  { cycle: Type.Optional(Type.String({ pattern: PATRON_CLE })), team: Type.Optional(Type.Unknown()) },
  { additionalProperties: false },
);
export type DemandeCyclePreparation = Static<typeof SchemaDemandeCyclePreparation>;

// ---- the answer --------------------------------------------------------------------------------------------------------------------
// A cycle offered by the selector: the neutral key and the dates, no count. Upcoming and running only.
export const SchemaCycleOffert = Type.Object(
  {
    key: Type.String({ pattern: PATRON_CLE }),
    start: Type.String(),
    end: Type.String(),
    state: Type.Union([Type.Literal("upcoming"), Type.Literal("running")]),
  },
  { additionalProperties: false },
);

// The Epic Review counts are partial evidence signals of hypothesis 4, never a verdict (D35).
const SchemaRevueEpics = Type.Object(
  {
    mentions: Type.Tuple([Type.Literal("partial_evidence_signals")]),
    inEpicReview: SchemaCellule,
    // Null while the mapping is not validated: a count within a column cannot be computed (see `cadrerSelonMapping`).
    candidates: Type.Union([SchemaCellule, Type.Null()]),
  },
  { additionalProperties: false },
);

// The summary of the cycle for the domain line: an indirect indicator (hypothesis 1). Every count is a structured cell (D3).
const SchemaResume = Type.Object(
  {
    mentions: Type.Tuple([Type.Literal("indirect_indicator")]),
    planned: SchemaCellule,
    ready: SchemaCellule,
    confirmedIn: SchemaCellule,
    declined: SchemaCellule,
    withoutConfirmation: SchemaCellule,
    replannedBeforeStart: SchemaCellule,
    epicReview: SchemaRevueEpics,
  },
  { additionalProperties: false },
);

// A column of the Discovery Workflow, or the row "status not mapped" (mapped false). The column is a code of the mapping, never a label.
const SchemaColonne = Type.Object(
  { column: Type.String({ minLength: 1, maxLength: 64 }), mapped: Type.Boolean(), count: SchemaCellule },
  { additionalProperties: false },
);

const entete = {
  threshold: Type.Integer({ minimum: PLANCHER }),
  dataDate: Type.String(),
  // The domain line only (M3): the one scope that exists.
  scope: Type.Literal("domain"),
  cycles: Type.Array(SchemaCycleOffert),
  cycle: Type.Union([Type.String({ pattern: PATRON_CLE }), Type.Null()]),
  // Always present (the code `dataset` is in every answer, task 40.3).
  dataset: Type.Union([Type.Literal("synthetic"), Type.Literal("real")]),
};
const SchemaAvis = Type.Literal("mapping_not_validated");

// The page is shown: a summary, the columns (empty while the mapping is not validated), the Ready source code.
export const SchemaReponseCycleAffichee = Type.Object(
  {
    ...entete,
    emptyState: Type.Null(),
    notices: Type.Array(SchemaAvis),
    readySource: Type.Union([Type.Literal("ready_source_label"), Type.Literal("ready_source_column")]),
    summary: SchemaResume,
    columns: Type.Array(SchemaColonne),
    // The total of the columns: a value only when no column cell is masked (computed by `totalDesCellules`, never by a route or a
    // component). Null when there is no column.
    columnsTotal: Type.Union([SchemaCellule, Type.Null()]),
  },
  { additionalProperties: false },
);

// An explained empty state: no count at all, no summary, no column, no total.
export const SchemaReponseCycleVide = Type.Object(
  {
    ...entete,
    emptyState: Type.Union([
      Type.Literal("no_cycle_configured"),
      Type.Literal("no_epic_for_cycle"),
      Type.Literal("no_label_history"),
      Type.Literal(CODE_DOMAINE_TROP_PETIT),
      Type.Literal(CODE_COMPTES_REELS_MASQUES),
    ]),
    notices: Type.Array(SchemaAvis, { maxItems: 0 }),
    readySource: Type.Null(),
    summary: Type.Null(),
    columns: Type.Array(SchemaColonne, { maxItems: 0 }),
    columnsTotal: Type.Null(),
  },
  { additionalProperties: false },
);

export const SchemaReponseCyclePreparation = Type.Union([SchemaReponseCycleAffichee, SchemaReponseCycleVide]);

export type ReponseCyclePreparation = Static<typeof SchemaReponseCyclePreparation>;
export type CycleOffert = Static<typeof SchemaCycleOffert>;
