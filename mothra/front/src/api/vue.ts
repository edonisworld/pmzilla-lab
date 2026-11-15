// Reading of a view through the server's one route, GET /api/views/:view (design D7). Every request goes to the local server by a
// relative path; the API answers codes only, and the front translates them through its catalogues (design D6).
import { estReponseVue, schemaReponseDeVue } from "@mothra/contract/reponse";
import type { Cellule, Contrat, ReponseVue, ValeurSimple } from "@mothra/contract";
import Value from "typebox/value";

// The shared views contract, embedded at build time (column names only, no data): it gives the strict schema of each declared view, so that
// a count column holds a count cell (value at the floor or more, or masked), a statistic or share a measure cell, a plain column a plain
// value, and nothing else. The server validates the same contract at start; the loader (node:fs) is not imported here.
import contratBrut from "../../../../contrats/vues.json" with { type: "json" };

const SCHEMAS_PAR_VUE = new Map((contratBrut as unknown as Contrat).views.map((v) => [v.name, schemaReponseDeVue(v)]));

export type { ReponseVue };

// A cell of a row, as the contract types it: a plain value, or a structured count cell (value or masked).
export type Valeur = Cellule | ValeurSimple;

// The last three are the refusals of the sheet routes (D29): the author reviewing their own sheet, publishing an unreviewed sheet,
// changing a published version.
export const CODES_ERREUR = [
  "UNKNOWN_VIEW",
  "DATABASE_UNAVAILABLE",
  "INTERNAL",
  "NOT_FOUND",
  "BUNDLE_MISSING",
  "SELF_REVIEW_REFUSED",
  "NOT_REVIEWED",
  "VERSION_FROZEN",
  // Completion of a draft (PATCH) and review refusals (D29, task 19.3).
  "UNKNOWN_USER",
  "NOT_AUTHOR",
  "NOT_DRAFT",
  "EFFECT_OR_CAUSE_MISSING",
  "NO_MANAGEMENT_QUESTION",
  // Refusals of the sheet and dashboard routes (task 19.7).
  "INVALID_REQUEST",
  "UNKNOWN_SHEET",
  "THRESHOLDS_NOT_SET",
  // The data date of a sheet (A-66, R-20261112-30, D29): refused at creation (422), stale draft refused at review and publication (409).
  "DATA_DATE_OUT_OF_RANGE",
  "DATA_DATE_STALE",
] as const;
export type CodeErreur = (typeof CODES_ERREUR)[number];

export function estCodeErreur(valeur: unknown): valeur is CodeErreur {
  return typeof valeur === "string" && (CODES_ERREUR as readonly string[]).includes(valeur);
}

// The catalogue key of each API error code.
export const CLES_ERREUR: Record<CodeErreur, string> = {
  UNKNOWN_VIEW: "error.UNKNOWN_VIEW",
  DATABASE_UNAVAILABLE: "error.DATABASE_UNAVAILABLE",
  INTERNAL: "error.INTERNAL",
  NOT_FOUND: "error.NOT_FOUND",
  BUNDLE_MISSING: "error.BUNDLE_MISSING",
  SELF_REVIEW_REFUSED: "error.SELF_REVIEW_REFUSED",
  NOT_REVIEWED: "error.NOT_REVIEWED",
  VERSION_FROZEN: "error.VERSION_FROZEN",
  UNKNOWN_USER: "error.UNKNOWN_USER",
  NOT_AUTHOR: "error.NOT_AUTHOR",
  NOT_DRAFT: "error.NOT_DRAFT",
  EFFECT_OR_CAUSE_MISSING: "error.EFFECT_OR_CAUSE_MISSING",
  NO_MANAGEMENT_QUESTION: "error.NO_MANAGEMENT_QUESTION",
  INVALID_REQUEST: "error.INVALID_REQUEST",
  UNKNOWN_SHEET: "error.UNKNOWN_SHEET",
  THRESHOLDS_NOT_SET: "error.THRESHOLDS_NOT_SET",
  DATA_DATE_OUT_OF_RANGE: "error.DATA_DATE_OUT_OF_RANGE",
  DATA_DATE_STALE: "error.DATA_DATE_STALE",
};

// An unknown code is shown as the internal error: the front never shows a code or a message it does not translate.
export function cleErreur(code: string): string {
  return estCodeErreur(code) ? CLES_ERREUR[code] : CLES_ERREUR.INTERNAL;
}

export class ErreurApi extends Error {
  code: CodeErreur;

  constructor(code: CodeErreur) {
    super(code);
    this.name = "ErreurApi";
    this.code = code;
  }
}

export type LecteurVue = (vue: string) => Promise<ReponseVue>;

async function codeDe(reponse: Response): Promise<CodeErreur> {
  try {
    const corps: unknown = await reponse.json();
    const code = typeof corps === "object" && corps !== null ? (corps as { error?: unknown }).error : undefined;
    return estCodeErreur(code) ? code : "INTERNAL";
  } catch {
    return "INTERNAL";
  }
}

export async function lireVue(vue: string, appeler: typeof fetch = fetch): Promise<ReponseVue> {
  let reponse: Response;
  try {
    reponse = await appeler(`/api/views/${encodeURIComponent(vue)}`, { headers: { accept: "application/json" } });
  } catch {
    throw new ErreurApi("INTERNAL");
  }
  if (!reponse.ok) throw new ErreurApi(await codeDe(reponse));
  let corps: unknown;
  try {
    corps = await reponse.json();
  } catch {
    throw new ErreurApi("INTERNAL");
  }
  // The answer is the contract's, and it is the view asked for: anything else is an internal fault, never shown as data.
  // A view declared in the contract is also checked with its own strict schema (generic union alone would accept a count cell holding 3).
  if (!estReponseVue(corps) || corps.view !== vue) throw new ErreurApi("INTERNAL");
  const schemaDeLaVue = SCHEMAS_PAR_VUE.get(vue);
  if (schemaDeLaVue !== undefined && !Value.Check(schemaDeLaVue, corps)) throw new ErreurApi("INTERNAL");
  return corps;
}

// The TanStack Query options of a view: one key per view, no retry (an error code is an answer, not a fault to hide).
export function optionsVue(vue: string, lire: LecteurVue = lireVue) {
  return {
    queryKey: ["view", vue],
    queryFn: () => lire(vue),
    retry: false,
    refetchOnWindowFocus: false,
  };
}
