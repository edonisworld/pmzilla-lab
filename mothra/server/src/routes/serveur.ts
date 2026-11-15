// The Fastify server of Mothra (mothra-slices D7): TypeBox schemas on every route, the six masking points, codes only in the answers.
// Points: (1) closed list checked before any connection; (2) threshold max(5, contract, setting, option) never lowered; (3) only count
// columns masked; (4) structured cell; (5) one response schema per route, serialization omitting undeclared fields; (6) the connection
// (opened by the access object given here) is under the view-limited role only.
// Logs: no request logging (a URL may hold a client text), no body, no value; an error is logged as its code only.
import { SchemaReponseVue, schemaReponseDeVue, seuilEffectif } from "@mothra/contract";
import type { Contrat, Vue } from "@mothra/contract";
import type { TypeBoxTypeProvider } from "@fastify/type-provider-typebox";
import Fastify, { LogController } from "fastify";
import type { FastifyInstance, FastifyReply } from "fastify";
import Type from "typebox";
import type { TSchema } from "typebox";

import { BaseIndisponible } from "../db/acces.ts";
import type { AccesVues } from "../db/acces.ts";
import { lireVueMasquee, servirVue } from "../service.ts";
import { enregistrerFiches } from "./fiches.ts";
import type { OptionsFiches } from "./fiches.ts";
import { enregistrerPanneaux } from "./panneaux.ts";
import type { OptionsPanneaux } from "./panneaux.ts";
import { enregistrerTableaux } from "./tableaux.ts";
import type { OptionsTableaux } from "./tableaux.ts";
import { DOSSIER_BUNDLE_STANDARD, ROUTES_DU_BUNDLE, codeIntrouvable, enregistrerBundle } from "./bundle.ts";

// The only routes dispensed from a response schema: those of the bundle (task 8.8, answer Q2). A test fails on any other entry.
export const ROUTES_WITHOUT_RESPONSE_SCHEMA: readonly string[] = ROUTES_DU_BUNDLE;

// The headers of every answer (answer Q1), set in one hook: no HSTS (the server listens on the loopback, in clear), no CORS.
export const EN_TETES_SECURITE: Readonly<Record<string, string>> = {
  "content-security-policy": "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
  "x-frame-options": "DENY",
};

// The one place that sets the four headers on a reply: the onSend hook and the framework-error answer (which bypasses the hooks) both call it.
export function poserEnTetesSecurite(reponse: { header(nom: string, valeur: string): unknown }): void {
  for (const [nom, valeur] of Object.entries(EN_TETES_SECURITE)) {
    reponse.header(nom, valeur);
  }
}

export interface RouteEnregistree {
  method: string;
  url: string;
}

// The views served by slice 0: the contract may list more, only these names (of the flow kind) are served, the others answer UNKNOWN_VIEW.
export const VUES_SERVIES_TRANCHE_0: readonly string[] = ["v_team_status"];

export interface OptionsServeur {
  contrat: Contrat;
  acces: AccesVues;
  // The names served (default: the list of the slice). A view of the contract that is not of the flow kind is never served.
  vuesServies?: readonly string[];
  // The threshold setting of the configuration (null when absent).
  reglageSeuil: number | null;
  // Pino options; `false` (default) logs nothing. A test passes a stream to capture the log.
  journal?: { level: string; stream?: { write(message: string): void } } | false;
  // The folder of the built bundle (default: mothra/front/dist). It may be absent: the server then answers BUNDLE_MISSING on its pages.
  dossierBundle?: string;
  // The sheet and threshold routes (task 18.1); absent, they are not registered.
  fiches?: OptionsFiches;
  // The dashboard route (task 19.6); absent, it is not registered.
  tableaux?: OptionsTableaux;
  // The four panel routes of the product-scope dashboard (task 37.1); absent, they are not registered.
  panneaux?: OptionsPanneaux;
  // Real data with counts not allowed (R-20261031-19, Q49): the table of counts `/api/views/:view` has no reduced form, so it answers the
  // existing 404 NOT_FOUND. Fixed at the start by the mode. Replaces: nothing. Removal: when the view has its reduced form (D34 point 6).
  vuesFermees?: boolean;
  // MOTHRA_SHOW_TEAM_NAMES (R-20261104-69 Q1): absent or false, the route leaves the column `team` out of its answer (`servirVue`).
  // Remplace : rien ; retrait : avec le réglage (N3 (a)).
  afficherNoms?: boolean;
  // The listening port, when the caller knows it: the Host header must then carry exactly it. Absent, any port of the two loopback names
  // is accepted (a test injects with the default host `localhost:80`). Remplace : rien ; retrait : avec les tests de Host de l'audit 629
  // (A-60) si le serveur n'écoute plus sur la boucle locale seule.
  portEcoute?: number;
}

