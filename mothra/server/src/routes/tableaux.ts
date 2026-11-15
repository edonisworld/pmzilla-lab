// The route of the dashboard "lead time against cycle time" (design D24, D29 additions of 2026-10-31, task 19.6): `GET /api/dashboards/lead_cycle`
// answers `ReponseLeadCycle` of the contract, or its reduced form on real data. Every answer of a dashboard goes through `servirTableau` of
// the service layer (a static test checks it): the route decides nothing and formats nothing. The response schema is chosen at the
// registration, from the mode fixed at the start, so a count the service hands over is omitted whatever it does (task 6.4 rule).
// Codes only in the answers; the log holds a code.
import { SchemaReponseLeadCycle, SchemaReponseLeadCycleReduite, SeuilsNonFixes } from "@mothra/contract";
import type { ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";
import type { FastifyError, FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import Type from "typebox";

import { BaseIndisponible } from "../db/acces.ts";
import { reduitEnMode, servirTableau } from "../service.ts";
import type { ModeDonnees } from "../service.ts";
import { nettoyer } from "./serveur.ts";

export const ROUTE_TABLEAU_LEAD_CYCLE = "/api/dashboards/lead_cycle";

export interface OptionsTableaux {
  // The answer of the dashboard from the views (the contract's function over the masked answer): complete, never reduced here.
  calculerTableau(): Promise<ReponseLeadCycle>;
  // The dataset and the constant of the contract, fixed at the start.
  mode: ModeDonnees;
  // For the tests only: replaces the service entry, so that the reduced response schema can be tested alone (a port that hands a complete
  // answer, a service that does not reduce). The start never gives it: the entry is `servirTableau` of the service layer.
  servir?: (reponse: ReponseLeadCycle, mode: ModeDonnees) => ReponseLeadCycle | ReponseLeadCycleReduite;
  // Whether the route is switched off (the start check found a collision of team identifiers, D29, task 19.8); read at each request. Absent: on.
  desactivees?(): boolean;
}

const Erreur = <C extends string>(code: C) => Type.Object({ error: Type.Literal(code) }, { additionalProperties: false });

const gererErreur = (erreur: FastifyError, requete: FastifyRequest, reponse: FastifyReply) => {
  if (erreur instanceof SeuilsNonFixes) {
    requete.log.error({ code: "THRESHOLDS_NOT_SET" }, "request refused");
    return reponse.code(409).send({ error: "THRESHOLDS_NOT_SET" });
  }
  const statut = erreur.statusCode;
  if (typeof statut === "number" && statut >= 400 && statut < 500) {
    requete.log.error({ code: "INVALID_REQUEST" }, "request refused");
    return reponse.code(400).send({ error: "INVALID_REQUEST" });
  }
  requete.log.error({ code: "INTERNAL" }, "request failed");
  return reponse.code(500).send({ error: "INTERNAL" });
};

export function enregistrerTableaux(instance: FastifyInstance, options: OptionsTableaux): void {
  const { calculerTableau, mode, desactivees } = options;
  const servir = options.servir ?? servirTableau;
  // Cut after a collision of team identifiers, like the sheets (D29): the existing 404 of the application. The test is on the route found
  // by the router (its pattern, after the decoding of the path), never on the raw URL. The hook is added before the route.
  instance.addHook("onRequest", async (requete, reponse) => {
    if (desactivees?.() === true && requete.routeOptions.url === ROUTE_TABLEAU_LEAD_CYCLE) {
      requete.log.error({ code: "NOT_FOUND" }, "request refused");
      // A text payload: the response schema of the route (which has no 404) must not serialize this answer.
      return reponse.code(404).type("application/json; charset=utf-8").send(JSON.stringify({ error: "NOT_FOUND" }));
    }
    return undefined;
  });
  instance.get(
    ROUTE_TABLEAU_LEAD_CYCLE,
    {
      errorHandler: gererErreur,
      schema: nettoyer({
        // No query parameter: any one is an invalid request.
        querystring: Type.Object({}, { additionalProperties: false }),
        response: {
          200: reduitEnMode(mode) ? SchemaReponseLeadCycleReduite : SchemaReponseLeadCycle,
          400: Erreur("INVALID_REQUEST"),
          409: Erreur("THRESHOLDS_NOT_SET"),
          500: Erreur("INTERNAL"),
          503: Erreur("DATABASE_UNAVAILABLE"),
        },
      }),
    },
    async (requete, reponse) => {
      try {
        return servir(await calculerTableau(), mode);
      } catch (erreur) {
        if (erreur instanceof BaseIndisponible) {
          requete.log.error({ code: "DATABASE_UNAVAILABLE" }, "request failed");
          return reponse.code(503).send({ error: "DATABASE_UNAVAILABLE" });
        }
        throw erreur;
      }
    },
  );
}
