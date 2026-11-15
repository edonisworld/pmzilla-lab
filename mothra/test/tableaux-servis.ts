// Static check of task 19.6 (B5): a route of `server/src/routes/` that serves a dashboard answer (a path under `/api/dashboards/`) calls
// `servirTableau` of the service layer, the one entry of the reduction on real data (design D34 point 7). It protects the routes to come
// (tasks 37 and 40). Pure function over file contents: no network, no install.
// Extended by task 37.1 (routes): the same rule for a path under `/api/panels/`, whose entry is `servirPanneau` (added, nothing of the first
// rule changed; the extension reads the same list below, no second check).
// Replaces: nothing. Removal condition: with the end of the exception of D34 point 6 (REAL_DATA_COUNTS_ALLOWED true for good), when the
// reduction itself goes. Source of the paths and the names: server/src/routes/tableaux.ts, server/src/routes/panneaux.ts and
// server/src/service.ts.
import type { Fichier } from "./frontieres.ts";

const PREFIXE_TABLEAUX = "/api/dashboards/";
const ENTREE = "servirTableau";
const ENTREES_PAR_PREFIXE: ReadonlyArray<readonly [string, string]> = [
  [PREFIXE_TABLEAUX, ENTREE],
  ["/api/panels/", "servirPanneau"],
];

function sansCommentaires(contenu: string): string {
  return contenu.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, "");
}

export function verifierTableauxServis(fichiers: Fichier[]): string[] {
  const ecarts: string[] = [];
  for (const { chemin, contenu } of fichiers) {
    if (!chemin.startsWith("server/src/routes/")) continue;
    const code = sansCommentaires(contenu);
    for (const [prefixe, entree] of ENTREES_PAR_PREFIXE) {
      if (code.includes(prefixe) && !new RegExp(`\\b${entree}\\b`).test(code)) {
        ecarts.push(`tableau servi sans réduction : ${chemin} sert un chemin ${prefixe}… sans appeler ${entree}`);
      }
    }
  }
  return ecarts;
}