const HOTES_AUTORISES: readonly string[] = ["127.0.0.1", "localhost"];

// A-60 (audit 629, L3-01), anti DNS rebinding: the Host header names the loopback address or `localhost`, with the listening port when it
// is known. Anything else (another name, no header, a list, a user-info part) is refused.
// Remplace : rien. Retrait : permanent tant que le serveur écoute en clair sur la boucle locale (invariant 6) ; tombe avec une décision
// d'hébergement qui remplace cette garde par celle du proxy.
export function hoteAccepte(entete: string | string[] | undefined, port: number | null = null): boolean {
  if (typeof entete !== "string") {
    return false;
  }
  const [nom, portTexte, ...reste] = entete.toLowerCase().split(":");
  if (nom === undefined || reste.length > 0 || !HOTES_AUTORISES.includes(nom)) {
    return false;
  }
  if (port === null) {
    return portTexte === undefined || /^[1-9][0-9]{0,4}$/.test(portTexte);
  }
  return portTexte === String(port);
}

// A-60 (audit 629, L3-01), anti-CSRF; the rebinding is stopped by hoteAccepte. On a request that writes (any method other than GET, HEAD and OPTIONS), an Origin header, when present, names
// this very server (`http://<Host>`), and a Sec-Fetch-Site header, when present, is `same-origin` (or `none`). A caller without the headers
// (a script, the e2e client, a test) is not refused: the browsers always send them on a cross-site write.
// Remplace : rien. Retrait : avec l'authentification de l'hébergement (levée de l'invariant 6), qui porte alors l'anti-CSRF.
export function ecritureMemeOrigine(methode: string, entetes: Readonly<Record<string, string | string[] | undefined>>): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(methode)) {
    return true;
  }
  const origine = entetes["origin"];
  if (origine !== undefined && (typeof origine !== "string" || origine !== `http://${String(entetes["host"])}`)) {
    return false;
  }
  const site = entetes["sec-fetch-site"];
  return site === undefined || site === "same-origin" || site === "none";
}

// TypeBox schemas carry internal markers (keys starting with "~") that a JSON Schema validator or serializer may refuse:
// the plain copy without them is what Fastify receives (same approach as the published schema files of the contract package).
export function nettoyer<T>(schema: T): T {
  return JSON.parse(JSON.stringify(schema, (cle, valeur: unknown) => (cle.startsWith("~") ? undefined : valeur))) as T;
}

const SchemaErreur = <C extends string>(code: C) => Type.Object({ error: Type.Literal(code) }, { additionalProperties: false });

// The views served: of the flow kind and in the served list. The only place that decides what the route answers.
export function vuesServies(contrat: Contrat, noms: readonly string[]): Vue[] {
  return contrat.views.filter((vue) => vue.roleKind === "flow" && noms.includes(vue.name));
}

// One strict response schema per served view, built from the contract (columns of the view and nothing else, a literal view name):
// a field a row would hold beyond them is not serialized. Without a served view, the generic schema of the contract package.
// `sansNom`: names off, the schema has no `team` column but keeps `kind` (R-20261109-21).
export function schemaDeReponse(vues: readonly Vue[], sansNom = false): TSchema {
  return vues.length === 0 ? SchemaReponseVue : Type.Union(vues.map((v) => schemaReponseDeVue(v, { sansNom })));
}

// A route registered without a response schema for its 200 answer makes the registration fail, naming the route.
export function exigerSchemaDeReponse(app: FastifyInstance, dispenses: readonly string[] = ROUTES_WITHOUT_RESPONSE_SCHEMA): void {
  app.addHook("onRoute", (route) => {
    if (dispenses.includes(`${[route.method].flat().join(",")} ${route.url}`)) {
      return;
    }
    const reponses = (route.schema as { response?: Record<string, unknown> } | undefined)?.response;
    if (reponses === undefined || reponses[200] === undefined) {
      throw new Error(`route sans schéma de réponse : ${[route.method].flat().join(",")} ${route.url}`);
    }
  });
}

