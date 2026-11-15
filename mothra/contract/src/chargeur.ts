// Loader of the views contract (mothra-slices D2): the floor of five is a constant of the code, the effective threshold is the highest
// of the floor, the contract, the setting and the option, and a missing, invalid or lowering contract is a named refusal.
// Never a fallback and never a built-in list of views: without a valid contract the server serves nothing.
// A refusal names no path and no value. French phrases, the catalogue of design D2.
import { readFileSync } from "node:fs";

import Value from "typebox/value";

import { PLANCHER } from "./plancher.ts";
import { type Contrat, SchemaVues } from "./vues.ts";

export type CodeRefus = "CONTRACT_MISSING" | "CONTRACT_INVALID" | "CONTRACT_FLOOR";

const PHRASES: Record<CodeRefus, string> = {
  CONTRACT_MISSING: "contrat des vues absent",
  CONTRACT_INVALID: "contrat des vues invalide",
  CONTRACT_FLOOR: "seuil du contrat sous le plancher",
};

export class RefusContrat extends Error {
  code: CodeRefus;

  constructor(code: CodeRefus) {
    super(PHRASES[code]);
    this.name = "RefusContrat";
    this.code = code;
  }
}

// Tables of the flow and quality schemas, all migrations: a contract names views, never a table. A safeguard on top of the static test of
// tests/flow_views, which compares the contract with the migrations.
// Remplace : la liste figée à la migration 0020. Retrait : permanent tant que le chargeur garde cette liste ; source : db/migrations,
// écart détecté par tables-interdites.test.ts (R-20261109-20).
export const TABLES_INTERDITES: ReadonlySet<string> = new Set([
  "teams",
  "issues",
  "issue_teams",
  "transitions",
  "links",
  "issue_label_periods",
  "issue_version_periods",
  "issue_current_versions",
  "raw_runs",
  "raw_run_sightings",
  "raw_issue_snapshots",
  "version_photo_versions",
  "version_photo_runs",
  "version_photo_weeks",
  "version_photo_rows",
  "version_photo_n",
  "items",
  "item_teams",
  "team_attributes",
  "team_reviews",
  "contents",
  "assessments",
  "overlay_versions",
  "coaching_feedback",
  "ref_cycles",
  "ref_labels",
  "ref_dw_columns",
  "ref_dw_statuses",
  "ref_state",
  "ref_flow_statuses",
  "ref_unplanned_types",
  "ref_blocking_link_types",
  "issue_delivery_fields",
  "sprints",
  "issue_current_sprints",
  "issue_current_asset_versions",
  "issue_delivery_options",
  "issue_defect_fields",
  "issue_sprint_periods",
  "issue_asset_version_periods",
  "release_versions",
  "raw_version_snapshots",
  "patient_scan_runs",
  "patient_scan_lifts",
]);

// Columns that carry text of a ticket or a person: never exposed by a view of the contract (invariant 4).
const COLONNES_INTERDITES = new Set([
  "key",
  "issue_key",
  "title",
  "summary",
  "description",
  "text",
  "body",
  "content",
  "comment",
  "assignee",
  "reporter",
  "creator",
  "author",
  "person",
  "email",
  "user",
]);

function refuser(code: CodeRefus): never {
  throw new RefusContrat(code);
}

export function validerContrat(valeur: unknown): Contrat {
  if (!Value.Check(SchemaVues, valeur)) {
    refuser("CONTRACT_INVALID");
  }
  const noms = new Set<string>();
  for (const vue of valeur.views) {
    const colonnes = [...vue.countColumns, ...vue.plainColumns, ...(vue.maskableColumns ?? [])];
    const incoherent =
      noms.has(vue.name) ||
      TABLES_INTERDITES.has(vue.name) ||
      vue.schema !== vue.roleKind ||
      new Set(colonnes).size !== colonnes.length ||
      colonnes.some((colonne) => COLONNES_INTERDITES.has(colonne));
    if (incoherent) {
      refuser("CONTRACT_INVALID");
    }
    noms.add(vue.name);
  }
  if (valeur.minThreshold !== undefined && valeur.minThreshold < PLANCHER) {
    refuser("CONTRACT_FLOOR");
  }
  return valeur;
}

export function lireContrat(texte: string): Contrat {
  let valeur: unknown;
  try {
    valeur = JSON.parse(texte);
  } catch {
    return refuser("CONTRACT_INVALID");
  }
  return validerContrat(valeur);
}

export function chargerContrat(chemin: string | URL): Contrat {
  let texte: string;
  try {
    texte = readFileSync(chemin, "utf8");
  } catch (erreur) {
    const code = (erreur as { code?: string }).code;
    return refuser(code === "ENOENT" || code === "ENOTDIR" ? "CONTRACT_MISSING" : "CONTRACT_INVALID");
  }
  return lireContrat(texte);
}

function entierOuRien(valeur: number | null | undefined): number {
  if (valeur === undefined || valeur === null) {
    return 0;
  }
  if (!Number.isInteger(valeur) || valeur < 0) {
    throw new TypeError("seuil : entier positif attendu");
  }
  return valeur;
}

// max(5, contract threshold, setting, option).
export function seuilEffectif(contrat: Contrat, reglage?: number | null, option?: number | null): number {
  return Math.max(PLANCHER, contrat.minThreshold ?? 0, entierOuRien(reglage), entierOuRien(option));
}

// Closed list: a view is accepted only by its exact name as the contract lists it. A table name, a schema-qualified name, another
// case, an injection text or an empty name is refused.
export function vueAcceptee(contrat: Contrat, nom: string): boolean {
  return contrat.views.some((vue) => vue.name === nom);
}
