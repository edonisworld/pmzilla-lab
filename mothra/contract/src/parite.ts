// Player of the synthetic parity cases (mothra-slices D4): one file of the contract folder, played here by the npm suite and, later,
// by the Python suite of the reader of aggregated views. It stops at the first differing case and names it.
import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";

import { cellule } from "./cellule.ts";
import type { Cellule } from "./cellule.ts";
import { RefusContrat, seuilEffectif, validerContrat, vueAcceptee } from "./chargeur.ts";
import type { Contrat } from "./vues.ts";

export interface CasCellule {
  name: string;
  view: string;
  column: string;
  value: number | string | null;
  threshold: number;
  expected: Cellule | string;
}

export interface CasVue {
  name: string;
  view: string;
  accepted: boolean;
}

export interface CasSeuil {
  name: string;
  contractThreshold: number | null;
  setting: number | null;
  option: number | null;
  expected: { threshold: number } | { refusal: string };
}

export interface CasParite {
  cells: CasCellule[];
  views: CasVue[];
  thresholds: CasSeuil[];
}

// The file must hold the three arrays of cases; anything else is refused, naming the missing or mistyped key.
export function chargerCasParite(chemin: string | URL): CasParite {
  const lu: unknown = JSON.parse(readFileSync(chemin, "utf8"));
  if (lu === null || typeof lu !== "object" || Array.isArray(lu)) {
    throw new Error("fichier de cas de parité invalide : objet attendu");
  }
  for (const cle of ["cells", "views", "thresholds"]) {
    if (!Array.isArray((lu as Record<string, unknown>)[cle])) {
      throw new Error(`fichier de cas de parité invalide : tableau attendu pour ${cle}`);
    }
  }
  return lu as CasParite;
}

// A count column becomes a cell, a plain column stays a plain value; any other column has no result (never a guess).
function resultatCellule(contrat: Contrat, cas: CasCellule): unknown {
  const vue = contrat.views.find((v) => v.name === cas.view);
  if (vue === undefined) {
    return undefined;
  }
  if (vue.countColumns.includes(cas.column)) {
    return cellule(cas.value as number | null, cas.threshold);
  }
  if (vue.plainColumns.includes(cas.column)) {
    return cas.value;
  }
  return undefined;
}

function resultatSeuil(contrat: Contrat, cas: CasSeuil): unknown {
  const candidat = cas.contractThreshold === null ? { views: contrat.views } : { views: contrat.views, minThreshold: cas.contractThreshold };
  try {
    return { threshold: seuilEffectif(validerContrat(candidat), cas.setting, cas.option) };
  } catch (erreur) {
    if (erreur instanceof RefusContrat) {
      return { refusal: erreur.code };
    }
    throw erreur;
  }
}

function differe(nom: string): never {
  throw new Error(`cas de parité différent : ${nom}`);
}

// Any error raised while a case is played (a bad value, a malformed case) makes that case differ: it is caught and named.
function joue(nom: string, conforme: () => boolean): void {
  let ok: boolean;
  try {
    ok = conforme();
  } catch {
    ok = false;
  }
  if (!ok) {
    differe(nom);
  }
}

export function jouerCasParite(cas: CasParite, contrat: Contrat): void {
  for (const c of cas.cells) {
    joue(c.name, () => isDeepStrictEqual(resultatCellule(contrat, c), c.expected));
  }
  for (const c of cas.views) {
    joue(c.name, () => vueAcceptee(contrat, c.view) === c.accepted);
  }
  for (const c of cas.thresholds) {
    joue(c.name, () => isDeepStrictEqual(resultatSeuil(contrat, c), c.expected));
  }
}
