// Task 18.4: no verdict, state or share composed in a route or a component (design D30). The test of the test first (fake files), then the
// real tree.
import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { collecterFichiers } from "./frontieres.ts";
import { FONCTIONS_DE_REDUCTION, FONCTIONS_DE_VERDICT, verifierFonctionsDeVerdict } from "./fonctions-de-verdict.ts";

const racine = fileURLToPath(new URL("..", import.meta.url));

test("a route that calls a verdict function fails, naming the file and the function", () => {
  const ecarts = verifierFonctionsDeVerdict([
    { chemin: "server/src/routes/fausse.ts", contenu: 'import { h5Verdict } from "@mothra/contract";\nexport const v = h5Verdict({});\n' },
  ]);
  assert.equal(ecarts.length, 1);
  assert.match(ecarts[0], /server\/src\/routes\/fausse\.ts.*h5Verdict/);
});

test("a component that names a composition function fails, every function of the list is watched", () => {
  for (const nom of FONCTIONS_DE_VERDICT) {
    const ecarts = verifierFonctionsDeVerdict([{ chemin: "front/src/pages/Fausse.ts", contenu: `const x = ${nom}(1);\n` }]);
    assert.equal(ecarts.length, 1, nom);
    assert.match(ecarts[0], new RegExp(`front/src/pages/Fausse\\.ts.*${nom}`));
  }
});

test("a route or a component that calls a function of the reduced form fails; reading the field of the same name is not an offence", () => {
  for (const nom of FONCTIONS_DE_REDUCTION) {
    for (const chemin of ["server/src/routes/fausse.ts", "front/src/pages/Fausse.ts"]) {
      const ecarts = verifierFonctionsDeVerdict([{ chemin, contenu: `const x = ${nom}(1);\n` }]);
      assert.equal(ecarts.length, 1, `${chemin} ${nom}`);
      assert.match(ecarts[0], new RegExp(nom));
    }
    const lecture = verifierFonctionsDeVerdict([{ chemin: "front/src/pages/Lit.ts", contenu: `const x = fiche.${nom};\nconst y = { ${nom}: 1 };\n` }]);
    assert.deepEqual(lecture, [], nom);
  }
});

test("the contract, the body builder, the tests, a comment, a string and another name are not offences", () => {
  const ecarts = verifierFonctionsDeVerdict([
    { chemin: "contract/src/verdict.ts", contenu: "export function h5Verdict() {}\n" },
    { chemin: "server/src/fiches/corps.ts", contenu: "corpsDepuisVues({});\n" },
    { chemin: "server/test/x.test.ts", contenu: "h5Verdict();\n" },
    { chemin: "server/src/routes/a.ts", contenu: '// h5Verdict is in the contract\n/* verdictFinal */\nconst t = "linkColour";\nconst u = h5VerdictLike;\n' },
  ]);
  assert.deepEqual(ecarts, []);
});

test("the real routes and components compute no verdict, state or share", () => {
  assert.deepEqual(verifierFonctionsDeVerdict(collecterFichiers(racine)), []);
});
