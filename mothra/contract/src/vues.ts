// The shape of the views contract (mothra-slices D2), published as contrats/schemas/vues.schema.json.
// The floor of five is not a schema rule: a threshold under it is a distinct refusal (CONTRACT_FLOOR), decided by the loader.
import Type from "typebox";
import type { Static } from "typebox";

const IDENTIFIANT = "^[a-z][a-z0-9_]*$";
const GENRE_DE_ROLE = "^(flow|quality)$";

const SchemaVue = Type.Object(
  {
    name: Type.String({ pattern: IDENTIFIANT }),
    schema: Type.String({ pattern: GENRE_DE_ROLE }),
    roleKind: Type.String({ pattern: GENRE_DE_ROLE }),
    countColumns: Type.Array(Type.String({ pattern: IDENTIFIANT }), { minItems: 1 }),
    plainColumns: Type.Array(Type.String({ pattern: IDENTIFIANT })),
    // Statistics and shares of a view (a median, a P85, a percentage): numbers masked with their count, served as a cell (R-20261030-49).
    maskableColumns: Type.Optional(Type.Array(Type.String({ pattern: IDENTIFIANT }))),
  },
  { additionalProperties: false },
);

export const SchemaVues = Type.Object(
  {
    minThreshold: Type.Optional(Type.Integer({ minimum: 0 })),
    views: Type.Array(SchemaVue, { minItems: 1 }),
  },
  { additionalProperties: false },
);

export type Vue = Static<typeof SchemaVue>;
export type Contrat = Static<typeof SchemaVues>;
