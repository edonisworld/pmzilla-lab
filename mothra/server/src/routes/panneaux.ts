// The four routes of the panels of the product-scope dashboard (mothra-slices D35, task 37.1; author's decision Q5 (a): one route and one
// response schema per panel): `GET /api/panels/<code>` for `stories-inout`, `correction-share`, `defects-inout` and `blocked-share`.
// Every answer goes through `servirPanneau` of the service layer (a static test checks it): the route decides nothing and formats nothing.
// The query is the shared filters of the second screen (task 31.1, reused): outside the schema, 400 INVALID_REQUEST; a bad scope or range,
// 422 SCOPE_INVALID or RANGE_INVALID. The blocked share has no product level: 422 SCOPE_INVALID (decision Q59). The response schema is chosen
// at the registration, from the mode fixed at the start, so a count the service hands over is omitted whatever it does (task 6.4 rule).
// One date per request: the three closed quarters of the filters are computed on that day.
// Codes only in the answers; the log holds a code.
import {
  CODES_PANNEAUX,
  SchemaPanneauBlockedShare,
  SchemaPanneauCorrectionShare,
  SchemaPanneauDefectsInout,
  SchemaPanneauReduit,
  SchemaPanneauStoriesInout,
  PorteeProduitRefusee,
} from "@mothra/contract";
import type { CodeJeuDeDonnees, CodePanneau, PanneauComplet, ResultatFiltres } from "@mothra/contract";
import type { FastifyError, FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import Type from "typebox";

import { BaseIndisponible } from "../db/acces.ts";
import { FenetreDeVuesDecalee } from "../fiches/fenetre.ts";
import { CollisionDIdentifiantsEquipe } from "../fiches/panneaux.ts";
import { reduitEnMode, servirPanneau } from "../service.ts";
import type { ModeDonnees } from "../service.ts";
import { SchemaQueryFiltres, SchemaRefusFiltres, aujourdhui as aujourdhuiUTC, lireFiltres } from "./filtres.ts";
import { nettoyer } from "./serveur.ts";

export const PREFIXE_ROUTES_PANNEAUX = "/api/panels/";

export interface OptionsPanneaux {
  // The complete panel from the views (the contract's functions over the masked answer): complete, never reduced here. `aujourdhui` is the
  // one date of the request.
  calculerPanneau(code: CodePanneau, filtres: Extract<ResultatFiltres, { ok: true }>, aujourdhui: string, jeu: CodeJeuDeDonnees): Promise<PanneauComplet>;
  // The dataset and the constant of the contract, fixed at the start.
  mode: ModeDonnees;
  // The day of the reading, `YYYY-MM-DD` (default: the UTC date of the server's clock); a test fixes it.
  aujourdhui?: () => string;
  // Whether the routes are switched off (the start check found a collision of team identifiers); read at each request. Absent: on.
  desactivees?(): boolean;
}

const Erreur = <C extends string>(code: C) => Type.Object({ error: Type.Literal(code) }, { additionalProperties: false });

const gererErreur = (erreur: FastifyError, requete: FastifyRequest, reponse: FastifyReply) => {
  const statut = erreur.statusCode;
  if (typeof statut === "number" && statut >= 400 && statut < 500) {
    requete.log.error({ code: "INVALID_REQUEST" }, "request refused");
    return reponse.code(400).send({ error: "INVALID_REQUEST" });
  }
  requete.log.error({ code: "INTERNAL" }, "request failed");
  return reponse.code(500).send({ error: "INTERNAL" });
};

const SCHEMAS_COMPLETS = {
  "stories-inout": SchemaPanneauStoriesInout,
  "correction-share": SchemaPanneauCorrectionShare,
  "defects-inout": SchemaPanneauDefectsInout,
  "blocked-share": SchemaPanneauBlockedShare,
} as const;

export function enregistrerPanneaux(instance: FastifyInstance, options: OptionsPanneaux): void {
  const { calculerPanneau, mode, desactivees } = options;
  const jour = options.aujourdhui ?? (() => aujourdhuiUTC());

  // Routes switched off after the start check (two team names giving one identifier, R-20261030-61), like the sheets (D29): the existing
  // 404 of the application. The hook is added before the routes, so that it applies to them.
  instance.addHook("onRequest", async (requete, reponse) => {
    if (desactivees?.() === true && (requete.routeOptions.url ?? "").startsWith(PREFIXE_ROUTES_PANNEAUX)) {
      requete.log.error({ code: "NOT_FOUND" }, "request refused");
      // A text payload: the response schema of the route (which has no 404) must not serialize this answer.
      return reponse.code(404).type("application/json; charset=utf-8").send(JSON.stringify({ error: "NOT_FOUND" }));
    }
    return undefined;
  });

  for (const code of CODES_PANNEAUX) {
    instance.get(
      `${PREFIXE_ROUTES_PANNEAUX}${code}`,
      {
        errorHandler: gererErreur,
        schema: nettoyer({
          querystring: SchemaQueryFiltres,
          response: {
            200: reduitEnMode(mode) ? SchemaPanneauReduit : SCHEMAS_COMPLETS[code],
            400: Erreur("INVALID_REQUEST"),
            409: Erreur("DATA_DATE_STALE"),
            422: SchemaRefusFiltres,
            500: Erreur("INTERNAL"),
            503: Erreur("DATABASE_UNAVAILABLE"),
          },
        }),
      },
      async (requete, reponse) => {
        const aujourdhui = jour();
        const filtres = lireFiltres(requete.query, aujourdhui);
        if (!filtres.ok) {
          requete.log.error({ code: filtres.code }, "request refused");
          return reponse.code(422).send({ error: filtres.code });
        }
        try {
          return servirPanneau(await calculerPanneau(code, filtres, aujourdhui, mode.jeu), mode);
        } catch (erreur) {
          if (erreur instanceof PorteeProduitRefusee) {
            requete.log.error({ code: "SCOPE_INVALID" }, "request refused");
            return reponse.code(422).send({ error: "SCOPE_INVALID" });
          }
          if (erreur instanceof CollisionDIdentifiantsEquipe) {
            requete.log.error({ code: "NOT_FOUND" }, "request refused");
            // The route schema has no 404 (like the hook above): the reply is typed loosely and sent as text.
            return (reponse as FastifyReply).code(404).type("application/json; charset=utf-8").send(JSON.stringify({ error: "NOT_FOUND" }));
          }
          // A66 (R-20261112-30): the views gave the window of another quarter than the day of the route (race at a quarter change).
          if (erreur instanceof FenetreDeVuesDecalee) {
            requete.log.error({ code: "DATA_DATE_STALE" }, "request refused");
            return reponse.code(409).send({ error: "DATA_DATE_STALE" });
          }
          if (erreur instanceof BaseIndisponible) {
            requete.log.error({ code: "DATABASE_UNAVAILABLE" }, "request failed");
            return reponse.code(503).send({ error: "DATABASE_UNAVAILABLE" });
          }
          throw erreur;
        }
      },
    );
  }
}
