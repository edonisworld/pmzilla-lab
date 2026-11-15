// The real source of the dashboard and of the sheet (task 19.7, Q54 bis): the client of the routes `GET /api/dashboards/lead_cycle`,
// `POST /api/sheets`, `GET /api/sheets/:id` and `PATCH /api/sheets/:id`. It only carries: it holds no rule of masking, of verdict or of
// total (design D30), it checks the shape of what it receives, and it turns a refusal of the service into a code of the front's catalogue
// (never a text of the server). Every request goes to the local server by a relative path; the `fetch` is injected, so that the tests
// call no network. The complete answer (synthetic dataset) and the reduced one (real data, D34) are both passed on as received.
import type { CodePanneau, ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";

import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";

import type { EtatEnCours, ResumeFiche, SourceCycleFiche } from "./cycleFiche.ts";
import { ETATS_FICHE, RefusFiche } from "./fiche.ts";
import type { ModificationFiche, RefusTexte, ReponseFiche, ResultatAction, ResultatCompletion } from "./fiche.ts";
import type { FiltresEcran } from "./filtres.ts";
import type { CreerFiche, SourceLeadCycle } from "./leadCycle.ts";
import { estRefusFiltres, RefusPanneau } from "./panneaux.ts";
import type { ReponsePanneau, SourcePanneaux } from "./panneaux.ts";
import { ErreurApi, estCodeErreur } from "./vue.ts";
import type { CodeErreur } from "./vue.ts";

export const ROUTE_TABLEAU = "/api/dashboards/lead_cycle";
export const ROUTE_FICHES = "/api/sheets";
export const ROUTE_PANNEAUX = "/api/panels/";
// The header that names the caller of a route that writes (a pseudonymous identifier, a guard of use until the single sign-on exists).
export const EN_TETE_UTILISATEUR = "x-mothra-user";

// The identifier of the caller, read when a request is made; none: the header is not sent and the service answers its own refusal.
export type Utilisateur = () => string | undefined;

function objet(valeur: unknown): Record<string, unknown> | undefined {
  return typeof valeur === "object" && valeur !== null && !Array.isArray(valeur) ? (valeur as Record<string, unknown>) : undefined;
}

async function corpsJson(reponse: Response): Promise<unknown> {
  try {
    return await reponse.json();
  } catch {
    return undefined;
  }
}

function codeConnu(code: unknown): CodeErreur {
  return estCodeErreur(code) ? code : "INTERNAL";
}

const CHAMPS_TEXTE = ["effect", "cause"] as const;
const RAISONS_TEXTE = ["ticket_key", "email", "sensitive_name", "too_long"] as const;

// The detail of a refused written text (`TEXT_REFUSED`, 422), or nothing when the body is not exactly that: the count and the maximum are
// kept with `too_long` only. The refused value is never part of the body, and nothing else of it is kept.
function texteRefuse(corps: Record<string, unknown>): RefusTexte | undefined {
  const { field, reason, count, max } = corps;
  const champ = CHAMPS_TEXTE.find((c) => c === field);
  const raison = RAISONS_TEXTE.find((r) => r === reason);
  if (corps.error !== "TEXT_REFUSED" || champ === undefined || raison === undefined) return undefined;
  if (raison === "too_long" && typeof count === "number" && typeof max === "number") return { field: champ, reason: raison, count, max };
  return { field: champ, reason: raison };
}

// What a refused request says: the code of its body (an unknown or absent one is the internal error), and the detail of a refused text.
async function refusDe(reponse: Response): Promise<{ code: CodeErreur | "TEXT_REFUSED"; texte?: RefusTexte }> {
  const corps = objet(await corpsJson(reponse));
  if (corps === undefined) return { code: "INTERNAL" };
  const texte = texteRefuse(corps);
  if (texte !== undefined) return { code: "TEXT_REFUSED", texte };
  return { code: codeConnu(corps.error) };
}

async function envoyer(appeler: typeof fetch, url: string, options: RequestInit): Promise<Response | undefined> {
  try {
    return await appeler(url, options);
  } catch {
    return undefined;
  }
}

function entetesEcriture(utilisateur: Utilisateur): Record<string, string> {
  const entetes: Record<string, string> = { accept: "application/json", "content-type": "application/json" };
  const identifiant = utilisateur();
  if (identifiant !== undefined && identifiant !== "") entetes[EN_TETE_UTILISATEUR] = identifiant;
  return entetes;
}

// The shape of the dashboard's answer (complete or reduced): the fields the screen reads, nothing computed.
function formeTableau(corps: unknown): corps is ReponseLeadCycle | ReponseLeadCycleReduite {
  const o = objet(corps);
  return o !== undefined && typeof o.threshold === "number" && typeof o.dataDate === "string" && Array.isArray(o.product) && Array.isArray(o.teams);
}

// The reader of the dashboard. A refusal is raised as an `ErreurApi` carrying its code.
export async function lireLeadCycleHttp(appeler: typeof fetch = fetch): Promise<ReponseLeadCycle | ReponseLeadCycleReduite> {
  const reponse = await envoyer(appeler, ROUTE_TABLEAU, { method: "GET", headers: { accept: "application/json" } });
  if (reponse === undefined) throw new ErreurApi("INTERNAL");
  if (!reponse.ok) {
    const refus = await refusDe(reponse);
    throw new ErreurApi(refus.code === "TEXT_REFUSED" ? "INTERNAL" : refus.code);
  }
  const corps = await corpsJson(reponse);
  if (!formeTableau(corps)) throw new ErreurApi("INTERNAL");
  return corps;
}

// The route of "make it a sheet". A refusal is raised as a `RefusFiche` (code, and the detail of a refused text).
export function creerFicheHttp(utilisateur: Utilisateur, appeler: typeof fetch = fetch): CreerFiche {
  return async (demande) => {
    const reponse = await envoyer(appeler, ROUTE_FICHES, { method: "POST", headers: entetesEcriture(utilisateur), body: JSON.stringify(demande) });
    if (reponse === undefined) throw new RefusFiche("INTERNAL");
    if (!reponse.ok) {
      const refus = await refusDe(reponse);
      throw new RefusFiche(refus.code, refus.texte);
    }
    const corps = objet(await corpsJson(reponse));
    if (corps === undefined || typeof corps.id !== "string" || corps.state !== "draft") throw new RefusFiche("INTERNAL");
    return { id: corps.id, state: "draft" };
  };
}

// The reading of a sheet. The answer is the contract's (complete or reduced), passed on as received once its identity is checked.
export async function lireFicheHttp(id: string, appeler: typeof fetch = fetch): Promise<ReponseFiche> {
  const reponse = await envoyer(appeler, `${ROUTE_FICHES}/${encodeURIComponent(id)}`, { method: "GET", headers: { accept: "application/json" } });
  if (reponse === undefined) throw new ErreurApi("INTERNAL");
  if (!reponse.ok) {
    const refus = await refusDe(reponse);
    throw new ErreurApi(refus.code === "TEXT_REFUSED" ? "INTERNAL" : refus.code);
  }
  const corps = objet(await corpsJson(reponse));
  if (corps === undefined || typeof corps.id !== "string" || typeof corps.state !== "string") throw new ErreurApi("INTERNAL");
  // A draft whose data date left the current quarter comes without a body (A-66, R-20261112-30, D29): it is shown as its refusal, through the
  // catalogue, with no body, no verdict and no chart. The front decides nothing from the date: it reads the field the service sets.
  if (corps.bodyState === "DATA_DATE_STALE") throw new ErreurApi("DATA_DATE_STALE");
  return corps as unknown as ReponseFiche;
}

// The completion of a draft: success, or the code of the refusal and, for a refused text, its detail.
export async function completerFicheHttp(
  id: string,
  modification: ModificationFiche,
  utilisateur: Utilisateur,
  appeler: typeof fetch = fetch,
): Promise<ResultatCompletion> {
  const reponse = await envoyer(appeler, `${ROUTE_FICHES}/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: entetesEcriture(utilisateur),
    body: JSON.stringify(modification),
  });
  if (reponse === undefined) return { ok: false, code: "INTERNAL" };
  if (reponse.ok) return { ok: true };
  const refus = await refusDe(reponse);
  return refus.texte === undefined ? { ok: false, code: refus.code } : { ok: false, code: refus.code, texte: refus.texte };
}

// ---- the life cycle of the sheets (audit #629, A-04) ----------------------------------------------------------------------------------

// A sheet of the list, or nothing when the entry is not exactly that: a kind outside the contract's closed list, which no page of the front
// opens, is left out; nothing else of the entry is kept.
function resumeDe(entree: unknown): ResumeFiche | undefined {
  const o = objet(entree);
  if (o === undefined) return undefined;
  const { id, chart, scope, dataDate, state } = o;
  const genre = GRAPHIQUES_DE_FICHE.find((g) => g === chart);
  const etat = ETATS_FICHE.find((e) => e === state);
  if (typeof id !== "string" || genre === undefined || typeof scope !== "string" || typeof dataDate !== "string" || etat === undefined) return undefined;
  return { id, chart: genre, scope, dataDate, state: etat };
}

// The sheets of a state, newest first as the service gives them: `GET /api/sheets?state=…`. A refusal is raised as an `ErreurApi` carrying its code.
export async function listerFichesHttp(etat: EtatEnCours, appeler: typeof fetch = fetch): Promise<ResumeFiche[]> {
  const reponse = await envoyer(appeler, `${ROUTE_FICHES}?state=${etat}`, { method: "GET", headers: { accept: "application/json" } });
  if (reponse === undefined) throw new ErreurApi("INTERNAL");
  if (!reponse.ok) {
    const refus = await refusDe(reponse);
    throw new ErreurApi(refus.code === "TEXT_REFUSED" ? "INTERNAL" : refus.code);
  }
  const corps = objet(await corpsJson(reponse));
  if (corps === undefined || !Array.isArray(corps.sheets)) throw new ErreurApi("INTERNAL");
  return corps.sheets.flatMap((entree: unknown) => resumeDe(entree) ?? []);
}

// A review or a publication: a POST with the caller's identifier and no body (so no content type, which the framework would refuse on an empty
// body). Success, or the code of the refusal; the answer's own body is not read, the screen reads the sheet again.
async function actionFicheHttp(id: string, action: "review" | "publish", utilisateur: Utilisateur, appeler: typeof fetch): Promise<ResultatAction> {
  const entetes: Record<string, string> = { accept: "application/json" };
  const identifiant = utilisateur();
  if (identifiant !== undefined && identifiant !== "") entetes[EN_TETE_UTILISATEUR] = identifiant;
  const reponse = await envoyer(appeler, `${ROUTE_FICHES}/${encodeURIComponent(id)}/${action}`, { method: "POST", headers: entetes });
  if (reponse === undefined) return { ok: false, code: "INTERNAL" };
  if (reponse.ok) return { ok: true };
  const refus = await refusDe(reponse);
  return { ok: false, code: refus.code === "TEXT_REFUSED" ? "INTERNAL" : refus.code };
}

export function relireFicheHttp(id: string, utilisateur: Utilisateur, appeler: typeof fetch = fetch): Promise<ResultatAction> {
  return actionFicheHttp(id, "review", utilisateur, appeler);
}

export function publierFicheHttp(id: string, utilisateur: Utilisateur, appeler: typeof fetch = fetch): Promise<ResultatAction> {
  return actionFicheHttp(id, "publish", utilisateur, appeler);
}

// The real source of the life cycle: the list and the two actions above.
export function sourceCycleFicheHttp(utilisateur: Utilisateur, appeler: typeof fetch = fetch): SourceCycleFiche {
  return {
    lister: (etat) => listerFichesHttp(etat, appeler),
    relire: (id) => relireFicheHttp(id, utilisateur, appeler),
    publier: (id) => publierFicheHttp(id, utilisateur, appeler),
  };
}

// The shape of a panel's answer (complete or reduced): the fields the screen reads, nothing computed.
function formePanneau(corps: unknown, code: CodePanneau): corps is ReponsePanneau {
  const o = objet(corps);
  return o !== undefined && o.panel === code && typeof o.scope === "string" && typeof o.dataDate === "string" && typeof o.hypothesis === "string";
}

// The reader of a panel (task 37.2): `GET /api/panels/<code>?team=<identifier>&from=<quarter>&to=<quarter>`, the team left out for the whole
// product. A refusal is raised as a `RefusPanneau` carrying its code (the filters' own codes included); the answer is passed on as received.
export async function lirePanneauHttp(code: CodePanneau, filtres: FiltresEcran, appeler: typeof fetch = fetch): Promise<ReponsePanneau> {
  const parametres = new URLSearchParams();
  if (filtres.team !== undefined) parametres.set("team", filtres.team);
  if (filtres.from !== undefined) parametres.set("from", filtres.from);
  if (filtres.to !== undefined) parametres.set("to", filtres.to);
  const requete = parametres.toString();
  const chemin = `${ROUTE_PANNEAUX}${code}`;
  const adresse = requete === "" ? chemin : `${chemin}?${requete}`;
  const reponse = await envoyer(appeler, adresse, { method: "GET", headers: { accept: "application/json" } });
  if (reponse === undefined) throw new RefusPanneau("INTERNAL");
  if (!reponse.ok) {
    const refus = objet(await corpsJson(reponse))?.error;
    throw new RefusPanneau(estRefusFiltres(refus) ? refus : codeConnu(refus));
  }
  const corps = await corpsJson(reponse);
  if (!formePanneau(corps, code)) throw new RefusPanneau("INTERNAL");
  return corps;
}

export function sourcePanneauxHttp(appeler: typeof fetch = fetch): SourcePanneaux {
  return { lire: (code, filtres) => lirePanneauHttp(code, filtres, appeler), simulee: false };
}

// The real source of the dashboard: the reader and the route of the sheet above, not simulated.
export function sourceHttp(utilisateur: Utilisateur, appeler: typeof fetch = fetch): SourceLeadCycle {
  return { lire: () => lireLeadCycleHttp(appeler), creer: creerFicheHttp(utilisateur, appeler), simulee: false };
}

// Whether the server is there: it answered the route of the dashboard (an answer, or a refusal with a code of its own). A network failure,
// or an answer that is not the server's (the page of a development server that does not know the route), is no server.
export async function serveurPresent(appeler: typeof fetch = fetch): Promise<boolean> {
  const reponse = await envoyer(appeler, ROUTE_TABLEAU, { method: "GET", headers: { accept: "application/json" } });
  if (reponse === undefined) return false;
  const corps = objet(await corpsJson(reponse));
  if (corps === undefined) return false;
  return reponse.ok ? formeTableau(corps) : typeof corps.error === "string";
}

// The source the bundle starts with: the real one when the server is present; without a server, the simulated one in development only
// (`developpement`, injected by the entry from the build mode) and none in production, where the screen shows the failure and a retry.
export async function choisirSource(
  simulee: SourceLeadCycle,
  utilisateur: Utilisateur,
  developpement: boolean,
  appeler: typeof fetch = fetch,
): Promise<SourceLeadCycle | undefined> {
  if (await serveurPresent(appeler)) return sourceHttp(utilisateur, appeler);
  return developpement ? simulee : undefined;
}
