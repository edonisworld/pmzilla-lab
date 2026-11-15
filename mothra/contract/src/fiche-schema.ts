// Request and response schemas of the sheet routes (design D29, task 18.1): one data layer, the server imports them from here.
// The request schemas declare no verdict field and refuse any undeclared field (additionalProperties false); the response schema lists
// the fields the screen reads and nothing else, so a field a service result holds beyond them is not serialized.
import Type from "typebox";
import type { Static } from "typebox";

import { SchemaCellule } from "./cellule.ts";
import { SchemaLigneTrimestre, SchemaMesure, SchemaPointTrimestre } from "./lead-cycle.ts";
import { CODES_JEU_DE_DONNEES, CONSTATS_DE_VERDICT, ETATS_COUVERTURE, GRAPHIQUES_DE_FICHE, POSITIONS_DEBIT, QUESTIONS_DE_DIRECTION } from "./listes-fiche.ts";
import type { GraphiqueDeFiche, QuestionDeDirection } from "./listes-fiche.ts";

// The list lives in listes-fiche.ts (the browser-safe subpath); re-exported here so that the server keeps one import.
export { QUESTIONS_DE_DIRECTION };
export type { QuestionDeDirection };

const Ferme = { additionalProperties: false } as const;

export const SchemaTexteLibre = Type.Object({ text: Type.String(), lang: Type.Union([Type.Literal("fr"), Type.Literal("en")]) }, Ferme);

// The four management questions of design D19: a closed list (listes-fiche.ts). A sheet answers one of them, chosen at creation; the
// review asks for it.
// `Type.Unsafe` gives the static type: a union built by `.map` over the list loses its literal members (the type resolved to nothing).
export const SchemaQuestionDeDirection = Type.Unsafe<QuestionDeDirection>(Type.Union(QUESTIONS_DE_DIRECTION.map((q) => Type.Literal(q))));

// POST /api/sheets: the chart, the scope (a code) and the data date, the management question, and the two written texts when the author
// writes them at creation. The forms are those the columns accept (migrations 0024 and 0027): a code is never a free text.
export const SchemaCreationFiche = Type.Object(
  {
    chart: Type.Unsafe<GraphiqueDeFiche>(Type.Union(GRAPHIQUES_DE_FICHE.map((g) => Type.Literal(g)))),
    scope: Type.String({ pattern: "^[a-z0-9_.-]{1,64}$" }),
    dataDate: Type.String({ pattern: "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" }),
    managementQuestion: Type.Optional(SchemaQuestionDeDirection),
    effect: Type.Optional(SchemaTexteLibre),
    cause: Type.Optional(SchemaTexteLibre),
  },
  Ferme,
);
export type CreationFiche = Static<typeof SchemaCreationFiche>;

// PATCH /api/sheets/:id: what the author completes on a draft, any of the three; no other field, no verdict.
export const SchemaModificationFiche = Type.Object(
  { managementQuestion: Type.Optional(SchemaQuestionDeDirection), effect: Type.Optional(SchemaTexteLibre), cause: Type.Optional(SchemaTexteLibre) },
  Ferme,
);
export type ModificationFiche = Static<typeof SchemaModificationFiche>;

// POST /api/thresholds: the date is optional in the schema on purpose, so that its absence is THRESHOLD_INCOMPLETE (D21, 422) and not a schema
// violation. There is no author field: the author of a threshold is the user of the header `x-mothra-user`, never a value of the body.
export const SchemaEntreeSeuil = Type.Object(
  { code: Type.String(), value: Type.Number(), setOn: Type.Optional(Type.String()) },
  Ferme,
);
export type EntreeSeuilRequete = Static<typeof SchemaEntreeSeuil>;

export const SchemaSeuilEnregistre = Type.Object({ code: Type.String(), value: Type.Number(), setOn: Type.String() }, Ferme);
export const SchemaReponseSeuils = Type.Object({ thresholds: Type.Array(SchemaSeuilEnregistre) }, Ferme);

const SchemaPart = Type.Union([
  Type.Object({ state: Type.Literal("value"), value: Type.Number() }, Ferme),
  Type.Object({ state: Type.Literal("masked"), threshold: Type.Integer() }, Ferme),
  Type.Object({ state: Type.Literal("insufficient_sample") }, Ferme),
]);

const SchemaCelluleMasqueeFiche = Type.Object({ state: Type.Literal("masked"), threshold: Type.Integer() }, Ferme);
const EtatExplication = Type.Union([Type.Literal("ruled_out"), Type.Literal("not_ruled_out"), Type.Literal("not_measurable")]);

