// The answer of the dashboard "lead time against cycle time" (design D19, D24) and the request that makes a sheet of it (D29).
// One data layer (D30, task 18.0): the server and the front import these types from the contract package only.
// A median or a P85 is a measure with three states: a value, a masked cell (under the confidentiality threshold, D22) or an
// insufficient sample (under the reliability threshold, D22). A masked or insufficient measure carries no value at all.
import Type from "typebox";
import type { Static } from "typebox";

import { SchemaCellule } from "./cellule.ts";
import { MOTIF_IDENTIFIANT_EQUIPE } from "./equipe.ts";
import { celluleDe, celluleOuMasquee, mesureDeStatistique, texteDe } from "./lecture-vue.ts";
import type { ReponseVue } from "./reponse.ts";
import { etiquetteTrimestre } from "./trimestres.ts";
import type { ConfigEchantillon } from "./verdict.ts";

export const SchemaMesure = Type.Union([
  Type.Object({ state: Type.Literal("value"), value: Type.Number() }, { additionalProperties: false }),
  Type.Object({ state: Type.Literal("masked"), threshold: Type.Integer() }, { additionalProperties: false }),
  Type.Object({ state: Type.Literal("insufficient_sample") }, { additionalProperties: false }),
]);
export type Mesure = Static<typeof SchemaMesure>;

export const SchemaPointTrimestre = Type.Object(
  { quarter: Type.String(), lead: SchemaMesure, cycle: SchemaMesure },
  { additionalProperties: false },
);
export type PointTrimestre = Static<typeof SchemaPointTrimestre>;

// A quarter's point with the count of items: the contract's cell (a value or a masked cell).
export const SchemaLigneTrimestre = Type.Object(
  { quarter: Type.String(), lead: SchemaMesure, cycle: SchemaMesure, items: SchemaCellule },
  { additionalProperties: false },
);
export type LigneTrimestre = Static<typeof SchemaLigneTrimestre>;

export const SchemaSerieEquipe = Type.Object(
  // `teamId`: the opaque identifier derived from the name (`identifiantEquipe`), the one the filters and the sheet scope use.
  // `team` is optional (D35, R-20261104-36 N1 (a)): the service layer leaves it out unless the server's setting MOTHRA_SHOW_TEAM_NAMES is on.
  { team: Type.Optional(Type.String()), teamId: Type.String({ pattern: MOTIF_IDENTIFIANT_EQUIPE.source }), points: Type.Array(SchemaLigneTrimestre) },
  { additionalProperties: false },
);
export type SerieEquipe = Static<typeof SchemaSerieEquipe>;

export const SchemaReponseLeadCycle = Type.Object(
  {
    threshold: Type.Integer(),
    dataDate: Type.String(),
    product: Type.Array(SchemaLigneTrimestre),
    teams: Type.Array(SchemaSerieEquipe),
    // `real` or `synthetic`, set by the service layer on every answer (D34, task 19.6); the front shows the notice from it.
    dataset: Type.Optional(Type.Union([Type.Literal("synthetic"), Type.Literal("real")])),
  },
  { additionalProperties: false },
);
export type ReponseLeadCycle = Static<typeof SchemaReponseLeadCycle>;

// The reduced answer of the dashboard on real data (D34 point 7, task 19.6): medians with their states, no count field at all, so that a
// count the service hands over is omitted by the serializer (task 6.4 rule). Chosen at the registration of the route, never at formatting.
export const SchemaSerieEquipeReduite = Type.Object(
  { team: Type.Optional(Type.String()), teamId: Type.String({ pattern: MOTIF_IDENTIFIANT_EQUIPE.source }), points: Type.Array(SchemaPointTrimestre) },
  { additionalProperties: false },
);
export const SchemaReponseLeadCycleReduite = Type.Object(
  {
    threshold: Type.Integer(),
    dataDate: Type.String(),
    product: Type.Array(SchemaPointTrimestre),
    teams: Type.Array(SchemaSerieEquipeReduite),
    // `real` or `synthetic`: set by the service layer on every answer (D34).
    dataset: Type.Optional(Type.Union([Type.Literal("synthetic"), Type.Literal("real")])),
  },
  { additionalProperties: false },
);
export type ReponseLeadCycleReduite = Static<typeof SchemaReponseLeadCycleReduite>;

