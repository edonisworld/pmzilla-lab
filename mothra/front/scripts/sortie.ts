// The two helpers that the scripts writing a page outside the repository share (`page-pastilles.ts`, `catalogue.ts`): the root of the
// repository and the test "this path is inside that folder". They were copied from one script to the other; this module is the one source.
// Replaces: the two copies. Removal: permanent while a script writes a page outside the repository.
import { existsSync, realpathSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";

// The nearest ancestor of the script that holds a `.git` entry (a folder, or a file in a worktree): the root of the repository.
export function racineGit(depart: string): string | undefined {
  let dossier = resolve(depart);
  for (;;) {
    if (existsSync(join(dossier, ".git"))) return realpathSync(dossier);
    const parent = dirname(dossier);
    if (parent === dossier) return undefined;
    dossier = parent;
  }
}

export function dansLe(dossier: string, chemin: string): boolean {
  const r = relative(dossier, chemin);
  return r === "" || (!r.startsWith("..") && !r.startsWith(sep) && r !== "..");
}
