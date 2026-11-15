// Static check of "one data layer" (design D30, task 18.0): the server and the front declare no type that the contract package
// exports; they import it from `@mothra/contract`. Pure functions over file contents: no network, no install.
import type { Fichier } from "./frontieres.ts";

// The names listed in the `export { ... }` and `export type { ... }` blocks of the contract's entry (comments left out).
export function nomsExportesDuContrat(index: string): string[] {
  const sans = index.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/\/\/[^\n]*/g, "");
  const noms = new Set<string>();
  for (const m of sans.matchAll(/export\s+(?:type\s+)?\{([^}]*)\}/g)) {
    for (const brut of m[1].split(",")) {
      const morceau = brut.trim().replace(/^type\s+/, "");
      if (morceau === "") continue;
      const apres = /\bas\s+(\w+)$/.exec(morceau);
      noms.add(apres ? apres[1] : morceau);
    }
  }
  return [...noms].sort();
}

const DECLARATION = /\b(?:type|interface|class|enum|const|let|var|function)\s+(\w+)/g;

// Homonyms, not answer types: the server's `CodeRefus` is the start-refusal code (D7, D17), a different type from the contract's loader
// code of the same name, and test/refus.test.ts imports it by that name. Permanent until that test renames it; replaces no other list.
const HOMONYMES: Readonly<Record<string, readonly string[]>> = { "server/src/refus.ts": ["CodeRefus"] };

// The files checked are those of `server/src` and `front/src`: the sources of the two consumers (their tests may build their own values).
export function verifierUneCouche(fichiers: Fichier[], exportes: readonly string[]): string[] {
  const connus = new Set(exportes);
  const ecarts: string[] = [];
  for (const { chemin, contenu } of fichiers) {
    if (!chemin.startsWith("server/src/") && !chemin.startsWith("front/src/")) continue;
    const sans = contenu.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, "");
    for (const m of sans.matchAll(DECLARATION)) {
      if (connus.has(m[1]) && !(HOMONYMES[chemin] ?? []).includes(m[1])) {
        ecarts.push(`une seule couche de données : ${chemin} déclare « ${m[1]} », déjà exporté par @mothra/contract`);
      }
    }
  }
  return ecarts;
}
