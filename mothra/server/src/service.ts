// Service layer: turns the rows of a view into the answer of the API (design D7 points 3 and 4): count columns become structured cells
// (a NULL or a count under the threshold is masked, nothing of it kept), the other columns stay plain values. Only the columns of the
// contract are copied: anything else a row holds is dropped here, and a second time by the response schema.
import { masquerVue, partsDAttente } from "@mothra/contract";
import type { EntreePartsDAttente, LigneBrute, PartsDAttente, ReponseVue, ValeurSimple, Vue } from "@mothra/contract";

import { BaseIndisponible } from "./db/acces.ts";
import type { AccesVues, LigneBase } from "./db/acces.ts";

// A count read from the driver: a number, a bigint or a digit string (PostgreSQL bigint), or NULL.
function compte(valeur: unknown): number | null {
  if (valeur === null || valeur === undefined) {
    return null;
  }
  if (typeof valeur === "number") {
    return valeur;
  }
  if (typeof valeur === "bigint") {
    return Number(valeur);
  }
  if (typeof valeur === "string" && /^[0-9]{1,15}$/.test(valeur)) {
    return Number(valeur);
  }
  throw new TypeError("compte : entier ou NULL attendu");
}

// A measure read from the driver (a statistic or a share): a number, a bigint, a numeric string (PostgreSQL numeric), or NULL.
function mesure(valeur: unknown): number | null {
  if (valeur === null || valeur === undefined) {
    return null;
  }
  if (typeof valeur === "number") {
    return valeur;
  }
  if (typeof valeur === "bigint") {
    return Number(valeur);
  }
  if (typeof valeur === "string" && /^-?[0-9]{1,15}(\.[0-9]{1,15})?$/.test(valeur)) {
    return Number(valeur);
  }
  throw new TypeError("mesure : nombre ou NULL attendu");
}

function simple(valeur: unknown): ValeurSimple {
  if (valeur === null || valeur === undefined) {
    return null;
  }
  if (typeof valeur === "number" || typeof valeur === "string") {
    return valeur;
  }
  return String(valeur);
}

// The driver gives a `date` column as a Date at local midnight; the masking and the contract read the ISO text of a date. (The numeric
// strings of the statistics and shares are read by `mesure` below.)
function normaliser(ligne: LigneBase): LigneBase {
  const sortie: LigneBase = {};
  for (const [colonne, valeur] of Object.entries(ligne)) {
    sortie[colonne] =
      valeur instanceof Date
        ? `${String(valeur.getFullYear()).padStart(4, "0")}-${String(valeur.getMonth() + 1).padStart(2, "0")}-${String(valeur.getDate()).padStart(2, "0")}`
        : valeur;
  }
  return sortie;
}

// The one path of a view to an answer, for the route of the views and for the body of the sheets (task 18.4): the rows read from the
// access, then the masking of the service. Any failure of the access is BaseIndisponible, whatever its form; a fault of the masking
// itself is not (it stays an internal error). The sheets never read a view any other way.
// Relation T3 (masking-sums D17, R-20261031-11): the lead time and throughput view is masked with the rows of `v_team_weekly_resolved`, read
// here with the same access (the view is internal to the server: it is never served).
const VUE_HEBDO: Vue = {
  name: "v_team_weekly_resolved",
  schema: "flow",
  roleKind: "flow",
  plainColumns: ["team", "type", "week_start"],
  countColumns: ["tickets"],
};

export async function lireVueMasquee(acces: AccesVues, vue: Vue, seuil: number): Promise<ReponseVue> {
  let lignes: LigneBase[];
  let hebdo: LigneBase[] | undefined;
  try {
    lignes = await acces.lireVue(vue);
    if (vue.name === "v_team_lead_time_throughput") {
      hebdo = await acces.lireVue(VUE_HEBDO);
    }
  } catch {
    throw new BaseIndisponible();
  }
  const brutesHebdo: LigneBrute[] | undefined = hebdo?.map(normaliser).map((ligne) => ({
    team: simple(ligne.team),
    type: simple(ligne.type),
    week_start: simple(ligne.week_start),
    tickets: compte(ligne.tickets),
  }));
  return composerReponse(vue, lignes.map(normaliser), seuil, brutesHebdo);
}

// The single point where the rows of a served view become the answer: every masking rule (floor, raised threshold, pairs, series,
// statistics and shares) is applied by `masquerVue` of the contract package, never here.
// `hebdo`: the rows of the weekly view for the relation T3 (masking-sums D17), when the caller has read them; see the note of lireVueMasquee.
export function composerReponse(vue: Vue, lignes: LigneBase[], seuil: number, hebdo?: LigneBrute[]): ReponseVue {
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
  const brutes: LigneBrute[] = lignes.map((ligne) => {
    const sortie: LigneBrute = {};
    for (const colonne of vue.plainColumns) {
      sortie[colonne] = simple(ligne[colonne]);
    }
    for (const colonne of vue.maskableColumns ?? []) {
      sortie[colonne] = mesure(ligne[colonne]);
    }
    for (const colonne of vue.countColumns) {
      sortie[colonne] = compte(ligne[colonne]);
    }
    return sortie;
  });
  const rows = masquerVue(vue, brutes, seuil, hebdo);
  return { view: vue.name, threshold: seuil, columns: colonnes, rows, sources: [vue.schema] };
}

// ---- The switch of the reduced form (mothra-slices D34, tasks 19.5 and 19.6) --------------------------------------------------------
// The functions (reduitEnMode, servirCorps, servirTableau, servirPanneau) and ModeDonnees live in the contract since R-20261031-61 (Q113):
// they depend on nothing of the server, so the tests of the front call the same ones. This module re-exports them, so that the routes keep
// one import and every route still goes through the one entry; there is no copy. The routes call these functions and never decide.
// Removal of the re-export: with the end of the exception (D34 point 6), when reduitEnMode is always false.
export { reduitEnMode, servirCorps, servirPanneau, servirTableau, servirVue } from "@mothra/contract";
export type { ModeDonnees } from "@mothra/contract";

// The bars of the share of waiting (mothra-demo-habillage D3b, R-20261101-20): the one place where `partsDAttente` of the contract is called.
// Applied at each reading of a sheet, on the body as the storage or the service gave it (full or reduced, a frozen version included), after
// `reduceToStatistics` since the function reads only fields the reduced form keeps. The result is never stored: the freeze takes the body
// before this call (Q151, R-20261101-32). Any `waitShares` the body held is replaced; a hypothesis 5 body (or one without ratios) gets none.
// Replaces: nothing. Removal: permanent while the bar in parts measures hypothesis 1.
export function avecPartsDAttente<T extends EntreePartsDAttente & { waitShares?: PartsDAttente }>(corps: T): T {
  const copie: Record<string, unknown> = { ...corps };
  delete copie.waitShares;
  const parts = partsDAttente(corps);
  if (parts !== undefined) copie.waitShares = parts;
  return copie as unknown as T;
}