// The fields of the method face the full form and the reduced form share; the coverage is the count (full) or the state (reduced, D34).
const champsMethode = {
    method: Type.String(),
    scope: Type.Object({ level: Type.Union([Type.Literal("team"), Type.Literal("product")]), id: Type.String() }, Ferme),
    period: Type.Object(
      { quarters: Type.Array(Type.Object({ year: Type.Integer(), quarter: Type.Union([Type.Literal(1), Type.Literal(2), Type.Literal(3), Type.Literal(4)]) }, Ferme)) },
      Ferme,
    ),
    thresholds: Type.Array(
      Type.Object(
        {
          code: Type.String(),
          value: Type.Number(),
          fixedOn: Type.String(),
          fixedBy: Type.Literal("author_alone"),
          modifiedAfterReading: Type.Optional(Type.Object({ formerValue: Type.Number(), formerDate: Type.String() }, Ferme)),
        },
        Ferme,
      ),
    ),
    thresholdsFixedOn: Type.String(),
    dataDate: Type.String(),
    fingerprint: Type.String(),
    maskedCells: Type.Array(Type.Object({ measure: Type.String(), cell: SchemaCelluleMasqueeFiche }, Ferme)),
    insufficientSamples: Type.Array(Type.String()),
    excluded: Type.Object({ median: Type.Array(Type.Integer()), p85: Type.Array(Type.Integer()), throughput: Type.Array(Type.Integer()) }, Ferme),
    limits: Type.Array(Type.String()),
    authorRole: Type.String(),
    version: Type.Integer(),
    hypothesis: Type.String(),
};

const SchemaMethode = Type.Object({ ...champsMethode, coverage: SchemaCellule }, Ferme);
const SchemaCouverture = Type.Union(ETATS_COUVERTURE.map((e) => Type.Literal(e)));
const SchemaMethodeReduite = Type.Object({ ...champsMethode, coverageState: SchemaCouverture }, Ferme);

const SchemaDataset = Type.Union(CODES_JEU_DE_DONNEES.map((e) => Type.Literal(e)));
const SchemaPositionDebit = Type.Union(POSITIONS_DEBIT.map((p) => Type.Literal(p)));
// Task 19.5: the P85 of the quarters, the positions of the throughput (F-H5), the ratios of the first half of hypothesis 1 (F-H1).
const SchemaP85 = Type.Object({ quarters: Type.Array(SchemaPointTrimestre), pooledYear: Type.Optional(SchemaPointTrimestre) }, Ferme);
const SchemaPositions = Type.Array(Type.Object({ quarter: Type.String(), position: SchemaPositionDebit }, Ferme));
const SchemaRapportTrimestre = Type.Object({ quarter: Type.String(), median: SchemaMesure, p85: SchemaMesure }, Ferme);
const SchemaRapports = Type.Object({ quarters: Type.Array(SchemaRapportTrimestre), pooledYear: Type.Optional(SchemaRapportTrimestre) }, Ferme);

// The bars of the share of waiting of hypothesis 1 (mothra-demo-habillage D3b): the median and P85 bars and the two threshold markers, as
// `partsDAttente` of the contract gives them. Optional in both answers; no count in it, so the reduced form keeps it.
const SchemaBarreAttente = Type.Union([
  Type.Object({ state: Type.Literal("value"), ratio: Type.Number(), waitShare: Type.Number(), workShare: Type.Number() }, Ferme),
  Type.Object({ state: Type.Literal("masked"), threshold: Type.Integer() }, Ferme),
  Type.Object({ state: Type.Literal("insufficient_sample") }, Ferme),
  Type.Object({ state: Type.Literal("not_comparable") }, Ferme),
]);
const SchemaRepereAttente = Type.Object({ ratio: Type.Number(), inScale: Type.Boolean(), share: Type.Optional(Type.Number()) }, Ferme);
const SchemaPartsDAttente = Type.Object(
  {
    median: SchemaBarreAttente,
    p85: SchemaBarreAttente,
    markers: Type.Object({ refutation: SchemaRepereAttente, confirmation: SchemaRepereAttente, applicable: Type.Boolean() }, Ferme),
  },
  Ferme,
);

// The answer of GET /api/sheets/:id and of the review and publication routes. The effect and the cause are present when written.
const champsReponseCommuns = {
  id: Type.String(),
  state: Type.Union([Type.Literal("draft"), Type.Literal("reviewed"), Type.Literal("published")]),
  publishedOn: Type.Optional(Type.String()),
  managementQuestion: Type.Optional(SchemaQuestionDeDirection),
  effect: Type.Optional(SchemaTexteLibre),
  cause: Type.Optional(SchemaTexteLibre),
  verdict: Type.String(),
  verdictReasons: Type.Array(Type.Object({ explanation: Type.String(), state: EtatExplication, reason: Type.String() }, Ferme)),
  h1Reasons: Type.Array(Type.String()),
  h5Reasons: Type.Array(Type.String()),
  verdictFindings: Type.Optional(Type.Array(Type.Union(CONSTATS_DE_VERDICT.map((c) => Type.Literal(c))))),
  attachmentSignal: Type.Union([Type.Literal("raised"), Type.Literal("not_raised")]),
  attachmentSignalReasons: Type.Array(Type.String()),
  attachmentSignalShown: Type.Boolean(),
  p85: Type.Optional(SchemaP85),
  throughputPositions: Type.Optional(SchemaPositions),
  ratios: Type.Optional(SchemaRapports),
  waitShares: Type.Optional(SchemaPartsDAttente),
  dataset: Type.Optional(SchemaDataset),
};

