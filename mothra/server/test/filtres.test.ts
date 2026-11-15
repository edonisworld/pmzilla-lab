// Task 31.1 (author's decision R-20261030-54): outside the schema (undeclared field, missing from or to) answers 400 INVALID_REQUEST;
// several teams or a malformed identifier answers 422 SCOPE_INVALID; a bad range answers 422 RANGE_INVALID. A code only, no text.
import assert from "node:assert/strict";
import { test } from "node:test";

import Fastify from "fastify";
import Type from "typebox";

import { SchemaQueryFiltres, SchemaRefusFiltres, repondreHorsSchema, lireFiltres } from "../src/routes/filtres.ts";

async function appel(url: string) {
  const app = Fastify({ ajv: { customOptions: { removeAdditional: false } } });
  app.setErrorHandler(repondreHorsSchema);
  app.get(
    "/api/essai",
    {
      schema: {
        querystring: SchemaQueryFiltres,
        response: {
          200: Type.Object({ periods: Type.Array(Type.String()) }),
          400: Type.Object({ error: Type.Literal("INVALID_REQUEST") }, { additionalProperties: false }),
          422: SchemaRefusFiltres,
        },
      },
    },
    async (requete, reponse) => {
      const r = lireFiltres(requete.query, "2026-11-19");
      if (!r.ok) return reponse.code(r.status).send({ error: r.code });
      return { periods: r.periods };
    },
  );
  const reponse = await app.inject({ method: "GET", url });
  await app.close();
  return { statut: reponse.statusCode, corps: reponse.json() as Record<string, unknown> };
}

test("the product over a closed range answers 200", async () => {
  const r = await appel("/api/essai?from=2026-Q2&to=2026-Q3");
  assert.equal(r.statut, 200);
  assert.deepEqual(r.corps, { periods: ["2026-Q2", "2026-Q3"] });
});

test("an undeclared field or a missing from or to answers 400 INVALID_REQUEST", async () => {
  for (const q of ["sort=asc&from=2026-Q2&to=2026-Q3", "foo=1&from=2026-Q2&to=2026-Q3", "to=2026-Q3", "from=2026-Q2", ""]) {
    const r = await appel(`/api/essai?${q}`);
    assert.equal(r.statut, 400);
    assert.deepEqual(r.corps, { error: "INVALID_REQUEST" });
  }
});

test("a repeated team, a list of teams and a malformed identifier answer 422 SCOPE_INVALID", async () => {
  for (const q of ["team=a&team=b", "team=a,b", "team=a%20b"]) {
    const r = await appel(`/api/essai?${q}&from=2026-Q2&to=2026-Q3`);
    assert.equal(r.statut, 422);
    assert.deepEqual(r.corps, { error: "SCOPE_INVALID" });
  }
});

test("a running quarter, an inverted range and a range outside the retained year answer 422 RANGE_INVALID", async () => {
  for (const q of ["from=2026-Q4&to=2026-Q4", "from=2025-Q2&to=2026-Q3", "from=2025-Q4&to=2026-Q3", "from=2026-Q3&to=2026-Q2", "from=2020-Q1&to=2020-Q4"]) {      // 2025-Q4 to 2026-Q3 is four quarters: refused since R-20261114-49
    const r = await appel(`/api/essai?${q}`);
    assert.equal(r.statut, 422);
    assert.deepEqual(r.corps, { error: "RANGE_INVALID" });
  }
});
