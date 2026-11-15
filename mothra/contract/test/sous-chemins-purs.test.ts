// The browser-safe subpaths of the contract package (`./equipe`, `./listes-fiche`): the front imports their values at run time, so neither
// they nor anything they import may reach Node (review of 19.3, B1; the package entry re-exports node-only loaders). Static test: the
// run-time imports are followed from each subpath, the type-only imports (erased) are not.
import assert from "node:assert/strict";
import { builtinModules } from "node:module";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const SRC = new URL("../src/", import.meta.url);
const SOUS_CHEMINS = ["./equipe", "./listes-fiche", "./composition"];

function importsAExecution(source: string): string[] {
  const specifieurs: string[] = [];
  for (const m of source.matchAll(/^(?:import|export)\s+(?!type\b)[^;]*?from\s+["']([^"']+)["']/gm)) specifieurs.push(m[1]);
  for (const m of source.matchAll(/^import\s+["']([^"']+)["']/gm)) specifieurs.push(m[1]);
  for (const m of source.matchAll(/\b(?:import|require)\(\s*["']([^"']+)["']\s*\)/g)) specifieurs.push(m[1]);
  return specifieurs;
}

function suivre(fichier: string, vus: Set<string>, natifs: string[]): void {
  if (vus.has(fichier)) return;
  vus.add(fichier);
  for (const specifieur of importsAExecution(readFileSync(new URL(fichier, SRC), "utf8"))) {
    if (specifieur.startsWith("node:") || builtinModules.includes(specifieur)) natifs.push(`${fichier} importe ${specifieur}`);
    else if (specifieur.startsWith(".")) suivre(specifieur.replace(/^\.\//, ""), vus, natifs);
    else natifs.push(`${fichier} importe le paquet ${specifieur}`);
  }
}

const exports = (JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { exports: Record<string, string> }).exports;

for (const sousChemin of SOUS_CHEMINS) {
  test(`the subpath ${sousChemin} is declared and imports nothing from Node, directly or through the modules it imports`, () => {
    assert.ok(Object.hasOwn(exports, sousChemin), `sous-chemin absent de exports : ${sousChemin}`);
    const natifs: string[] = [];
    const vus = new Set<string>();
    suivre(exports[sousChemin].replace(/^\.\/src\//, ""), vus, natifs);
    assert.deepEqual(natifs, []);
  });
}

test("the checker sees a node: import, a native module and a package, and ignores a type-only import", () => {
  assert.deepEqual(importsAExecution('import { a } from "node:fs";\nimport b from "path";\nexport { c } from "./c.ts";'), ["node:fs", "path", "./c.ts"]);
  assert.deepEqual(importsAExecution('import type { A } from "node:fs";\nexport type { B } from "./b.ts";'), []);
});
