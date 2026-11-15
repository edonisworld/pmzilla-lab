// Static check of the package boundaries of ADR 0002, Q3 (task 2.7). Pure functions over file contents: no network, no install.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { posix } from "node:path";

export const PAQUETS = ["contract", "server", "front"] as const;
export type Paquet = (typeof PAQUETS)[number];

// For each package, the Mothra packages it must not import. The front reaches the contract by its package name; any other
// Mothra package, and the contract by a relative path, is a crossing.
const INTERDITS: Record<Paquet, readonly Paquet[]> = {
  contract: ["server", "front"],
  server: ["front"],
  front: ["server"],
};

export interface Fichier {
  chemin: string; // relative to mothra/, with "/" separators
  contenu: string;
}

const EXTENSIONS = /\.(?:ts|tsx|mts|cts|js|jsx|mjs|cjs)$/;
const IGNORES = new Set(["node_modules", "dist"]);

// A string literal is kept only right after `from`, `import`, `import(` or `require(`: those are the import specifiers. Any other
// string is emptied, so a `/*` or an import-like text inside a string neither opens a comment nor counts as an import.
// Limits, accepted: no regular-expression literals, no interpolation `${...}` holding a quote or backtick, no JSX text with an apostrophe.
const AVANT_SPECIFICATEUR = /(?:\bfrom|\bimport|\b(?:import|require)\s*\()\s*$/;

function sansCommentairesNiChaines(source: string): string {
  let sortie = "";
  let i = 0;
  while (i < source.length) {
    const c = source[i];
    const suivant = source[i + 1];
    if (c === "/" && suivant === "*") {
      const fin = source.indexOf("*/", i + 2);
      i = fin < 0 ? source.length : fin + 2;
      sortie += " ";
    } else if (c === "/" && suivant === "/") {
      while (i < source.length && source[i] !== "\n") i++;
    } else if (c === '"' || c === "'" || c === "`") {
      let j = i + 1;
      while (j < source.length && source[j] !== c && (c === "`" || source[j] !== "\n")) j += source[j] === "\\" ? 2 : 1;
      sortie += AVANT_SPECIFICATEUR.test(sortie) ? source.slice(i, j + 1) : c + c;
      i = j + 1;
    } else {
      sortie += c;
      i++;
    }
  }
  return sortie;
}

export function importsDe(contenu: string): string[] {
  const sans = sansCommentairesNiChaines(contenu);
  const trouves: Array<[number, string]> = [];
  const motifs = [
    /\bfrom\s*["']([^"']+)["']/g,
    /\bimport\s*["']([^"']+)["']/g,
    /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g,
    /\brequire\s*\(\s*["']([^"']+)["']\s*\)/g,
  ];
  for (const motif of motifs) {
    for (const m of sans.matchAll(motif)) trouves.push([m.index ?? 0, m[1]]);
  }
  return trouves.sort((a, b) => a[0] - b[0]).map(([, spec]) => spec);
}

function paquetDuChemin(chemin: string): Paquet | null {
  const premier = chemin.split("/")[0];
  return (PAQUETS as readonly string[]).includes(premier) ? (premier as Paquet) : null;
}

function cible(fichier: string, spec: string): Paquet | null {
  if (spec.startsWith(".")) {
    const resolu = posix.normalize(posix.join(posix.dirname(fichier), spec));
    return paquetDuChemin(resolu);
  }
  const m = /^@mothra\/([^/]+)/.exec(spec);
  return m && (PAQUETS as readonly string[]).includes(m[1]) ? (m[1] as Paquet) : null;
}

export function verifierFrontieres(fichiers: Fichier[]): string[] {
  const ecarts: string[] = [];
  for (const { chemin, contenu } of fichiers) {
    const propre = paquetDuChemin(chemin);
    if (propre === null) continue;
    for (const spec of importsDe(contenu)) {
      const vise = cible(chemin, spec);
      if (vise === null || vise === propre) continue;
      const relatif = spec.startsWith(".");
      if (INTERDITS[propre].includes(vise) || relatif) {
        ecarts.push(`frontière de paquet franchie : ${chemin} (paquet ${propre}) importe le paquet ${vise}`);
      }
    }
  }
  return ecarts;
}

export function collecterFichiers(racine: string): Fichier[] {
  const fichiers: Fichier[] = [];
  const parcourir = (dossier: string, relatif: string): void => {
    for (const nom of readdirSync(dossier)) {
      if (IGNORES.has(nom)) continue;
      const complet = `${dossier}/${nom}`;
      const rel = relatif ? `${relatif}/${nom}` : nom;
      if (statSync(complet).isDirectory()) parcourir(complet, rel);
      else if (EXTENSIONS.test(nom)) fichiers.push({ chemin: rel, contenu: readFileSync(complet, "utf8") });
    }
  };
  for (const paquet of PAQUETS) {
    try {
      parcourir(`${racine.replace(/\/$/, "")}/${paquet}`, paquet);
    } catch {
      // package folder absent: nothing to check
    }
  }
  return fichiers;
}