export function construireServeur(options: OptionsServeur): { app: FastifyInstance; routes: RouteEnregistree[] } {
  const { contrat, acces, reglageSeuil } = options;
  const servies = vuesServies(contrat, options.vuesServies ?? VUES_SERVIES_TRANCHE_0);
  const instance = Fastify({
    logger: options.journal ?? false,
    // A malformed URL (bad percent-encoding) or any error raised by the framework before the route: the same code as an unknown view,
    // never Fastify's own text.
    frameworkErrors: (_erreur, requete, reponse: FastifyReply) => {
      const code = codeIntrouvable(requete.url, requete.method);
      requete.log.error({ code }, "request refused");
      // The hooks do not run on this answer: the headers are set here.
      poserEnTetesSecurite(reponse);
      void reponse.code(404).send({ error: code });
    },
    // Fastify 5.12: the top-level `disableRequestLogging` is deprecated (FSTDEP023); the log controller carries it (lib/log-controller.js).
    logController: new LogController({ disableRequestLogging: true }),
    exposeHeadRoutes: false,
    // An undeclared field of a request is refused, never silently dropped (D29: `additionalProperties: false`; Fastify's default removes it).
    ajv: { customOptions: { removeAdditional: false } },
  });
  exigerSchemaDeReponse(instance);
  const routes: RouteEnregistree[] = [];
  instance.addHook("onRoute", (route) => {
    routes.push({ method: [route.method].flat().join(","), url: route.url });
  });

  instance.setErrorHandler((_erreur, requete, reponse) => {
    requete.log.error({ code: "INTERNAL" }, "request failed");
    return reponse.code(500).send({ error: "INTERNAL" });
  });
  instance.setNotFoundHandler((requete, reponse) => reponse.code(404).send({ error: codeIntrouvable(requete.url, requete.method) }));
  // A-60: the Host and write-origin guard, first hook of the server, so that it covers every route registered after it (the API, the bundle
  // and the not-found handler). A test lists the registered routes and checks that each refuses a foreign Host. The answer is the existing
  // 404 NOT_FOUND, as a text payload (the response schema of a route has its own 404).
  instance.addHook("onRequest", async (requete, reponse) => {
    if (!hoteAccepte(requete.headers.host, options.portEcoute ?? null) || !ecritureMemeOrigine(requete.method, requete.headers)) {
      requete.log.error({ code: "NOT_FOUND" }, "request refused");
      return reponse.code(404).type("application/json; charset=utf-8").send(JSON.stringify({ error: "NOT_FOUND" }));
    }
  });
  // The same four headers on every answer (a file, a page, an error, the API), in one place.
  instance.addHook("onSend", async (_requete, reponse, charge) => {
    poserEnTetesSecurite(reponse);
    return charge;
  });

  const app = instance.withTypeProvider<TypeBoxTypeProvider>();
  const schema = nettoyer({
    params: Type.Object({ view: Type.String() }),
    response: {
      // Setting off: the strict schema has no `team` column either (a row never holds one, see `servirVue`), but a by-team view keeps `kind`.
      200: schemaDeReponse(servies, options.afficherNoms !== true),
      404: Type.Union([SchemaErreur("UNKNOWN_VIEW"), SchemaErreur("NOT_FOUND")]),
      500: SchemaErreur("INTERNAL"),
      503: SchemaErreur("DATABASE_UNAVAILABLE"),
    },
  });

  app.get("/api/views/:view", { schema }, async (requete, reponse) => {
    if (options.vuesFermees === true) {
      requete.log.error({ code: "NOT_FOUND" }, "request refused");
      return reponse.code(404).send({ error: "NOT_FOUND" });
    }
    const nom = requete.params.view;
    // Point 1: the closed list, before any connection. The name is never passed to the database: the view comes from the contract.
    const vue = servies.find((v) => v.name === nom);
    if (vue === undefined) {
      return reponse.code(404).send({ error: "UNKNOWN_VIEW" });
    }
    // Audit #629 A-78, R-20261107-29 point 6 (b): no threshold option in the request (`?threshold` is ignored on every view); the threshold
    // served is the one of the contract and the configuration. Replaces: the option read for the views with no relation between cells.
    // Removal: permanent (the relation T3 and the pairs are not monotone in the threshold).
    const seuil = seuilEffectif(contrat, reglageSeuil);
    try {
      return servirVue(await lireVueMasquee(acces, vue, seuil), { afficherNoms: options.afficherNoms });
    } catch (erreur) {
      if (!(erreur instanceof BaseIndisponible)) {
        throw erreur;
      }
      requete.log.error({ code: "DATABASE_UNAVAILABLE" }, "request failed");
      return reponse.code(503).send({ error: "DATABASE_UNAVAILABLE" });
    }
  });

  // The sheet and threshold routes (task 18.1), only when the caller gives their storage and body builder; before the bundle, which
  // answers under /api/ with codes only.
  if (options.fiches !== undefined) {
    enregistrerFiches(instance, options.fiches);
  }
  // The dashboard route (task 19.6), with its mode; absent, it is not registered.
  if (options.tableaux !== undefined) {
    enregistrerTableaux(instance, options.tableaux);
  }
  // The panel routes (task 37.1), with their mode; absent, they are not registered.
  if (options.panneaux !== undefined) {
    enregistrerPanneaux(instance, options.panneaux);
  }

  // After the API route: the bundle (files, then index.html for the routes of the front). Under /api/ it answers codes only.
  enregistrerBundle(instance, options.dossierBundle ?? DOSSIER_BUNDLE_STANDARD);

  return { app: instance, routes };
}
