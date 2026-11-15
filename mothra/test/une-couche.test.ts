// Task 18.0: static test of "one data layer" (design D30): no answer type declared in the server or the front when the contract
// package exports it. Fake file sets first, then the real tree.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { collecterFichiers } from "./frontieres.ts";
import { nomsExportesDuContrat, verifierUneCouche } from "./une-couche.ts";

const racine = fileURLToPath(new URL("..", import.meta.url));

test("the exported names are read from the value and type export blocks, comments left out", () => {
  const index = 'export { A, b as c } from "./a.ts";\nexport type { D, E } from "./d.ts"; // export { Z }\n/* export { Y } */\nexport {\n  F,\n  type G,\n} from "./f.ts";\n';
  assert.deepEqual(nomsExportesDuContrat(index), ["A", "D", "E", "F", "G", "c"]);
});

test("a type declared in the server or the front under a name the contract exports fails, naming the file and the type", () => {
  const ecarts = verifierUneCouche(
    [
      { chemin: "server/src/a.ts", contenu: "export interface Brouillon { id: string }\n" },
      { chemin: "front/src/b.ts", contenu: 'export type Mesure = { state: "value" };\n' },
      { chemin: "front/src/c.ts", contenu: "const ReponseLeadCycle = 1;\n" },
    ],
    ["Brouillon", "Mesure", "ReponseLeadCycle"],
  );
  assert.equal(ecarts.length, 3);
  assert.match(ecarts[0], /server\/src\/a\.ts.*Brouillon/);
  assert.match(ecarts[1], /front\/src\/b\.ts.*Mesure/);
  assert.match(ecarts[2], /front\/src\/c\.ts.*ReponseLeadCycle/);
});

test("an import, a name of another type, a comment and a test file are not declarations", () => {
  const ecarts = verifierUneCouche(
    [
      { chemin: "front/src/a.ts", contenu: 'import type { Mesure } from "@mothra/contract";\nexport type Effectif = Mesure;\n// type Mesure = 1\n/* interface Mesure {} */\n' },
      { chemin: "front/test/b.ts", contenu: "interface Mesure { x: number }\n" },
      { chemin: "contract/src/c.ts", contenu: "export type Mesure = 1;\n" },
    ],
    ["Mesure"],
  );
  assert.deepEqual(ecarts, []);
});

test("the contract exports the answer types of the dashboard and of the sheet request", () => {
  const noms = nomsExportesDuContrat(readFileSync(`${racine}contract/src/index.ts`, "utf8"));
  for (const nom of ["Mesure", "LigneTrimestre", "ReponseLeadCycle", "PointTrimestre", "SerieEquipe", "DemandeFiche", "Brouillon", "ReponseFiche", "CorpsFiche", "MethodeFiche", "TexteLibre", "Part", "Seuil", "Trimestre"]) {
    assert.ok(noms.includes(nom), nom);
  }
});

test("the real server and front declare no type that the contract package exports", () => {
  const exportes = nomsExportesDuContrat(readFileSync(`${racine}contract/src/index.ts`, "utf8"));
  assert.deepEqual(verifierUneCouche(collecterFichiers(racine), exportes), []);
});
