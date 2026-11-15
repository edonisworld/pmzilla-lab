// What the sheet routes need from Mothra's own storage (design D20, D29, task 18.1). The routes never see a driver. Two parts, both
// implemented by the storage access (db/stockage.ts): the thresholds, on `mothra.threshold_history`, and the sheets, on `mothra.sheets`
// (with the context columns of the migration 0027) and `mothra.published_versions`. The test double (test/depot-memoire.ts) implements both.
import { createHash } from "node:crypto";

import type { CorpsFiche, EtatDeLaFiche, QuestionDeDirection, TexteLibre } from "@mothra/contract";

export interface SeuilStocke {
  code: string;
  value: number;
  setOn: string; // ISO date
  setBy: string; // a pseudonymous identifier, never a name
}

// The dated threshold history: insertion only (no update, no delete, the role has none). The server never reads it as a verdict input.
export interface DepotSeuils {
  seuils(): Promise<SeuilStocke[]>;
  ajouterSeuil(seuil: SeuilStocke): Promise<void>;
}

// The computed body of a sheet (verdict, explanations, signal, shares, method face): what the verdict service gives, aggregates only.
export type CorpsCalcule = Omit<CorpsFiche, "id" | "effect" | "cause">;

// The content frozen at publication (author's decision of 2026-10-29): the computed body and the written parts, effect, cause and management
// question, all in the fingerprint. A published sheet is read from this alone; the table is not read again for it.
export type ContenuFige = CorpsCalcule & { effect: TexteLibre; cause: TexteLibre; managementQuestion: QuestionDeDirection };

// Thrown by the depot when the sheet is no longer a reviewed one at the moment of the freeze (already published by another request): the
// route answers VERSION_FROZEN (409).
export class FicheDejaPubliee extends Error {
  constructor() {
    super("sheet already published");
    this.name = "FicheDejaPubliee";
  }
}

export interface FicheStockee {
  id: string;
  chart: string;
  scope: string;
  dataDate: string;
  state: EtatDeLaFiche;
  managementQuestion?: QuestionDeDirection;
  effect?: TexteLibre;
  cause?: TexteLibre;
  createdBy: string;
  reviewedBy?: string;
  published?: { version: number; content: ContenuFige; fingerprint: string; publishedBy: string; publishedOn: string };
}

// One sheet of a list (audit #629, A-04): enough to find it and open it, nothing written and nothing computed.
export interface FicheListee {
  id: string;
  chart: string;
  scope: string;
  dataDate: string;
  state: EtatDeLaFiche;
}

// The most sheets a list holds (the newest first): a list is a way to find a sheet, not a report.
export const LIMITE_LISTE_FICHES = 100;

export interface DepotFiches {
  // The sheets of one state, the newest first, at most `LIMITE_LISTE_FICHES`.
  lister(etat: EtatDeLaFiche): Promise<FicheListee[]>;
  creer(entree: {
    chart: string;
    scope: string;
    dataDate: string;
    managementQuestion?: QuestionDeDirection;
    effect?: TexteLibre;
    cause?: TexteLibre;
    createdBy: string;
  }): Promise<string>;
  lire(id: string): Promise<FicheStockee | null>;
  // The day the sheet was created (`created_at`, ISO date), the first reading of its data for "threshold modified after reading" (Q8);
  // kept apart from `lire` so that the stored sheet keeps its shape. Null for an unknown sheet.
  creeeLe(id: string): Promise<string | null>;
  // Completes a draft: only the fields given change. Touches nothing but a draft.
  modifier(id: string, changement: { managementQuestion?: QuestionDeDirection; effect?: TexteLibre; cause?: TexteLibre }): Promise<void>;
  relire(id: string, reviewer: string): Promise<void>;
  // Inserts the frozen version and sets the state `published`; the version number is the next one of the sheet.
  publier(id: string, entree: { content: ContenuFige; fingerprint: string; publishedBy: string }): Promise<{ version: number; publishedOn: string }>;
}

// The users of the application (`mothra.users`): a header that names none is refused (UNKNOWN_USER). Reading only: no user is written here.
export interface DepotUtilisateurs {
  utilisateurExiste(id: string): Promise<boolean>;
}

function canonique(valeur: unknown): string {
  if (Array.isArray(valeur)) return `[${valeur.map(canonique).join(",")}]`;
  if (valeur !== null && typeof valeur === "object") {
    const cles = Object.keys(valeur as Record<string, unknown>)
      .filter((c) => (valeur as Record<string, unknown>)[c] !== undefined)
      .sort();
    return `{${cles.map((c) => `${JSON.stringify(c)}:${canonique((valeur as Record<string, unknown>)[c])}`).join(",")}}`;
  }
  return JSON.stringify(valeur) ?? "null";
}

// The fingerprint of a frozen content: SHA-256 of its canonical JSON (keys sorted, undefined left out), 64 lower-case hexadecimal digits,
// the shape the column `published_versions.fingerprint` accepts.
export function empreinte(contenu: unknown): string {
  return createHash("sha256").update(canonique(contenu)).digest("hex");
}
