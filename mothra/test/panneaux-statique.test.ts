// Task 37.1 (routes), static checks on the panel routes: a route under /api/panels/ calls servirPanneau (extension of the list of served
// dashboards, tableaux-servis.ts), and no route nor component names a panel function that composes a total or a share (list of
// fonctions-de-verdict.ts). The test of the test first (fake files), then the real tree.
import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { FONCTIONS_DE_VERDICT, verifierFonctionsDeVerdict } from "./fonctions-de-verdict.ts";
import { collecterFichiers } from "./frontieres.ts";
import { verifierTableauxServis } from "./tableaux-servis.ts";

const racine = fileURLToPath(new URL("..", import.meta.url));

test("a route under /api/panels/ that does not call servirPanneau fails, naming the file", () => {
  const ecarts = verifierTableauxServis([
    { chemin: "server/src/routes/faux-panneau.ts", contenu: 'instance.get("/api/panels/x", {}, async () => ({ points: [] }));\n' },
  ]);
  assert.equal(ecarts.length, 1);
  assert.match(ecarts[0], /server\/src\/routes\/faux-panneau\.ts/);
});

test("a panel route that calls servirPanneau, a comment and another folder are not offences", () => {
  const ecarts = verifierTableauxServis([
    { chemin: "server/src/routes/ok.ts", contenu: 'instance.get("/api/panels/x", {}, async () => servirPanneau(p, mode));\n' },
    { chemin: "server/src/routes/commentaire.ts", contenu: '// "/api/panels/x" is served elsewhere\n' },
    { chemin: "server/test/x.test.ts", contenu: 'inject("/api/panels/x");\n' },
  ]);
  assert.deepEqual(ecarts, []);
});

test("the real panel routes serve every answer through servirPanneau", () => {
  const fichiers = collecterFichiers(racine);
  assert.ok(fichiers.some((f) => f.chemin === "server/src/routes/panneaux.ts"), "the route of the panels is in the tree");
  assert.deepEqual(verifierTableauxServis(fichiers), []);
});

test("a route or a component that names a panel function fails: no rule in the formatting", () => {
  for (const nom of ["panneauStoriesInout", "panneauDefectsInout", "panneauCorrectionShare", "panneauBlockedShare", "partDeDebitEnCorrection"]) {
    assert.ok((FONCTIONS_DE_VERDICT as readonly string[]).includes(nom), nom);
    for (const chemin of ["server/src/routes/panneaux.ts", "front/src/pages/Panneau.ts"]) {
      const ecarts = verifierFonctionsDeVerdict([{ chemin, contenu: `const x = ${nom}(lignes);\n` }]);
      assert.equal(ecarts.length, 1, `${chemin} ${nom}`);
    }
  }
});

test("the service layer of the server may name them: the adapter lives in server/src/fiches/", () => {
  const ecarts = verifierFonctionsDeVerdict([{ chemin: "server/src/fiches/panneaux.ts", contenu: "panneauStoriesInout(l, f, d, 5);\n" }]);
  assert.deepEqual(ecarts, []);
});