export const SchemaReponseFiche = Type.Object(
  {
    ...champsReponseCommuns,
    explanations: Type.Array(
      Type.Object({ name: Type.String(), state: EtatExplication, reason: Type.Optional(Type.String()), measure: Type.Optional(SchemaPart) }, Ferme),
    ),
    chart: Type.Optional(Type.Object({ quarters: Type.Array(SchemaLigneTrimestre), pooledYear: Type.Optional(SchemaLigneTrimestre) }, Ferme)),
    unplannedProductShare: Type.Optional(SchemaPart),
    tasksWithoutTeamShare: Type.Optional(SchemaPart),
    method: SchemaMethode,
  },
  Ferme,
);

// The answer on real data (D34 point 2, task 19.5): the same fields without any count field. The explanations carry no measure, the chart
// points no `items`, there is no share of a count and the method face holds the coverage state, not the coverage. The route registers this
// schema when the dataset is real and REAL_DATA_COUNTS_ALLOWED is false, so a count the service hands over is omitted whatever it does.
export const SchemaReponseFicheReduite = Type.Object(
  {
    ...champsReponseCommuns,
    explanations: Type.Array(Type.Object({ name: Type.String(), state: EtatExplication, reason: Type.Optional(Type.String()) }, Ferme)),
    chart: Type.Optional(Type.Object({ quarters: Type.Array(SchemaPointTrimestre), pooledYear: Type.Optional(SchemaPointTrimestre) }, Ferme)),
    method: SchemaMethodeReduite,
  },
  Ferme,
);

// A draft or reviewed sheet whose data date is no longer in the current UTC quarter (audit #629, A-66, R-20261112-30): what the author wrote
// and `bodyState` DATA_DATE_STALE (design D29), no body (no verdict, no figure). The only field this answer adds to the sheet is `bodyState`.
// Replaces: nothing. Removal: permanent (R-20261112-30).
export const SchemaFicheSansCorps = Type.Object(
  {
    id: Type.String(),
    state: Type.Union([Type.Literal("draft"), Type.Literal("reviewed")]),
    managementQuestion: Type.Optional(SchemaQuestionDeDirection),
    effect: Type.Optional(SchemaTexteLibre),
    cause: Type.Optional(SchemaTexteLibre),
    bodyState: Type.Literal("DATA_DATE_STALE"),
  },
  Ferme,
);
export type FicheSansCorps = Static<typeof SchemaFicheSansCorps>;

// The sheets of one state (audit #629, A-04): `GET /api/sheets?state=…`, so that a reviewer finds the drafts and a publisher the reviewed sheets.
// One entry per sheet: the opaque identifier, the kind, the scope code (`team.<opaque identifier>`), the data date, the state. No written text,
// no verdict, no count, no author: nothing a list needs beyond finding the sheet. The server bounds the list (newest first).
export const SchemaEtatDeListe = Type.Object(
  { state: Type.Union([Type.Literal("draft"), Type.Literal("reviewed"), Type.Literal("published")]) },
  Ferme,
);
export type EtatDeListe = Static<typeof SchemaEtatDeListe>["state"];

export const SchemaListeFiches = Type.Object(
  {
    sheets: Type.Array(
      Type.Object(
        {
          id: Type.String(),
          chart: Type.String(),
          scope: Type.String(),
          dataDate: Type.String(),
          state: Type.Union([Type.Literal("draft"), Type.Literal("reviewed"), Type.Literal("published")]),
        },
        Ferme,
      ),
    ),
  },
  Ferme,
);

// The refusal of a written text (D20): the field, the reason, and the count and the maximum with `too_long` only.
export const SchemaTexteRefuse = Type.Object(
  {
    error: Type.Literal("TEXT_REFUSED"),
    field: Type.Union([Type.Literal("effect"), Type.Literal("cause")]),
    reason: Type.Union([Type.Literal("ticket_key"), Type.Literal("email"), Type.Literal("sensitive_name"), Type.Literal("too_long")]),
    count: Type.Optional(Type.Integer()),
    max: Type.Optional(Type.Integer()),
  },
  Ferme,
);
export type TexteRefuse = Static<typeof SchemaTexteRefuse>;
