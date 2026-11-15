// Task 16.2 (design D17, D34; spec mothra-server, "Counts constant on the branch"): the constant REAL_DATA_COUNTS_ALLOWED of the contract
// package. It fails when the constant is missing and when it is not `false` on the branch; the commit that sets it to `true`, after the
// merge of masking-sums D15 and of its group 7, changes this test in the same reviewed commit. No setting, option or request field
// changes it (static test over the sources of the three packages).
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import * as contrat from "../src/index.ts";

const RACINE = fileURLToPath(new URL("../../", import.meta.url));
const NOM = "REAL_DATA_COUNTS_ALLOWED";
const DECLARATION = "contract/src/donnees-reelles.ts";

function sources(dossier: string): string[] {
  const fichiers: string[] = [];
  for (const entree of readdirSync(dossier, { withFileTypes: true })) {
    if (entree.name === "node_modules" || entree.name === "dist") {
      continue;
    }
    const chemin = join(dossier, entree.name);
    if (entree.isDirectory()) {
      fichiers.push(...sources(chemin));
    } else if (/\.(ts|tsx)$/.test(entree.name)) {
      fichiers.push(chemin);
    }
  }
  return fichiers;
}

test("the constant exists in the public entry of the contract package", () => {
  assert.ok(NOM in contrat, `${NOM} is missing from @mothra/contract`);
});

test("the constant is false on this branch", () => {
  assert.equal((contrat as Record<string, unknown>)[NOM], false);
});

test("the constant is declared once, as a literal, in its own file", () => {
  const texte = readFileSync(join(RACINE, DECLARATION), "utf8");
  assert.match(texte, new RegExp(`export const ${NOM} = false;`));
  const declarations = sources(RACINE).filter((f) => new RegExp(`(const|let|var)\\s+${NOM}\\b`).test(readFileSync(f, "utf8")));
  assert.deepEqual(declarations.map((f) => f.slice(RACINE.length)), [DECLARATION]);
});

test("no setting, option or request field changes it: it is only imported and read, never assigned, never taken from the environment", () => {
  for (const fichier of [...sources(join(RACINE, "contract/src")), ...sources(join(RACINE, "server/src")), ...sources(join(RACINE, "front/src"))]) {
    const relatif = fichier.slice(RACINE.length);
    if (relatif === DECLARATION) {
      continue;
    }
    const lignes = readFileSync(fichier, "utf8").split("\n");
    lignes.forEach((ligne, i) => {
      if (!ligne.includes(NOM)) {
        return;
      }
      const lieu = `${relatif}:${i + 1}`;
      assert.ok(!new RegExp(`${NOM}\\s*(=[^=>]|\\+=|\\|=|&=)`).test(ligne), `${lieu}: assigned`);
      assert.ok(!/process\.env|import\.meta\.env/.test(ligne), `${lieu}: read from the environment`);
      assert.ok(!/Type\.|Value\.|schema|Schema|options|query|body|params/.test(ligne.replace(/\/\/.*$/, "")), `${lieu}: taken from a schema, an option or a request`);
    });
  }
});

test("the configuration module declares no variable that names it", () => {
  const config = readFileSync(join(RACINE, "server/src/config/index.ts"), "utf8");
  assert.ok(!config.includes(NOM) && !/COUNTS/i.test(config));
});
