// Task 19.6 (B5): a route that serves a dashboard answer without `servirTableau` fails, naming the file. The test of the test first (fake files),
// then the real tree.
import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { collecterFichiers } from "./frontieres.ts";
import { verifierTableauxServis } from "./tableaux-servis.ts";

const racine = fileURLToPath(new URL("..", import.meta.url));

test("a route under /api/dashboards/ that does not call servirTableau fails, naming the file", () => {
  const ecarts = verifierTableauxServis([
    { chemin: "server/src/routes/backlog.ts", contenu: 'instance.get("/api/dashboards/backlog_age", {}, async () => ({ rows: [] }));\n' },
  ]);
  assert.equal(ecarts.length, 1);
  assert.match(ecarts[0], /server\/src\/routes\/backlog\.ts/);
});

test("a route that calls servirTableau, a route that serves no dashboard, a comment and another folder are not offences", () => {
  const ecarts = verifierTableauxServis([
    { chemin: "server/src/routes/ok.ts", contenu: 'instance.get("/api/dashboards/x", {}, async () => servirTableau(r, mode));\n' },
    { chemin: "server/src/routes/fiches.ts", contenu: 'instance.get("/api/sheets/:id", {}, async () => ({}));\n' },
    { chemin: "server/src/routes/commentaire.ts", contenu: '// "/api/dashboards/x" is served elsewhere\n' },
    { chemin: "server/test/x.test.ts", contenu: 'inject("/api/dashboards/x");\n' },
  ]);
  assert.deepEqual(ecarts, []);
});

test("the real routes serve every dashboard answer through servirTableau", () => {
  const fichiers = collecterFichiers(racine);
  assert.ok(fichiers.some((f) => f.chemin === "server/src/routes/tableaux.ts"), "the route of the dashboard is in the tree");
  assert.deepEqual(verifierTableauxServis(fichiers), []);
});
