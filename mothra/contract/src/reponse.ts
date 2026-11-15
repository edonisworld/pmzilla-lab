// The answer of the view route (mothra-slices D7), shared by the server and the front: one TypeBox schema, published as
// contrats/schemas/reponse-vue.schema.json, and the TypeScript type `ReponseVue` derived from it. `columns` is the list of column codes
// (a code, never a label); a count column holds a structured cell, any other column a plain value.
// The generic schema (rows of any column) is the published one; the server builds the strict schema of each served view from the
// contract with `schemaReponseDeVue` (the columns of the view and nothing else, a literal view name).
import Type from "typebox";
import type { Static, TSchema } from "typebox";
import Value from "typebox/value";

import {
  colonneAvecZero,
  SchemaCelluleAnciens,
  SchemaCelluleMasquee,
  SchemaCelluleMesure,
  SchemaCelluleMesuree,
  SchemaCelluleValeur,
} from "./cellule.ts";
import type { Cellule } from "./cellule.ts";
import { PLANCHER } from "./plancher.ts";
import type { Vue } from "./vues.ts";

export type ValeurSimple = string | number | null;
export type LigneReponse = Record<string, Cellule | ValeurSimple>;

// The `kind` of a row of a by-team view served by the generic route (R-20261109-21): the product row, the row of the items without a team, or
// a team. It is the only way to recognise a row: it holds no name and derives from none, and the order alone is not enough (the product row
// can be masked and absent, H-05). A view with no column `team` has no notion of team: its rows carry no `kind`.
export type GenreDeLigne = "product" | "no_team" | "team";

const SchemaGenreDeLigne = Type.Union([Type.Literal("product"), Type.Literal("no_team"), Type.Literal("team")]);

const SchemaValeurSimple = Type.Union([Type.String(), Type.Number(), Type.Null()]);

// A flat union (the two branches of a cell, then the plain kinds): the published file lists them side by side.
export const SchemaValeurDeLigne = Type.Union([
  SchemaCelluleValeur,
  SchemaCelluleMesure,
  SchemaCelluleMasquee,
  Type.String(),
  Type.Number(),
  Type.Null(),
]);

export const SchemaReponseVue = Type.Object(
  {
    view: Type.String(),
    threshold: Type.Integer({ minimum: PLANCHER }),
    columns: Type.Array(Type.String()),
    rows: Type.Array(Type.Object({}, { additionalProperties: SchemaValeurDeLigne })),
    sources: Type.Array(Type.String()),
  },
  { additionalProperties: false },
);

export type ReponseVue = Omit<Static<typeof SchemaReponseVue>, "rows"> & { rows: LigneReponse[] };

// Guard of the answer: the schema check, typed as the contract's ReponseVue.
export function estReponseVue(x: unknown): x is ReponseVue {
  // Check proves Static<schema> (rows: object[]); ReponseVue narrows rows to LigneReponse[] (the override above): this predicate is the one conversion.
  return Value.Check(SchemaReponseVue, x);
}

// The strict schema of the answer for one view of the contract: its columns and nothing else in a row, a count column as a cell, a
// plain column as a plain value, the view name as a literal.
// A view with a column `team` also declares `kind`, REQUIRED (R-20261109-22): the route always sets it, names shown or not. With
// `sansNom`, the column `team` is left out of the row (names off) and `kind` stays (R-20261109-21).
export function schemaReponseDeVue(vue: Vue, options: { sansNom?: boolean } = {}): TSchema {
  const proprietes: Record<string, TSchema> = {};
  for (const nom of vue.plainColumns) {
    if (options.sansNom === true && nom === "team") continue;
    proprietes[nom] = SchemaValeurSimple;
  }
  if (vue.plainColumns.includes("team")) {
    proprietes.kind = SchemaGenreDeLigne;
  }
  for (const nom of vue.countColumns) {
    proprietes[nom] = colonneAvecZero(vue.name, nom) ? SchemaCelluleAnciens : Type.Union([SchemaCelluleValeur, SchemaCelluleMasquee]);
  }
  for (const nom of vue.maskableColumns ?? []) {
    proprietes[nom] = SchemaCelluleMesuree;
  }
  return Type.Object(
    {
      view: Type.Literal(vue.name),
      threshold: Type.Integer({ minimum: PLANCHER }),
      columns: Type.Array(Type.String()),
      rows: Type.Array(Type.Object(proprietes, { additionalProperties: false })),
      sources: Type.Array(Type.String()),
    },
    { additionalProperties: false },
  );
}