// The label of the pooled-year point of a team's series (the three closed quarters shown together: « Last three quarters », R-20261114-49; the
// identifier keeps its name, renaming it would change existing tests beyond the move from four quarters to three).
export const ETIQUETTE_ANNEE_GROUPEE = "pooled_year";

// The dashboard from the masked answer of v_team_lead_time_throughput (task 18.4, D30): the only function that builds the figures of the
// dashboard, and the one the sheet takes its chart from, so a figure of the sheet never differs from its dashboard figure. A median is
// a value, a masked cell or an insufficient sample (the headcount of the same line against the reliability size of D22); the headcount
// of a point is the cycle time one. Nothing is estimated: a masked cell stays the masked cell of the view. The view has no product
// line, so `product` is empty (a product line would need a sum of masked cells). Pure; the answer is already masked.
// `identifiant` turns a team name of the view into the opaque team identifier (identifiantEquipe of the contract, R-20261030-61): the
// caller gives it (a test may give a declared double), so that each series carries its required `teamId`.
export function tableauLeadCycle(
  reponse: ReponseVue,
  config: ConfigEchantillon,
  dataDate: string,
  identifiant: (nom: string) => string,
): ReponseLeadCycle {
  const parEquipe = new Map<string, Array<{ ordre: string; point: LigneTrimestre }>>();
  for (const ligne of reponse.rows) {
    const equipe = texteDe(ligne, "team");
    const periode = texteDe(ligne, "period");
    if (equipe === null || periode === null) {
      continue;
    }
    const debut = texteDe(ligne, "quarter_start");
    let etiquette: string;
    let ordre: string;
    if (periode === "pooled_year") {
      etiquette = ETIQUETTE_ANNEE_GROUPEE;
      ordre = "9999-99-99";
    } else if (debut !== null) {
      etiquette = etiquetteTrimestre(debut);
      ordre = debut;
    } else {
      continue;
    }
    const seuil = reponse.threshold;
    const point: LigneTrimestre = {
      quarter: etiquette,
      lead: mesureDeStatistique(celluleDe(ligne, "lead_median_days"), celluleDe(ligne, "items_lt"), config.medianMinItems, seuil),
      cycle: mesureDeStatistique(celluleDe(ligne, "cycle_median_days"), celluleDe(ligne, "items_ct"), config.medianMinItems, seuil),
      items: celluleOuMasquee(celluleDe(ligne, "items_ct"), seuil),
    };
    const liste = parEquipe.get(equipe) ?? [];
    liste.push({ ordre, point });
    parEquipe.set(equipe, liste);
  }
  // Internal computation: ordered by name. The order of the served answer (by identifier when the names are off, Q238, L3-08) is decided by
  // `servirTableau`, the one place where the answer goes out to the client.
  const teams: SerieEquipe[] = [...parEquipe.keys()]
    .sort()
    .map((team) => ({
      team,
      teamId: identifiant(team),
      points: (parEquipe.get(team) ?? []).sort((a, b) => (a.ordre < b.ordre ? -1 : a.ordre > b.ordre ? 1 : 0)).map((p) => p.point),
    }));
  return { threshold: reponse.threshold, dataDate, product: [], teams };
}

// The request of POST /api/sheets from a chart: the chart, the scope and the data date. It declares no verdict field.
export const SchemaDemandeFiche = Type.Object(
  { chart: Type.String(), scope: Type.String(), dataDate: Type.String() },
  { additionalProperties: false },
);
export type DemandeFiche = Static<typeof SchemaDemandeFiche>;

export const SchemaBrouillon = Type.Object(
  { id: Type.String(), state: Type.Literal("draft") },
  { additionalProperties: false },
);
export type Brouillon = Static<typeof SchemaBrouillon>;
