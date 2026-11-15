// The shared filters of the second screen's routes (mothra-slices D35, task 31.1): the querystring schema and the refusals.
// Outside the schema (undeclared field, missing from or to, wrong type): 400 INVALID_REQUEST (D29). Several teams or a malformed
// identifier: 422 SCOPE_INVALID. A bad range: 422 RANGE_INVALID (author's decision R-20261030-54). Codes only, no text.
// The check itself is `verifierFiltres` of the contract package; this file only wires it to a route.
import { SchemaFiltres, verifierFiltres } from "@mothra/contract";
import type { ResultatFiltres } from "@mothra/contract";
import type { FastifyReply, FastifyRequest } from "fastify";
import Type from "typebox";

// The querystring of a route that takes the filters: the contract's schema, the one source (no second schema).
export const SchemaQueryFiltres = SchemaFiltres;

export const SchemaRefusFiltres = Type.Object(
  { error: Type.Union([Type.Literal("SCOPE_INVALID"), Type.Literal("RANGE_INVALID")]) },
  { additionalProperties: false },
);

// The error handler for a request outside its schema: 400 and the code, never the framework's text. Any other error is left to the
// server's own handler (500 INTERNAL).
export function repondreHorsSchema(erreur: { validation?: unknown }, requete: FastifyRequest, reponse: FastifyReply): FastifyReply {
  if (erreur.validation !== undefined) {
    return reponse.code(400).send({ error: "INVALID_REQUEST" });
  }
  requete.log.error({ code: "INTERNAL" }, "request failed");
  return reponse.code(500).send({ error: "INTERNAL" });
}

// Today's date, `YYYY-MM-DD`, from the server's clock (injected by the caller in tests). It is the UTC date: in Paris, between 0 h and
// 2 h on the first day of a quarter, the quarter that just ended is still refused. This errs on the safe side (a refusal, never a
// running period accepted).
export function aujourdhui(maintenant: Date = new Date()): string {
  return maintenant.toISOString().slice(0, 10);
}

// The refusal to send (status 422 and `{ error: code }`), or the accepted filters.
export function lireFiltres(query: unknown, today: string): ResultatFiltres {
  return verifierFiltres(query, { today });
}
