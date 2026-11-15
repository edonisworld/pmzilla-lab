// The routes of the argument sheets and of the thresholds (design D20, D21, D29, task 18.1): a sheet from a chart, its reading, the review
// (refused to the author), the publication (freeze with fingerprint), the thresholds. Codes only in the answers, except the two texts the
// Agile Lead wrote, which come back as `{ text, lang }`. The verdict is never read from a request: no request schema declares it, and any
// undeclared field is refused. The body of a sheet (verdict, explanations, signal, shares) comes from the injected `calculerCorps`, which is
// the verdict service fed by the views (branché par une tâche à venir après g15); nothing here computes a verdict.
// Logs: a code, a field and a reason only; never a text, a value or a list.
import {
  SchemaBrouillon,
  SchemaCreationFiche,
  SchemaEntreeSeuil,
  SchemaEtatDeListe,
  SchemaListeFiches,
  SchemaModificationFiche,
  SchemaReponseFiche,
  SchemaReponseFicheReduite,
  SchemaReponseSeuils,
  SchemaTexteRefuse,
  codeDeSeuilConnu,
  couplesIncoherents,
  seuilDansLesBornes,
  verifierTexteEcrit,
} from "@mothra/contract";
import { GraphiqueInconnu, PorteeNonServie, SeuilsNonFixes } from "@mothra/contract";
import type { EtatDeLaFiche, QuestionDeDirection, ReponseFiche } from "@mothra/contract";
import type { FastifyError, FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import Type from "typebox";

import { BaseIndisponible } from "../db/acces.ts";
import { FicheNonServie } from "../fiches/corps.ts";
import { FicheDejaPubliee, empreinte } from "../fiches/depot.ts";
import type { ContenuFige, CorpsCalcule, DepotFiches, DepotSeuils, DepotUtilisateurs, FicheStockee } from "../fiches/depot.ts";
import { FenetreDeVuesDecalee, dataDateAcceptee, donneesPerimees } from "../fiches/fenetre.ts";
import { nettoyer } from "./serveur.ts";

export interface OptionsFiches {
  depot: DepotFiches & DepotSeuils & DepotUtilisateurs;
  // The computed body of a sheet from its chart, scope and data date: the verdict service over the views (branché par une tâche à venir après g15).
  // `id` is the sheet: the real implementation reads its creation day (the first reading, Q8). The tests' doubles ignore the context.
  calculerCorps(contexte: { id: string; chart: string; scope: string; dataDate: string }): Promise<CorpsCalcule>;
  // Optional check before a sheet is created: the chart is in the closed list (GraphiqueInconnu, 400), the scope is a team one
  // (PorteeNonServie, 400) and the thresholds it reads are fixed (SeuilsNonFixes, 409). Absent with the test doubles.
  verifierCreation?(entree: { chart: string; scope: string }): Promise<void>;
  // The bars of the share of waiting (mothra-demo-habillage D3b, R-20261101-20), added to the body at each reading, a frozen version included
  // (never stored: the freeze takes `calculerCorps` alone, Q151). Absent with the test doubles: the answer then carries no `waitShares`.
  // The route computes nothing: the service layer does (service.ts). Replaces: nothing. Removal: permanent while the bar measures hypothesis 1.
  completer?<T extends CorpsCalcule>(corps: T): T;
  // Whether the routes are switched off (the start check found a collision of team identifiers); read at each request. Absent: on.
  desactivees?(): boolean;
  // Today as `YYYY-MM-DD`, the latest date a threshold can be fixed on. Absent: the UTC day (aujourdhuiISO).
  // Replaces: the clock read inside the route, which no test could fix. Removal: permanent (same pattern as demarrage.ts).
  aujourdhui?: () => string;
  // The compiled patterns of the two lists of names the server loaded at start-up (task 18.3), never the lists themselves.
  motifsNoms: readonly RegExp[];
  // Real data with counts not allowed (task 19.5, D34): the response schema without any count field is registered, so a count the service
  // hands over is omitted whatever it does. Fixed at the start by the mode, never decided at the formatting of an answer. Absent: complete.
  // Mandatory (task 19.8, R-20261031-24 Q55): absent, the registration is refused, never made with the complete schema.
  // Replaces: the default "absent: complete". Removal: permanent.
  reduite: boolean;
}

// The caller: a pseudonymous identifier in the header `x-mothra-user`. A declarative header is a guard of use, not a protection: anyone can
// send the identifier of a user, until the single sign-on exists (author's decision of 2026-10-29). A value that is not an identifier is
// refused (400); a well-formed identifier that names no user is refused (403 UNKNOWN_USER), and the answer never echoes it.
export const EN_TETE_UTILISATEUR = "x-mothra-user";
const MOTIF_UTILISATEUR = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const MOTIF_DATE = /^\d{4}-\d{2}-\d{2}$/;
const MOTIF_CODE_SEUIL = /^[a-z0-9_.-]{1,64}$/;

// The header, declared in the schema of every route that writes (pattern of `users.id`): a missing or malformed value is a schema violation,
// answered 400 like any other.
const SchemaEnTete = Type.Object({ [EN_TETE_UTILISATEUR]: Type.String({ pattern: MOTIF_UTILISATEUR.source }) });

const Erreur = <C extends string>(code: C) => Type.Object({ error: Type.Literal(code) }, { additionalProperties: false });

// A real calendar date: the form `YYYY-MM-DD` and a day that exists (`2026-02-30` is refused).
export function dateReelle(valeur: string): boolean {
  if (!MOTIF_DATE.test(valeur)) return false;
  const date = new Date(`${valeur}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === valeur;
}

// Today as `YYYY-MM-DD` (UTC): the latest date a threshold can be fixed on (A-63: a future date freezes the value).
// Injectable by `options.aujourdhui` (pattern of demarrage.ts) so that a test fixes the date; the default stays UTC.
function aujourdhuiISO(): string {
  return new Date().toISOString().slice(0, 10);
}

// The error handler of the routes of the sheets and thresholds: any 4xx error of the framework (malformed JSON, unsupported media type, body too
// large, empty body) is an invalid request (400, a code, no framework text); anything else is INTERNAL, as everywhere.
const gererErreur = (erreur: FastifyError, requete: FastifyRequest, reponse: FastifyReply) => {
  // A threshold missing from the history: no verdict is computed (D21, R-20261030-58 Q5), a code of the application, nothing else said.
  if (erreur instanceof SeuilsNonFixes) {
    requete.log.error({ code: "THRESHOLDS_NOT_SET" }, "request refused");
    return reponse.code(409).send({ error: "THRESHOLDS_NOT_SET" });
  }
  // The views gave the window of another quarter than the data date of the sheet (A-66, R-20261112-30): no body served nor frozen.
  if (erreur instanceof FenetreDeVuesDecalee) {
    requete.log.error({ code: "DATA_DATE_STALE" }, "request refused");
    return reponse.code(409).send({ error: "DATA_DATE_STALE" });
  }
  // A sheet kind not served on real data (R-20261031-19, Q48 (a)): the existing 404 of the application.
  if (erreur instanceof FicheNonServie) {
    requete.log.error({ code: "NOT_FOUND" }, "request refused");
    return reponse.code(404).send({ error: "NOT_FOUND" });
  }
  // A chart outside the closed list of the sheet kinds (D29, Q3): an invalid request.
  if (erreur instanceof GraphiqueInconnu || erreur instanceof PorteeNonServie) {
    requete.log.error({ code: "INVALID_REQUEST" }, "request refused");
    return reponse.code(400).send({ error: "INVALID_REQUEST" });
  }
  const statut = erreur.statusCode;
  if (typeof statut === "number" && statut >= 400 && statut < 500) {
    requete.log.error({ code: "INVALID_REQUEST" }, "request refused");
    return reponse.code(400).send({ error: "INVALID_REQUEST" });
  }
  requete.log.error({ code: "INTERNAL" }, "request failed");
  return reponse.code(500).send({ error: "INTERNAL" });
};

// An empty text, or one made of spaces, counts as absent for the review (the draft may hold it as it is).
const vide = (texte?: { text: string }): boolean => texte === undefined || texte.text.trim() === "";

function utilisateurDe(requete: FastifyRequest): string | null {
  const valeur = requete.headers[EN_TETE_UTILISATEUR];
  return typeof valeur === "string" && MOTIF_UTILISATEUR.test(valeur) ? valeur : null;
}

// A published sheet answers from its frozen content alone (the effect, the cause and the question included: a change of the table after the
// publication shows nowhere); any other sheet answers from the table and the computed body.
function reponseFiche(fiche: FicheStockee, contenu: CorpsCalcule | ContenuFige): ReponseFiche {
  if (fiche.state === "published" && fiche.published !== undefined) {
    // `contenu` MUST be `corpsDe(fiche)` of the caller: the frozen content, with the bars of the share of waiting added at this reading when the
    // option is given. Checked on the fingerprint of the method face, so that a caller passing another body fails loudly instead of serving it.
    if (contenu.method.fingerprint !== fiche.published.content.method.fingerprint) {
      throw new Error("reponseFiche : le contenu d'une fiche publiée doit venir de corpsDe(fiche)");
    }
    return { ...contenu, id: fiche.id, state: "published", publishedOn: fiche.published.publishedOn } as unknown as ReponseFiche;
  }
  const base = { ...contenu, id: fiche.id, managementQuestion: fiche.managementQuestion, effect: fiche.effect, cause: fiche.cause } as Record<string, unknown>;
  return { ...base, state: fiche.state } as unknown as ReponseFiche;
}

export function enregistrerFiches(instance: FastifyInstance, options: OptionsFiches): void {
  const { depot, calculerCorps, motifsNoms, verifierCreation, desactivees, completer } = options;
  const aujourdhui = options.aujourdhui ?? aujourdhuiISO;
  // Refusal by default: the schema of the answers is never chosen by omission (the runtime check holds where the types do not).
  if (typeof (options as Partial<OptionsFiches>).reduite !== "boolean") {
    throw new Error("reduite obligatoire : les routes des fiches ne sont jamais enregistrées sans la forme (réduite ou complète) explicite");
  }

  // Routes switched off after the start check (two team names giving one identifier, R-20261030-61): the existing 404 of the application.
  // The hook is added before the routes, so that it applies to them.
  instance.addHook("onRequest", async (requete, reponse) => {
    // The route found by the router (its pattern, after the decoding of the path), not the raw URL: `/api/%73heets` reaches `/api/sheets`.
    if (desactivees?.() === true && /^\/api\/(sheets|thresholds)(\/|$)/.test(requete.routeOptions.url ?? "")) {
      requete.log.error({ code: "NOT_FOUND" }, "request refused");
      // A text payload: the response schema of the route (which has its own 404) must not serialize this answer.
      return reponse.code(404).type("application/json; charset=utf-8").send(JSON.stringify({ error: "NOT_FOUND" }));
    }
    return undefined;
  });

  // Any failure of the storage: no detail, the same code as the views.
  const indisponible = (requete: FastifyRequest, reponse: FastifyReply) => {
    requete.log.error({ code: "DATABASE_UNAVAILABLE" }, "request failed");
    return reponse.code(503).send({ error: "DATABASE_UNAVAILABLE" });
  };
  const invalide = (reponse: FastifyReply) => reponse.code(400).send({ error: "INVALID_REQUEST" });

  // A draft whose data date is no longer in the current UTC quarter is stale (A-66, R-20261112-30): the views give another window, so no body is
  // computed for it (reading, change, review, publication). A published sheet is frozen and never stale.
  const perimee = (fiche: FicheStockee): boolean => fiche.state !== "published" && donneesPerimees(fiche.dataDate, aujourdhui());
  // The sheet without its body, with the code: the fields the author wrote and nothing else. Sent as text, which the response schema of the
  // route does not serialize; the shape is `SchemaFicheSansCorps` of the contract (a test checks it).
  const sansCorps = (fiche: FicheStockee, reponse: FastifyReply) =>
    reponse
      .code(200)
      .type("application/json; charset=utf-8")
      .send(
        JSON.stringify({
          id: fiche.id,
          state: fiche.state,
          managementQuestion: fiche.managementQuestion,
          effect: fiche.effect,
          cause: fiche.cause,
          bodyState: "DATA_DATE_STALE",
        }),
      );

  // The caller of a route that reads the header: the identifier when it names a user, otherwise the answer is sent (400, 403 or 503) and
  // `null` is returned. The routes that read the header all call this, nothing else.
  async function appelant(requete: FastifyRequest, reponse: FastifyReply): Promise<string | null> {
    const utilisateur = utilisateurDe(requete);
    if (utilisateur === null) {
      await invalide(reponse);
      return null;
    }
    try {
      if (!(await depot.utilisateurExiste(utilisateur))) {
        requete.log.error({ code: "UNKNOWN_USER" }, "request refused");
        await reponse.code(403).send({ error: "UNKNOWN_USER" });
        return null;
      }
    } catch (erreur) {
      if (erreur instanceof BaseIndisponible) {
        await indisponible(requete, reponse);
        return null;
      }
      throw erreur;
    }
    return utilisateur;
  }

  // The check of the two written texts of a request (creation and change): the answer 422 is sent and `true` returned on a refusal.
  async function texteRefuse(requete: FastifyRequest, reponse: FastifyReply, textes: { effect?: { text: string }; cause?: { text: string } }): Promise<boolean> {
    for (const champ of ["effect", "cause"] as const) {
      const texte = textes[champ];
      if (texte === undefined) continue;
      const resultat = verifierTexteEcrit(texte.text, motifsNoms);
      if (!resultat.ok) {
        requete.log.error({ code: "TEXT_REFUSED", field: champ, reason: resultat.reason }, "request refused");
        const corps =
          resultat.reason === "too_long"
            ? { error: "TEXT_REFUSED", field: champ, reason: resultat.reason, count: resultat.count, max: resultat.max }
            : { error: "TEXT_REFUSED", field: champ, reason: resultat.reason };
        await reponse.code(422).send(corps);
        return true;
      }
    }
    return false;
  }
  const rogne = (t?: { text: string; lang: "fr" | "en" }) => (t === undefined ? undefined : { text: t.text.trim(), lang: t.lang });

  // The body an answer reads: the frozen content of a published sheet, otherwise the computed body; the bars of the share of waiting are added
  // at each reading when the option is given (D3b). The freeze below calls `calculerCorps` itself, so that they are never stored.
  async function corpsDe(fiche: FicheStockee): Promise<CorpsCalcule | ContenuFige> {
    const corps = fiche.published !== undefined ? fiche.published.content : await calculerCorps({ id: fiche.id, chart: fiche.chart, scope: fiche.scope, dataDate: fiche.dataDate });
    return completer === undefined ? corps : completer(corps);
  }

  const reponsesFiche = {
    200: options.reduite ? SchemaReponseFicheReduite : SchemaReponseFiche,
    400: Erreur("INVALID_REQUEST"),
    404: Erreur("UNKNOWN_SHEET"),
    403: Type.Union([Erreur("SELF_REVIEW_REFUSED"), Erreur("NOT_AUTHOR"), Erreur("UNKNOWN_USER")]),
    // 5xx other than 503 are INTERNAL (the handler of these routes), without schema.
    409: Type.Union([Erreur("NOT_REVIEWED"), Erreur("VERSION_FROZEN"), Erreur("NOT_DRAFT"), Erreur("THRESHOLDS_NOT_SET"), Erreur("DATA_DATE_STALE")]),
    422: Type.Union([Erreur("NO_MANAGEMENT_QUESTION"), Erreur("EFFECT_OR_CAUSE_MISSING"), SchemaTexteRefuse]),
    503: Erreur("DATABASE_UNAVAILABLE"),
  };

  instance.post(
    "/api/sheets",
    {
      attachValidation: true,
      errorHandler: gererErreur,
      schema: nettoyer({
        headers: SchemaEnTete,
        body: SchemaCreationFiche,
        response: {
          200: SchemaBrouillon,
          400: Erreur("INVALID_REQUEST"),
          403: Erreur("UNKNOWN_USER"),
          404: Erreur("NOT_FOUND"),
          409: Erreur("THRESHOLDS_NOT_SET"),
          422: Type.Union([SchemaTexteRefuse, Erreur("DATA_DATE_OUT_OF_RANGE")]),
          503: Erreur("DATABASE_UNAVAILABLE"),
        },
      }),
    },
    async (requete, reponse) => {
      if (requete.validationError !== undefined) {
        return invalide(reponse);
      }
      const demande = requete.body as {
        chart: string;
        scope: string;
        dataDate: string;
        managementQuestion?: QuestionDeDirection;
        effect?: { text: string; lang: "fr" | "en" };
        cause?: { text: string; lang: "fr" | "en" };
      };
      // A date that does not exist (`2026-02-30`) is an invalid request, whatever the pattern of the schema accepted.
      if (!dateReelle(demande.dataDate)) return invalide(reponse);
      // A-66 (R-20261112-30): the data date is not after the UTC day and lies in the current UTC quarter; the code only, no date echoed.
      // Replaces: « date réelle seulement ». Removal: permanent (R-20261112-30).
      if (!dataDateAcceptee(demande.dataDate, aujourdhui())) {
        requete.log.error({ code: "DATA_DATE_OUT_OF_RANGE" }, "request refused");
        return reponse.code(422).send({ error: "DATA_DATE_OUT_OF_RANGE" });
      }
      const utilisateur = await appelant(requete, reponse);
      if (utilisateur === null) return reponse;
      if (await texteRefuse(requete, reponse, demande)) return reponse;
      try {
        // The chart is in the closed list and the thresholds it reads are in the history (errors answered by the handler of the routes).
        if (verifierCreation !== undefined) await verifierCreation({ chart: demande.chart, scope: demande.scope });
        // The texts are stored trimmed, the form the length rule counts (the column holds at most 500 characters).
        const id = await depot.creer({
          chart: demande.chart,
          scope: demande.scope,
          dataDate: demande.dataDate,
          managementQuestion: demande.managementQuestion,
          effect: rogne(demande.effect),
          cause: rogne(demande.cause),
          createdBy: utilisateur,
        });
        return { id, state: "draft" as const };
      } catch (erreur) {
        if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
        throw erreur;
      }
    },
  );

  // The sheets of one state (audit #629, A-04), so that a reviewer finds the drafts and an author the reviewed sheets: the identifier, the kind, the
  // scope code, the data date and the state of each, the newest first, bounded. No written text, no verdict, no author. Reading needs no caller, as
  // the reading of one sheet does not. A state outside the three is an invalid request (400), a missing one too.
  instance.get(
    "/api/sheets",
    {
      attachValidation: true,
      errorHandler: gererErreur,
      schema: nettoyer({
        querystring: SchemaEtatDeListe,
        response: { 200: SchemaListeFiches, 400: Erreur("INVALID_REQUEST"), 503: Erreur("DATABASE_UNAVAILABLE") },
      }),
    },
    async (requete, reponse) => {
      if (requete.validationError !== undefined) return invalide(reponse);
      try {
        return { sheets: await depot.lister((requete.query as { state: EtatDeLaFiche }).state) };
      } catch (erreur) {
        if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
        throw erreur;
      }
    },
  );

  instance.get("/api/sheets/:id", { errorHandler: gererErreur, schema: nettoyer({ params: Type.Object({ id: Type.String() }), response: reponsesFiche }) }, async (requete, reponse) => {
    try {
      const fiche = await depot.lire((requete.params as { id: string }).id);
      if (fiche === null) return reponse.code(404).send({ error: "UNKNOWN_SHEET" });
      if (perimee(fiche)) return sansCorps(fiche, reponse);
      return reponseFiche(fiche, await corpsDe(fiche));
    } catch (erreur) {
      if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
      throw erreur;
    }
  });

  // The author completes a draft: the effect, the cause and the management question, any of them. Reserved to the author of the draft by the
  // declarative header (a guard of use, see above). A published version is frozen (409 VERSION_FROZEN), a reviewed sheet is no longer a draft
  // (409 NOT_DRAFT: a change would void its review); the texts go through the same check as at creation (422 TEXT_REFUSED).
  instance.patch(
    "/api/sheets/:id",
    {
      attachValidation: true,
      errorHandler: gererErreur,
      schema: nettoyer({ headers: SchemaEnTete, params: Type.Object({ id: Type.String() }), body: SchemaModificationFiche, response: reponsesFiche }),
    },
    async (requete, reponse) => {
      if (requete.validationError !== undefined) return invalide(reponse);
      const changement = requete.body as { managementQuestion?: QuestionDeDirection; effect?: { text: string; lang: "fr" | "en" }; cause?: { text: string; lang: "fr" | "en" } };
      if (changement.managementQuestion === undefined && changement.effect === undefined && changement.cause === undefined) return invalide(reponse);
      const utilisateur = await appelant(requete, reponse);
      if (utilisateur === null) return reponse;
      try {
        const id = (requete.params as { id: string }).id;
        const fiche = await depot.lire(id);
        if (fiche === null) return reponse.code(404).send({ error: "UNKNOWN_SHEET" });
        if (fiche.state === "published") return reponse.code(409).send({ error: "VERSION_FROZEN" });
        if (fiche.createdBy !== utilisateur) return reponse.code(403).send({ error: "NOT_AUTHOR" });
        if (fiche.state !== "draft") return reponse.code(409).send({ error: "NOT_DRAFT" });
        // A stale draft is not modified (A-66, R-20261112-33): refused before anything is written.
        if (perimee(fiche)) {
          requete.log.error({ code: "DATA_DATE_STALE" }, "request refused");
          return reponse.code(409).send({ error: "DATA_DATE_STALE" });
        }
        if (await texteRefuse(requete, reponse, changement)) return reponse;
        await depot.modifier(id, { managementQuestion: changement.managementQuestion, effect: rogne(changement.effect), cause: rogne(changement.cause) });
        const apres = await depot.lire(id);
        if (apres === null) return reponse.code(404).send({ error: "UNKNOWN_SHEET" });
        if (perimee(apres)) return sansCorps(apres, reponse);
        return reponseFiche(apres, await corpsDe(apres));
      } catch (erreur) {
        if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
        throw erreur;
      }
    },
  );

  instance.post(
    "/api/sheets/:id/review",
    { attachValidation: true, errorHandler: gererErreur, schema: nettoyer({ headers: SchemaEnTete, params: Type.Object({ id: Type.String() }), response: reponsesFiche }) },
    async (requete, reponse) => {
      if (requete.validationError !== undefined) return invalide(reponse);
      const utilisateur = await appelant(requete, reponse);
      if (utilisateur === null) return reponse;
      try {
        const id = (requete.params as { id: string }).id;
        const fiche = await depot.lire(id);
        if (fiche === null) return reponse.code(404).send({ error: "UNKNOWN_SHEET" });
        if (fiche.state === "published") return reponse.code(409).send({ error: "VERSION_FROZEN" });
        // One review only (author's decision of 2026-10-29): a sheet already reviewed is no longer a draft.
        if (fiche.state !== "draft") return reponse.code(409).send({ error: "NOT_DRAFT" });
        if (fiche.createdBy === utilisateur) return reponse.code(403).send({ error: "SELF_REVIEW_REFUSED" });
        // A sheet is reviewed only when it answers a management question and holds its effect and its cause, an empty text counting as absent.
        if (fiche.managementQuestion === undefined) return reponse.code(422).send({ error: "NO_MANAGEMENT_QUESTION" });
        if (vide(fiche.effect) || vide(fiche.cause)) return reponse.code(422).send({ error: "EFFECT_OR_CAUSE_MISSING" });
        // A stale draft is not reviewed (A-66): the review would rest on a body that is not computed. Refused before anything is written.
        if (perimee(fiche)) {
          requete.log.error({ code: "DATA_DATE_STALE" }, "request refused");
          return reponse.code(409).send({ error: "DATA_DATE_STALE" });
        }
        // The body is read before the review is written: a window race (409 DATA_DATE_STALE from corpsDe) leaves the draft as it was.
        const corps = await corpsDe(fiche);
        await depot.relire(id, utilisateur);
        const apres = await depot.lire(id);
        if (apres === null) return reponse.code(404).send({ error: "UNKNOWN_SHEET" });
        return reponseFiche(apres, corps);
      } catch (erreur) {
        if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
        throw erreur;
      }
    },
  );

  instance.post(
    "/api/sheets/:id/publish",
    { attachValidation: true, errorHandler: gererErreur, schema: nettoyer({ headers: SchemaEnTete, params: Type.Object({ id: Type.String() }), response: reponsesFiche }) },
    async (requete, reponse) => {
      if (requete.validationError !== undefined) return invalide(reponse);
      const utilisateur = await appelant(requete, reponse);
      if (utilisateur === null) return reponse;
      try {
        const id = (requete.params as { id: string }).id;
        const fiche = await depot.lire(id);
        if (fiche === null) return reponse.code(404).send({ error: "UNKNOWN_SHEET" });
        if (fiche.state === "published") return reponse.code(409).send({ error: "VERSION_FROZEN" });
        // Only the author of the sheet publishes it (author's decision of 2026-10-29). Like every identity check here, a guard of use on a
        // declarative header, not a protection, until the single sign-on exists.
        if (fiche.createdBy !== utilisateur) return reponse.code(403).send({ error: "NOT_AUTHOR" });
        if (fiche.state !== "reviewed") return reponse.code(409).send({ error: "NOT_REVIEWED" });
        if (fiche.managementQuestion === undefined || fiche.effect === undefined || fiche.cause === undefined) {
          return reponse.code(422).send({ error: "EFFECT_OR_CAUSE_MISSING" });
        }
        // A stale sheet is not frozen (A-66, R-20261112-30): no body is computed, nothing is stored.
        if (perimee(fiche)) {
          requete.log.error({ code: "DATA_DATE_STALE" }, "request refused");
          return reponse.code(409).send({ error: "DATA_DATE_STALE" });
        }
        // The freeze: the computed body as it is now, with the effect, the cause and the question as the table holds them, and the fingerprint
        // of that whole content, inserted once and never changed. The state is checked again in the transaction of the depot.
        const contenu: ContenuFige = {
          ...(await calculerCorps({ id: fiche.id, chart: fiche.chart, scope: fiche.scope, dataDate: fiche.dataDate })),
          effect: fiche.effect,
          cause: fiche.cause,
          managementQuestion: fiche.managementQuestion,
        };
        await depot.publier(id, { content: contenu, fingerprint: empreinte(contenu), publishedBy: utilisateur });
        const apres = await depot.lire(id);
        if (apres === null) return reponse.code(404).send({ error: "UNKNOWN_SHEET" });
        return reponseFiche(apres, await corpsDe(apres));
      } catch (erreur) {
        if (erreur instanceof FicheDejaPubliee) return reponse.code(409).send({ error: "VERSION_FROZEN" });
        if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
        throw erreur;
      }
    },
  );

  instance.get("/api/thresholds", { errorHandler: gererErreur, schema: nettoyer({ response: { 200: SchemaReponseSeuils, 503: Erreur("DATABASE_UNAVAILABLE") } }) }, async (requete, reponse) => {
    try {
      return { thresholds: await depot.seuils() };
    } catch (erreur) {
      if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
      throw erreur;
    }
  });

  instance.post(
    "/api/thresholds",
    {
      attachValidation: true,
      errorHandler: gererErreur,
      // R-20261107-29 decision 5 (a): the coercion of types is off for the value of this body only (the global validator keeps its own):
      // before the validation, a value that is not a number (null, "5", true, ["5"]) is refused, where the coercion would turn it into a number.
      // Replaces: the coercion of the value by the validator (null read as 0). Removal: permanent (A-63, bornes-seuils.ts).
      preValidation: async (requete, reponse) => {
        const corps = requete.body;
        if (typeof corps === "object" && corps !== null && "value" in corps && typeof corps.value !== "number") {
          return invalide(reponse);
        }
        return undefined;
      },
      schema: nettoyer({
        headers: SchemaEnTete,
        body: SchemaEntreeSeuil,
        response: { 200: SchemaReponseSeuils, 400: Erreur("INVALID_REQUEST"), 403: Erreur("UNKNOWN_USER"), 422: Erreur("THRESHOLD_INCOMPLETE"), 503: Erreur("DATABASE_UNAVAILABLE") },
      }),
    },
    async (requete, reponse) => {
      if (requete.validationError !== undefined) return invalide(reponse);
      const entree = requete.body as { code: string; value: number; setOn?: string };
      // The author of a threshold is the user of the header, never a value of the body (the body schema declares no author field, and any
      // undeclared field is refused). An entry without its date is refused (D21), whatever else is wrong with it.
      if (entree.setOn === undefined) {
        requete.log.error({ code: "THRESHOLD_INCOMPLETE" }, "request refused");
        return reponse.code(422).send({ error: "THRESHOLD_INCOMPLETE" });
      }
      // Audit #629 A-63: the code is in the closed list, the value in the bounds of its code, the date not in the future.
      // Replaces: the free code (a pattern) and the free value. Removal: permanent (see contract/src/bornes-seuils.ts).
      if (
        !MOTIF_CODE_SEUIL.test(entree.code) ||
        !dateReelle(entree.setOn) ||
        !Number.isFinite(entree.value) ||
        !codeDeSeuilConnu(entree.code) ||
        !seuilDansLesBornes(entree.code, entree.value) ||
        entree.setOn > aujourdhui()
      ) {
        return invalide(reponse);
      }
      const utilisateur = await appelant(requete, reponse);
      if (utilisateur === null) return reponse;
      try {
        // A pair (lower, upper) that would not be ordered once this value is in force is refused before anything is stored, only when the
        // pair touches the code written: with an history already inconsistent, the write of another code goes through.
        // Replaces: the refusal on any inconsistent pair of the history, whatever the code written. Removal: permanent (A-63, bornes-seuils.ts).
        const apres = [...(await depot.seuils()), { code: entree.code, value: entree.value, setOn: entree.setOn }];
        if (couplesIncoherents(apres).includes(entree.code)) return invalide(reponse);
        await depot.ajouterSeuil({ code: entree.code, value: entree.value, setOn: entree.setOn, setBy: utilisateur });
        return { thresholds: await depot.seuils() };
      } catch (erreur) {
        if (erreur instanceof BaseIndisponible) return indisponible(requete, reponse);
        throw erreur;
      }
    },
  );
}
